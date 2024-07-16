import asyncio
import os
import random
import re
from enum import Enum
from typing import Dict, Optional, Tuple, Callable, Any, Union
from urllib.parse import quote

import aiohttp
from aiohttp import ClientResponseError
from cache import AsyncLRU
from loguru import logger

from mediasorter.lib.config import MetadataProviderApi
from mediasorter.lib.models import MovieMetadata, TvShowMetadata
from mediasorter.lib.overrides import read_search_overrides
from mediasorter.lib.utils import split_and_lower

max_concurrent_requests = os.environ.get("MEDIASORTER_MAX_CONCURRENT_REQUESTS") or 10
published_search_overrides = read_search_overrides()


class Registry:

    mapping: dict[str, type['MetadataApi']]

    def __init__(self):
        self.mapping = {}

    def get(self, name: str):
        return self.mapping.get(name)

    def from_config(self, api_config: MetadataProviderApi):
        return self.get(api_config.name)

    # def register(self, names: list[str]):
    #     def decorator(cls):
    #         def inner(*args, **kwargs):
    #             for name in names:
    #                 self.mapping[name] = cls
    #             return cls(*args, **kwargs)
    #
    #         return inner
    #
    #     return decorator

    def register(self, cls):
        if keys := getattr(cls, "registry_keys", []):
            for key in keys:
                self.mapping[key] = cls
        self.mapping[cls.__name__.lower()] = cls


class TvMetadataProviders(Registry):
    pass


tv_metadata_providers = TvMetadataProviders()


class MovieMetadataProviders(Registry):
    pass


movie_metadata_providers = MovieMetadataProviders()


class MetadataQueryError(Exception):
    pass


class MetadataNotFoundError(MetadataQueryError):

    search_term: str


def validation(fn):
    # just a dummy marker
    return fn


