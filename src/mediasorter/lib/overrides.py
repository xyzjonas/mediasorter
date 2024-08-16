import os
from urllib import request

import yaml
from pydantic import BaseModel
from loguru import logger


class SearchOverrides(BaseModel):
    movies: dict[str, str]
    shows: dict[str, str]


def read_search_overrides() -> SearchOverrides:
    if os.path.isfile("./mediasorter.search.overrides.yml"):
        # logger.info("Opting for the local copy of search.overrides.yml")
        with open("./mediasorter.search.overrides.yml", "r") as local_copy:
            data = yaml.load(local_copy.read(), yaml.SafeLoader)
            return SearchOverrides(**data)

    url = 'https://raw.githubusercontent.com/xyzjonas/mediasorter/main/mediasorter.search.overrides.yml'
    try:
        req = request.Request(url)
        with request.urlopen(req, timeout=5) as response:
            text = response.read().decode("utf-8").lower()
            data = yaml.load(text, yaml.SafeLoader)

            return SearchOverrides(**data)
    except Exception as e:
        logger.error(f'Can\'t read public search overrides file: {e}')
    return SearchOverrides(movies={}, shows={})
