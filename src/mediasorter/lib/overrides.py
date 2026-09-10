import aiohttp
import yaml
from loguru import logger
from pydantic import BaseModel


class SearchOverrides(BaseModel):
    movies: dict[str, str]
    shows: dict[str, str]


async def read_search_overrides() -> SearchOverrides:

    url = "https://raw.githubusercontent.com/xyzjonas/mediasorter/main/mediasorter.search.overrides.yml"
    try:
        logger.debug(f"Reading search overrides file: {url}")
        async with (
            aiohttp.ClientSession(timeout=5) as session,
            session.get(url) as response,
        ):
            response.raise_for_status()  # Raised errors don't get cached.
            text = await response.text()
            data = yaml.load(text, yaml.SafeLoader)
            return SearchOverrides(**data)
    except Exception as exc:  # noqa: BLE001 - fall back to empty overrides on any failure
        logger.error(f"Can't read public search overrides file: {exc}")
        return SearchOverrides(movies={}, shows={})