class MetadataApi:

    # These attributes can be hard-coded in the implementation
    # and overridden via configuration.
    key: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    search_overrides: Dict[str, str] = {}

    semaphore: asyncio.Semaphore

    def __init__(self, config: MetadataProviderApi, search_overrides: Dict[str, str] = None) -> None:
        self.key = config.key
        self.url = config.url
        self.path = config.path
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        if search_overrides:
            self.search_overrides = search_overrides

    async def _query(self, *args, **kwargs) -> Union[TvShowMetadata, MovieMetadata]:
        """
        The high level query function used to query the database. Returns media metadata
        in a format specific to the actual implementation.

        MUST return a valid response, otherwise raise any MetadataQueryException.
        """
        raise NotImplemented

    async def query(self, *args, **kwargs) -> Union[TvShowMetadata, MovieMetadata]:
        return await self._query(*args, **kwargs)

    @staticmethod
    @AsyncLRU(maxsize=1024)
    async def request(url: str) -> dict:
        """
        A wrapper around the actual request that caches a successful response is obtained.
        Otherwise, ClientResponseError is raised.

        :param url: Specify the url that we want to request
        :return: A json object
        """
        logger.debug(f"Network request: [GET]({url})")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()  # Raised errors don't get cached.
                data = await response.json()
        return data

    async def async_fetch_json(self, url, retry=0, max_retries=4):
        """
        A wrapper around the requests function that handles retries and error handling.
        It returns the raw JSON response, or raises an exception if it eventually fails
        to get a valid response.

        :param url: specify the url to fetch
        :param retry: int: retry counter (0 = the actual 1st request, not a re-try yet)
        :param max_retries: int: limit the number of retries in case of a 429 or 503 errors
        :return: the result of the metadata API
        """
        logger.debug(f"fetching '{url}', retries={retry}/{max_retries}")
        await self.semaphore.acquire()
        try:
            return await MetadataApi.request(url)
        except ClientResponseError as e:
            # Running too many queries at once causes the API (TV Maze at the very least)
            # to decline our requests. Simple wait and retry seems to be sufficient.
            if e.status in (429, 503) and retry < max_retries:
                wait_sec = random.randint(10, 100) / 100 * (retry + 1)
                logger.warning(f"Service unavailable, retrying in {wait_sec}s.")
                await asyncio.sleep(wait_sec)
                return await self.async_fetch_json(url, retry + 1)
            raise MetadataQueryError(e)
        finally:
            self.semaphore.release()

    async def try_harder(
        self,
        search_term: str,
        validation_func: Callable[[dict, Any], Any] = None,  # must raise
        validation_callback_args: Tuple = None,
        to_be_raised: Exception = None,
        try_index: int = 1,
        min_len: int = 1
    ) -> Any:
        """
        A helper function that tries to find the metadata by searching for it in an iterative way.
        It does this by removing one word from the end of the search term and trying again. If it
        fails, then it removes another word and tries again until min_len is reached.

        :param search_term: Search for the show
        :param validation_func: Validate the response data (! must raise MetadataQueryException)
        :param validation_callback_args:Tuple=None: Pass arguments to the validation callback
        :param to_be_raised: Pass an exception to be raised once the function eventually fails.
        :param try_index: Keep track of the number of tries
        :param min_len: set the minimum words count to be searched for.
        :return: The response data "as-is" if it matches provided validation fn.
        """
        split = search_term.split()

        while len(split) >= min_len:
            search_title = self.clean_search_term(" ".join(split))
            # search_title = quote(search_title_in)
            logger.info(f"{try_index}. try: search='{search_title}'")
            show_url = self.url + "/" + self.path.format(title=quote(search_title))
            try:
                response_data = await self.async_fetch_json(show_url)
                return await validation_func(
                    response_data,
                    search_title,
                    *(validation_callback_args or tuple())
                )
            except MetadataQueryError as e:
                logger.debug(f"Invalid search result: {e}")
                if not to_be_raised:
                    to_be_raised = e
                return await self.try_harder(
                    search_term=" ".join(split[:-1]),
                    validation_func=validation_func,
                    validation_callback_args=validation_callback_args,
                    to_be_raised=to_be_raised,  # propagate "the original" exc
                    try_index=try_index + 1,
                    min_len=min_len
                )
        raise to_be_raised or MetadataQueryError(f"No exception provided, query failed: "
                                                 f"{search_term=}, {try_index}. try.")

    def clean_search_term(self, string, overrides: Dict[str, str] = None) -> str:
        parts = string.split()
        if not parts:
            parts = [string]

        # Skip all the words "the" in the title, because TVMaze seems to choke on this.
        # * The leading 'the' needs to be preserved though...
        first_the = None
        if re.match('^[Tt]he$', parts[0]):
            first_the = parts.pop(0)
        parts = [word for word in parts if not re.match('^[Tt]he$', word)]
        if first_the:
            parts.insert(0, first_the)

        # This seems to yield better results than '+'.
        search_title = ' '.join(parts)

        # search_title = title
        if overrides and search_title in overrides:
            new_name = overrides[string]
            logger.debug(f"Overriding search title: '{string}' -> '{new_name}'")
            search_title = new_name

        search_title = search_title.replace("'", "")

        return search_title


class TvShowMetadataApi(MetadataApi):

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        tv_metadata_providers.register(cls)

    async def query(self, title: str, season_id: int, episode_id: int) -> TvShowMetadata:
        raise NotImplemented


class MovieMetadataApi(MetadataApi):

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        movie_metadata_providers.register(cls)

    async def query(self, title: str, year: str) -> MovieMetadata:
        raise NotImplemented


