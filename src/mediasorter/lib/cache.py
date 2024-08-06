import os.path
from typing import Dict, Union, Optional

from loguru import logger
from pydantic import BaseModel, Field

from mediasorter.lib.models import TvShowMetadata, MovieMetadata


class Memory(BaseModel):
    items: Dict[str, Union[TvShowMetadata, MovieMetadata]] = Field(default_factory=dict)


class Cache:

    def __init__(self, cache_path: Optional[str]):
        self.path = cache_path
        if self.path and os.path.isfile(self.path):
            logger.debug(f"Loading cache from {self.path}")
            with open(self.path, "r") as file:
                contents = file.read().strip()
                if contents:
                    self.memory = Memory.parse_raw(contents)
                else:
                    logger.debug(f"Initializing empty cache at {self.path}")
                    self.memory = Memory()
            logger.debug(f"Cache recovered successfully ({len(self.memory.items)} items)")
        else:
            logger.debug(f"Initializing empty cache at {self.path}")
            self.memory = Memory()

    @property
    def is_disabled(self):
        return self.path is None

    def __del__(self):
        if getattr(self, "memory", None):
            self.write()

    @staticmethod
    def __construct_unique_key(*args, **kwargs) -> Optional[str]:
        res = []
        for arg in args:
            if arg is None:
                continue

            if not isinstance(arg, str) and not isinstance(arg, int):
                return None

            res.append(str(arg))

        for key, val in kwargs:
            if val is None:
                continue

            if not isinstance(key, str) and not isinstance(key, int):
                return None

            if not isinstance(val, str) and not isinstance(val, int):
                return None

            res.append(f"{key}:{val}")

        return ",".join(res)

    def insert(self, *args, result: Union[TvShowMetadata, MovieMetadata] = None, **kwargs):
        if self.is_disabled:
            return

        unique_key = self.__construct_unique_key(*args, **kwargs)
        if not unique_key:
            logger.debug(f"Can't serialize into a unique key! {args=}, {kwargs=}")
            return

        self.memory.items[unique_key] = result

    def get(self, *args, **kwargs) -> Optional[Union[TvShowMetadata, MovieMetadata]]:
        if self.is_disabled:
            return

        unique_key = self.__construct_unique_key(*args, **kwargs)
        if not unique_key:
            logger.debug(f"Can't serialize into a unique key! {args=}, {kwargs=}")
            return

        hit = self.memory.items.get(unique_key)
        if hit:
            logger.debug(f"cache hit: {args}, {kwargs} => {hit}")

        return hit

    def write(self):
        if self.is_disabled:
            return

        logger.debug(f"Storing current cache ({len(self.memory.items)} items) to {self.path}")
        with open(self.path, "w") as file:
            file.write(self.memory.json())
        logger.debug(f"Cache saved successfully.")
