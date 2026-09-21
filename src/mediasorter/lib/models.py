import enum

from pydantic import BaseModel


class MediaType(enum.Enum):
    TV_SHOW = "tv-show"
    MOVIE = "movie"


class BaseMetadata(BaseModel):
    type: MediaType


class TvShowMetadata(BaseModel):
    type: MediaType = MediaType.TV_SHOW
    series_title: str
    season_id: int
    episode_title: str
    episode_id: int
    episode_summary: str | None = None  # can indeed be null


class MovieMetadata(BaseModel):
    type: MediaType = MediaType.MOVIE
    title: str
    year: int
    summary: str