class TvMaze(TvShowMetadataApi):

    # Base URL for TV Maze; should generally not be changed (can be overridden via config)
    url: str = "https://api.tvmaze.com"

    # Search path for TV Maze; should generally not be changed (can be overridden via config)
    # Variables replaced at runtime:
    #  * "title": the show name query, extracted from the source filename
    path = "singlesearch/shows?q={title}&embed=episodes"

    async def _match_tv_show(
            self, series_data: dict, search_title: str, season_id: int, episode_id: int
    ) -> Tuple[dict, dict]:
        """
        Find the correct episode in the series episodes list.

        :param series_data: dict: Pass the data from _get_series_data() to _match_tv_show()
        :param season_id: int: Specify the season number
        :param episode_id: int: Specify the episode number
        :return: A dictionary with the episode data
        """

        @validation
        def find_episode(e_list):
            for episode in e_list:
                if episode.get('season') == season_id and episode.get('number') == episode_id:
                    return episode

        episode_list = series_data['_embedded'].get('episodes', [])
        correct_episode = find_episode(episode_list)
        if not correct_episode:
            logger.warning(f"Episode {season_id=} {episode_id=} not found.")

            if series_data.get("_links") and series_data["_links"].get("self"):
                alternative_url = series_data["_links"]["self"]["href"] + "/episodes?specials=True"
                logger.debug(f"Trying alternative URL: {alternative_url}")

                episode_list = await self.async_fetch_json(alternative_url)

                correct_episode = find_episode(episode_list)
                if not correct_episode:
                    # One last try - maybe TV Maze does not show the episode id,
                    # e.g. a special episode (?)
                    season_only = list(filter(lambda e: e["season"] == season_id, episode_list))
                    if not season_only:
                        msg = f"TV show {series_data.get('name')} found, BUT " \
                              f"there are NO episodes in requested season: {season_id=}"
                        raise MetadataQueryError(msg)
                    season_only.sort(key=lambda e: e["airdate"])
                    logger.info(f"{len(season_only)} {episode_id=}")
                    episode_list = season_only
                    if len(season_only) >= episode_id:
                        # Yay! We should have a match. Just grab the episode by index
                        # (assuming the 'air date' ordering is valid).
                        correct_episode = season_only[episode_id - 1]

        if not correct_episode:
            episodes = [f"S{e.get('season')}E{e.get('number')}" for e in episode_list]
            msg = f"TV show {series_data.get('name')} found, BUT correct " \
                  f"episode {season_id=}, {episode_id=} can't be found in {episodes}"
            raise MetadataQueryError(msg)
        return series_data, correct_episode

    async def query(self, title: str, season_id: int, episode_id: int) -> TvShowMetadata:
        if override_title := self.search_overrides.get(title.lower()):
            title = override_title
        elif override_title := published_search_overrides.shows.get(title.lower()):
            title = override_title

        series_data, episode = await self.try_harder(
            search_term=title,
            validation_func=self._match_tv_show,
            validation_callback_args=(season_id, episode_id)
        )

        # Sometimes, we get a slash; only invalid char on *NIX so replace it
        episode_title = episode.get('name').replace('/', '-')

        return TvShowMetadata(
            series_title=series_data.get('name'),
            season_id=season_id,
            episode_title=episode_title,
            episode_id=episode_id
        )


