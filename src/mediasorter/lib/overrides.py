from urllib import request

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
        async with aiohttp.ClientSession(timeout=5) as session:
            async with session.get(url) as response:
                response.raise_for_status()  # Raised errors don't get cached.
                text = await response.text()
                data = yaml.load(text, yaml.SafeLoader)
                return SearchOverrides(**data)
    except Exception as exc:
        logger.error(f"Can't read public search overrides file: {exc}")
        return SearchOverrides(movies={}, shows={})

        req = request.Request(url)
        with request.urlopen(req, timeout=5) as response:
            text = response.read().decode("utf-8").lower()
            data = yaml.load(text, yaml.SafeLoader)

            return SearchOverrides(**data)
    except Exception as e:
        logger.error(f"Can't read public search overrides file: {e}")
    return SearchOverrides(movies={}, shows={})
