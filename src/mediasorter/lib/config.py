import os
from typing import List, Dict, Optional, Literal, Union

import yaml
from loguru import logger
from pydantic import BaseModel, PositiveInt, ValidationError, Field

CONFIG_PATH = os.environ.get(
    "MEDIASORTER_CONFIG",
    os.path.expanduser(os.path.join("~", ".config", "mediasorter.yml"))
)


MediaType = Literal["tv", "movie", "auto"]
Action = Literal["move", "hardlink", "symlink", "copy"]


class MetadataProviderApi(BaseModel):
    name: str
    key: Optional[str]
    url: Optional[str]
    path: Optional[str]


class OperationOptions(BaseModel):
    user: Union[int, str] = "root"
    group: Union[int, str] = "media"
    chown: bool = False
    dir_mode: str = '0o644'
    file_mode: Optional[str]
    overwrite: bool = False
    infofile: bool = False
    shasum: bool = False


class ScanConfig(BaseModel):
    """
    Specify an "input/output" combo for different directories
    """
    src_path: str  # source path (duh...)
    media_type: MediaType = "auto"  # force only a specific media type
    action: Action = "copy"  # select action type
    tv_shows_output: Optional[str]  # where to put recognized TV shows
    movies_output: Optional[str]  # where to put recognized movies
    options: Optional[OperationOptions] = None  # options for the sorting operation itself


class BaseParams(BaseModel):
    min_split_length: PositiveInt = 3
    suffix_the: bool = False
    file_format: str


class MovieParams(BaseParams):
    subdir: bool = True  # sort all files related to a single movie to a common subdir
    file_format: str = "{title} ({year})"
    dir_format: str = file_format
    allow_metadata_tagging: bool = False


class TvShowParams(BaseParams):
    dir_format: str = "{series_title}/Season {season_id}"
    file_format: str = '{series_title} - S{season_id:02d}E{episode_id:02d} - {episode_title}'


class Parameters(BaseModel):
    valid_extensions: List[str] = [".avi", ".mkv", ".mp4"]
    split_characters: List[str] = [" ", ".", "_"]

    tv: TvShowParams = TvShowParams()
    movie: MovieParams = MovieParams()


class Logging(BaseModel):
    logfile: str
    loglevel: str


class MediaSorterConfig(BaseModel):
    # Configure different metadata provider APIs (API keys, override URLs,...).
    # Must correspond to an existing key in the MetadataProvider enum.
    api: List[MetadataProviderApi] = []

    # Configure multiple directories to be scanned
    # without the need to specify using command line interface.
    scan_sources: List[ScanConfig] = []

    search_overrides: Dict[str, str] = {}

    parameters: Parameters = Parameters()

    options: OperationOptions = OperationOptions()

    metainfo_map: Dict[str, str] = {}

    loging: Optional[Logging]

    maximum_concurrent_requests: int = Field(gt=0, default=100)

    cache_path: Optional[str] = "/tmp/mediasorter.cache"


class ConfigurationError(Exception):
    pass


def read_config(config_file: Optional[str] = None) -> MediaSorterConfig:
    config_file = config_file if config_file else CONFIG_PATH
    try:
        logger.info(f'reading configuration file: {config_file}')
        with open(config_file, 'r') as cfgfile:
            o_config = yaml.load(cfgfile, Loader=yaml.SafeLoader)

        return MediaSorterConfig(**o_config['mediasorter'])
    except FileNotFoundError:
        raise ConfigurationError(
            f"Can't load configuration '{config_file}', file not found"
        )
    except (KeyError, ValidationError):
        raise ConfigurationError(
            f"Can't load configuration '{config_file}', invalid config keys."
        )
    except Exception as e:
        raise ConfigurationError(
            f"Can't load configuration from '{config_file}', unexpected error {type(e)} "
        )


default_config = MediaSorterConfig(
    api=[
        MetadataProviderApi(
            name="tvmaze",
            url="http://api.tvmaze.com",
            path="singlesearch/shows?q={title}&embed=episodes",
        ),
        MetadataProviderApi(
            name="tmdb",
            url="https://api.themoviedb.org/3",
            key="",
            path="search/movie?api_key={key}&query={title}",
        ),
    ],
    parameters=Parameters(
        valid_extensions=[".avi", ".mkv", ".mp4"],
        split_characters=[" ", ".", "_"],
        tv=TvShowParams(
            # Available values are:
            # - series_title
            # - episode_title
            # - season_id
            # - episode_id
            dir_format="{series_title}/Season {season_id:02d}",
            file_format="{series_title} S{season_id:02d}E{episode_id:02d} - {episode_title}",
            min_split_length=3,
            suffix_the=False,
        ),
        movie=MovieParams(
            # Available values are:
            # - title
            # - year
            dir_format="{title} {year}",
            file_format="{title} {year}",
            min_split_length=1,
            suffix_the=False,
            subdir=True,
        ),
    ),
    logging=Logging(
        file=False,
        loglevel="WARNING",
        logfile="/var/log/mediasorter.log",
    )
)
#
#
# config: MediaSorterConfig = read_config(config_file=CONFIG_PATH)
