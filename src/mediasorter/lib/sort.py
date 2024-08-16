import asyncio
import os
import subprocess
from itertools import chain
from typing import Optional, List, Tuple, Any, Union

from loguru import logger
from pydantic import BaseModel

from mediasorter.lib.execute import ExecutionError, Executable
from .cache import Cache
from .config import (
    OperationOptions,
    MediaType,
    Action, MediaSorterConfig,
    read_config
)
from .metadata import (
    TvShowMetadata,
    MovieMetadata,
    MetadataQueryError,
    tv_metadata_providers, movie_metadata_providers,
)
from .parse import (
    parse_season_and_episode,
    parse_movie_name,
    fix_leading_the,
    ParsingError
)


class MediaSorterError(Exception):
    pass


class CantSortError(MediaSorterError):
    pass


class Operation(BaseModel):
    input_path: str
    output_path: Optional[str]
    action: Action = "copy"
    type: MediaType = "auto"
    exception: Optional[Any]
    options: Optional[OperationOptions]

    @property
    def is_error(self):
        return self.exception is not None

    @property
    def handler(self):
        return OperationHandler(self)

    def raise_error(self):
        if self.exception:
            raise self.exception
        return self


class OperationHandler:

    op: Operation
    options: OperationOptions

    def __init__(self, operation) -> None:
        self.op = operation

    @property
    def options(self):
        return self.op.options

    def pre_commit(self):
        if not self.op.output_path:
            self.op.exception = CantSortError(f"Destination path missing.")

        if os.path.exists(self.op.output_path):
            logger.info(f"File exists '{self.op.output_path}'")
            if self.op.options.overwrite:
                logger.info(f"Removing for overwrite.")
                os.remove(self.op.output_path)
            else:
                msg = f"Destination file '{self.op.output_path}' exists, overwrite not allowed."
                logger.warning(msg)
                self.op.exception = CantSortError(msg)

    async def commit(self):
        self.pre_commit()
        if self.op.is_error:
            return

        try:
            # fail fast if user/group doesn't exist
            if self.options.chown:
                _get_uid_and_gid(self.options.user, self.options.group)

            Executable.from_action_type(self.op.action) \
                      .commit(self.op.input_path, self.op.output_path)

            uid, gid = None, None
            if self.options.chown:
                uid, gid = _get_uid_and_gid(self.options.user, self.options.group)
                logger.info(
                    f"Correcting ownership and permissions: "
                    f"{uid=}, {gid=}, mode={self.options.file_mode}"
                )
                parent_dir = os.path.dirname(self.op.output_path)
                os.chown(parent_dir, uid, gid)
                os.chown(self.op.output_path, uid, gid)
                os.chmod(self.op.output_path, int(self.options.file_mode, 8))
                if self.options.dir_mode:
                    logger.info(f"Changing parent dire mode: {self.options.dir_mode=}")
                    os.chmod(parent_dir, int(self.options.dir_mode, 8))

            # Create the info file.
            if self.options.infofile:
                info_file_name = f"{self.op.output_path}.txt"
                logger.info(f"Creating info file: .../{os.path.basename(info_file_name)}")
                info_file_contents = [
                    "Source filename:  {}".format(os.path.basename(self.op.output_path)),
                    "Source directory: {}".format(os.path.dirname(self.op.output_path))
                ]
                with open(info_file_name, 'w') as fh:
                    fh.write('\n'.join(info_file_contents))
                    fh.write('\n')
                if self.options.chown:
                    os.chown(info_file_name, uid, gid)
                    os.chmod(info_file_name, int(self.options.file_mode, 8))

            # Create sha256sum file
            if self.options.shasum:
                shasum_name = '{}.sha256sum'.format(self.op.output_path)
                logger.debug(f"Generating shasum file: .../'{os.path.basename(shasum_name)}'.")
                shasum_cmdout = subprocess.run(
                    ['sha256sum', '-b', f'{self.op.output_path}'],
                    capture_output=True, encoding='utf8'
                )
                if shasum_cmdout.returncode != 0 or not shasum_cmdout.stdout:
                    msg = f"SHASUM checksum generation failed, " \
                          f"out={shasum_cmdout.stdout} err={shasum_cmdout.stderr}"
                    logger.error(msg)
                    self.op.exception = MediaSorterError(msg)
                    return

                shasum_data = shasum_cmdout.stdout.strip()
                logger.info(
                    f".../{os.path.basename(self.op.output_path)}: SHA generated {shasum_data}.")
                with open(shasum_name, 'w') as fh:
                    fh.write(shasum_data)
                    fh.write('\n')
                if self.options.chown:
                    logger.debug(f"{os.path.basename(shasum_name)}: changing owner.")
                    os.chown(shasum_name, uid, gid)
                    os.chmod(shasum_name, int(self.options.file_mode, 8))
        except (ExecutionError, KeyError) as e:
            if "getgrnam" in str(e):
                msg = f"Group doesn't exist: {str(e).replace('getgrnam(): ', '')}"
                e = ExecutionError(msg)

            logger.error(f"Commit error: {e}")
            self.op.exception = e
            return

        except Exception as e:
            logger.exception(e)
            self.op.exception = e


