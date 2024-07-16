from pydantic import BaseModel


class TvShowMetadata(BaseModel):
    series_title: str
    season_id: int
    episode_title: str
    episode_id: int


class MovieMetadata(BaseModel):
    title: str
    year: int