class TMDB(MovieMetadataApi):

    # Base URL for TMDB; should generally not be changed (can be overriden via config)
    url: str = "https://api.themoviedb.org/3"

    # Search path for TMDB; should generally not be changed (can be overriden via config)
    # Variables replaced at runtime:
    #  * "key": the TMDB API key specified above
    #  * "title": the movie name query, extracted from the source filename
    path: str = "search/movie?api_key={key}&query={title}"

    # Don't load more than this amount of pages - could get pretty crazy.
    max_pages = 5

    async def async_fetch_json(self, url, retry=0, max_retries=4):
        """
        Override for TMDB in case there is more than 1 page of results.
        Very generic search terms can produce A LOT of results,
        but our target year might still be somewhere in there...
        """
        result = await super().async_fetch_json(url, retry, max_retries)
        total_pages = result.get("total_pages", 0)
        if total_pages <= 1 or not result.get("results"):
            return result

        next_page = 2
        while next_page <= (self.max_pages if total_pages >= self.max_pages else total_pages):
            next_page_data = await super().async_fetch_json(url + f"&page={next_page}")
            next_page += 1
            if next_results := next_page_data.get("results"):
                result.get("results").extend(next_results)

        return result

    def __init__(self, provider_config: MetadataProviderApi = None, search_overrides: Dict[str, str] = None) -> None:
        super().__init__(provider_config, search_overrides)
        self.path = self.path.format(key=self.key, title='{title}')

    def clean_search_term(self, string, overrides: Dict[str, str] = None):
        # "Sanitize" input name...

        # Remove the first "The" from the title when searching to avoid weird conflicts
        search_movie_title = re.sub("[Tt]he\+", "", string, 1)
        search_movie_title = search_movie_title.replace("'", "")
        # Apply overrides
        if overrides and (search_movie_title in overrides):
            new_name = overrides[search_movie_title]
            logger.debug(f"Overriding search title: '{search_movie_title}' -> '{new_name}'")
            search_movie_title = new_name

        return search_movie_title

    @staticmethod
    def _parse_release_year(movie_data: dict):
        try:
            return int(movie_data.get('release_date', '0000-00-00').split('-')[0])
        except (TypeError, ValueError):
            return 0  # No release year.

    @validation
    async def _match_movie(self, movie_data: dict, search_term, search_year: int = None):
        # List all movies and find the one with matching release year (+- 1 year)
        result_list = movie_data.get('results')

        if not result_list:
            raise MetadataQueryError(f"'{search_term}': Results list is empty.")

        new_result_list = result_list
        if search_year:
            new_result_list = list(
                filter(
                    lambda res: abs(self._parse_release_year(res) - search_year) < 2, result_list
                )
            )
        elif len(new_result_list) > 2:
            new_result_list = [item for item in result_list if item.get("popularity", 100) > 10]
            if len(new_result_list) > 2:
                raise MetadataQueryError(
                    f"{search_term}: too many results ({len(result_list)}), we cant' be sure"
                )

        if not new_result_list:
            raise MetadataQueryError(
                f"Movie search produced results, BUT the requested {search_year=} not found in: "
                f"{['{title}/{release_date}'.format(**mov) for mov in result_list]}"
            )
        probable_result = new_result_list[0]

        result_movie_title = probable_result.get('title')
        result_original_movie_title = probable_result.get('original_title')
        result_movie_year = self._parse_release_year(probable_result)

        # Triple check: flimsy, but better than nothing...
        # Look for at least a single matching word in the result title(s).
        search_terms = split_and_lower(search_term, alphanum_only=True)
        actual_terms = split_and_lower(result_original_movie_title, alphanum_only=True)
        actual_terms = actual_terms + split_and_lower(result_movie_title, alphanum_only=True)
        if not any([t in actual_terms for t in search_terms]):
            raise MetadataQueryError(
                f"'{search_term}': result '{result_movie_title}' probably a nonsense."
            )

        return result_movie_title, result_movie_year

    async def query(self, title: str, search_year: int = None) -> Optional[MovieMetadata]:
        if override_title := self.search_overrides.get(title.lower()):
            title = override_title
        elif override_title := published_search_overrides.movies.get(title.lower()):
            title = override_title

        if not self.key:
            raise MetadataQueryError(f"{self.__class__.__name__}: key required.")

        result_movie_title, result_movie_year = await self.try_harder(
            search_term=title,
            validation_func=self._match_movie,
            validation_callback_args=(search_year,)
        )
        return MovieMetadata(title=result_movie_title, year=result_movie_year)


class MetadataProvider(Enum):
    """List of all available (implemented) metadata providers."""
    TV_MAZE = "tvmaze"
    TMDB = "tmdb"

    @property
    def clazz(self):
        return {
            MetadataProvider.TV_MAZE.value: TvMaze,
            MetadataProvider.TMDB.value: TMDB,
        }.get(self.value)
