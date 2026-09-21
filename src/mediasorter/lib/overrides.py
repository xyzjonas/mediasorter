# import aiohttp
# import yaml
# from loguru import logger
from pydantic import BaseModel, field_validator

# Search overrides
# Useful if you have some search term that sortfile is generating which does not work reliably.
# Use this dictionary, where the key is whatever sortfile generates, and the value is what you
# want to search instead, to override the actual search with another one.
# Add your own as needed; this list is populated by my own findings.
KNOWN_OVERRIDES = {
    "movies": {
        "ghandi": "gandhi",
    },
    "shows": {
        "s w a t": "swat",
        "Haló, Haló!": "allo allo",
    },
}


class SearchOverrides(BaseModel):
    movies: dict[str, str]
    shows: dict[str, str]

    @field_validator("movies", "shows")
    @classmethod
    def fold_case(cls, field: dict[str, str]) -> dict[str, str]:
        sanitized = {}
        for key, value in field.items():
            sanitized[key.casefold()] = value.casefold()

        return sanitized

    @property
    def flat_overrides(self) -> dict[str, str]:
        return self.movies | self.shows


def get_search_overrides() -> SearchOverrides:
    return SearchOverrides(**KNOWN_OVERRIDES)
    # url = "https://raw.githubusercontent.com/xyzjonas/mediasorter/main/mediasorter.search.overrides.yml"
    # try:
    #     logger.debug(f"Reading search overrides file: {url}")
    #     async with (
    #         aiohttp.ClientSession(timeout=5) as session,
    #         session.get(url) as response,
    #     ):
    #         response.raise_for_status()  # Raised errors don't get cached.
    #         text = await response.text()
    #         data = yaml.load(text, yaml.SafeLoader)
    #         return SearchOverrides(**data)
    # except Exception as exc:
    #     logger.error(f"Can't read public search overrides file: {exc}")
    #     return SearchOverrides(movies={}, shows={})