def _get_uid_and_gid(
        user_name: Union[str, int] = None,
        group_name: Union[str, int] =None
) -> (int, int):
    # expect ImportError on Windows
    import grp
    import pwd

    if isinstance(user_name, str):
        uid = pwd.getpwnam(user_name)[2]
    elif isinstance(user_name, int):
        uid = user_name
    else:
        uid = os.getuid()

    if isinstance(group_name, str):
        gid = grp.getgrnam(group_name)[2]
    elif isinstance(group_name, int):
        gid = group_name
    else:
        gid = os.getgid()

    return uid, gid


class MediaSorter:

    # config: MediaSorterConfig

    def __init__(self, config: MediaSorterConfig):
        self.config = config
        self.cache = Cache(config.cache_path)

    @classmethod
    def from_config(cls, config_path: str):
        return cls(read_config(config_path))

    async def scan_all(self) -> List[Operation]:
        """Scan all preconfigured scan sources."""
        scan_ops = [self.scan(**scan.__dict__) for scan in self.config.scan_sources]
        result_lists = await asyncio.gather(*scan_ops)
        return list(chain(*result_lists))

    async def scan(
            self,
            src_path: str,
            media_type: MediaType,
            tv_shows_output: str = None,
            movies_output: str = None,
            action: Action = "copy",
            options: OperationOptions = OperationOptions()
    ) -> List[Operation]:
        """Scan a single source path (file or directory)."""
        operations = []

        if os.path.isdir(src_path):
            tasks = []
            logger.debug(f"Scanning {src_path} [{media_type}]")
            for filename in sorted(os.listdir(src_path)):
                child_path = os.path.join(src_path, filename)
                tasks.append(
                    self.scan(
                        child_path, media_type, tv_shows_output,
                        movies_output, action, options
                    )
                )

            results = await asyncio.gather(*tasks)
            for res in results:
                operations.extend(res)
        elif not os.path.exists(src_path):
            logger.error(f"{src_path}: path does not exist!")
            op = Operation(input_path=src_path)
            op.exception = FileNotFoundError(f"File does not exist: '{src_path}'")
            if options:
                op.options = options
            operations.append(op)
        else:
            if op := await self.suggest(src_path, media_type=media_type, action=action):
                if op.is_error:
                    pass
                elif op.type == "tv" and tv_shows_output:
                    op.output_path = os.path.join(tv_shows_output, op.output_path)
                elif op.type == "movie" and movies_output:
                    op.output_path = os.path.join(movies_output, op.output_path)
                if options:
                    op.options = options
                operations.append(op)

        return [op for op in operations if op]

    async def find_tvshow(self, *args) -> TvShowMetadata:
        """Make an external query to find a TV-show/movie metadata."""
        if hit := self.cache.get(*args):
            return hit

        exceptions = []
        for api in self.config.api:
            try:
                provider_cls = tv_metadata_providers.get(api.name)
                if provider_cls:
                    provider = provider_cls(api, self.config.search_overrides)
                    result = await provider.query(*args)
                    self.cache.insert(*args, result=result)
                    return result
            except MetadataQueryError as e:
                logger.error(f"{api.name} query failed.")
                exceptions.append(e)

        raise MediaSorterError(
            f"TV: none of {[a.name for a in self.config.api]} API queries was successful",
            exceptions
        )

    async def find_movie(self, *args) -> MovieMetadata:
        """Make an external query to find a TV-show/movie metadata."""
        if hit := self.cache.get(*args):
            return hit

        exceptions = []
        for api in self.config.api:
            try:
                # TMDB()
                provider_cls = movie_metadata_providers.get(api.name)
                if provider_cls:
                    provider = provider_cls(api, self.config.search_overrides)
                    result = await provider.query(*args)
                    self.cache.insert(*args, result=result)
                    return result
            except MetadataQueryError as e:
                logger.error(f"{api.name} query failed.")
                exceptions.append(e)

        raise MediaSorterError(
            f"MOVIE: none of {[a.name for a in self.config.api]} API queries was successful",
            exceptions
        )

    async def suggest_tv_show(self, src_path: str):
        try:
            parsed_tv_show = parse_season_and_episode(
                src_path,
                self.config.parameters.split_characters,
                self.config.parameters.tv.min_split_length,
                force=False,
            )
        except ParsingError:
            logger.debug(f"Parsing failed: {src_path}, trying force=True.")
            parsed_tv_show = parse_season_and_episode(
                src_path,
                self.config.parameters.split_characters,
                self.config.parameters.tv.min_split_length,
                force=True  # Try everything!
            )

        if parsed_tv_show:
            name, series, episode = parsed_tv_show

            logger.debug(f"TV show recognized: series='{name}' S={series} E={episode}")
            result = await self.find_tvshow(name, series, episode)

            if self.config.parameters.tv.suffix_the:
                result.series_title = fix_leading_the(result.series_title)

            # Build the final path+filename
            season_dir = self.config.parameters.tv.dir_format.format(**result.__dict__)
            filename = self.config.parameters.tv.file_format.format(**result.__dict__)
            filename = " ".join(filename.split())

            return season_dir, filename

    async def suggest_movie(self, src_path: str) -> Tuple[Optional[str], str]:
        """
        Suggest the title of the movie, as well as its year based on an external metadata API.

        :param src_path: str: Specify the path to the file that is going to be moved
        :return: A final, formatted movie file name suggestion (dir and filename)
        """
        try:
            # Even if movie type is forced, try to find the season/episode numbers
            # to disqualify the media file before any network requests.
            if parse_season_and_episode(
                    src_path,
                    self.config.parameters.split_characters,
                    self.config.parameters.movie.min_split_length,
                    force=False  # We DON'T want to parse a TV show at all costs.
            ):
                raise MediaSorterError(f"This appears to be a TV show: {src_path}")
        except ParsingError:
            pass

        movie, year, metainfo = parse_movie_name(
            src_path,
            self.config.parameters.split_characters,
            self.config.parameters.movie.min_split_length,
            self.config.metainfo_map
        )
        logger.debug(f"Parsed {os.path.basename(src_path)}, {movie=} {year=}")
        result = await self.find_movie(movie, year)

        # for title in self.config.parameters.movie.name_overrides:
        #     if title == result.title:
        #         result.title = self.config.parameters.movie.name_overrides[title]
        #         break

        filename = self.config.parameters.movie.file_format.format(**result.__dict__)

        # Sort movie files in a directory.
        if self.config.parameters.movie.subdir:
            subdir = self.config.parameters.movie.dir_format.format(**result.__dict__)
        else:
            subdir = None

        if self.config.parameters.movie.allow_metadata_tagging and metainfo:
            # MUST be "space", "hyphen", "space"
            # https://jellyfin.org/docs/general/server/media/movies/#multiple-versions-of-a-movie
            filename = f"{filename} - [{' '.join(metainfo)}]"

        return subdir, filename.strip()

    async def suggest(
            self, src_path: str, media_type: MediaType = "auto", action: Action = "copy"
    ) -> Optional[Operation]:

        extension = os.path.splitext(src_path)[-1]

        logger.info(f">>> Parsing {src_path} [{media_type}]")

        if not extension:
            logger.warning(f"{os.path.basename(src_path)}: files without extension not allowed.")
            return None
        elif extension and extension not in self.config.parameters.valid_extensions:
            logger.warning(
                f"{os.path.basename(src_path)}: extension '{extension}' not allowed, "
                f"not in {self.config.parameters.valid_extensions}."
            )
            return None

        # First try to parse a TV show (series and episodes numbers)
        directory, filename = None, None
        operation = Operation(
            input_path=src_path,
            type="tv",
            action=action,
            options=self.config.options
        )
        if media_type in ["auto", "tv"]:
            try:
                directory, filename = await self.suggest_tv_show(src_path)
            except ParsingError as e:
                msg = f"{os.path.basename(src_path)} can't be parsed into a TV show: {e}."
                if media_type == "tv":
                    logger.error(msg)
                    operation.exception = MediaSorterError(msg)
                    return operation
                logger.debug(msg)
            except (MediaSorterError, MetadataQueryError) as e:
                operation.exception = e
                return operation

        if not filename:
            # Not a TV show? Must be a movie then...
            operation.type = "movie"
            try:
                directory, filename = await self.suggest_movie(src_path)
            except (MediaSorterError, ParsingError) as e:
                msg = f"{os.path.basename(src_path)} can't be parsed into a movie title: {e}."
                logger.error(msg)
                operation.exception = MediaSorterError(msg)
                return operation
            except (MediaSorterError, MetadataQueryError) as e:
                operation.exception = e
                return operation

        # Build the final path+filename
        if directory:
            dst_path = os.path.join(directory, filename)
        else:
            dst_path = os.path.join(filename)

        # Get rid of forbidden characters (I'm looking at you, Windows!)
        for illegal_char in (":", "#"):
            dst_path = dst_path.replace(illegal_char, "")

        dst_path += extension
        logger.debug(f"Suggested output path: {dst_path}")
        operation.output_path = dst_path

        return operation

    @staticmethod
    async def commit_all(operations: List[Operation]) -> List[Operation]:
        for sort_op in operations:
            await sort_op.handler.commit()
        return operations
