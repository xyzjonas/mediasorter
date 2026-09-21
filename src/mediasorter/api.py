from mediasorter.lib.config import MetadataProviderApi, read_config
from mediasorter.lib.metadata import (
    MetadataProviderConfigError,
    MetadataQueryError,
    movie_metadata_providers,
    tv_metadata_providers,
)
from mediasorter.lib.models import MovieMetadata, TvShowMetadata
from mediasorter.lib.parse import (
    ParsingError,
    parse_movie_name,
    parse_season_and_episode,
)


async def whats_this(
    filename_or_path: str,
    metadata_providers_map: dict[str, MetadataProviderApi] | None = None,
) -> MovieMetadata | TvShowMetadata:
    """
    What's this? Parse, recognize and fetch metadata based on a string input (e.g. filename)

    :param filename_or_path: plain string (filename) or relative/absolute path (base name will be extracted).
    :param metadata_providers_map: override metadata providers (clients) configuration, if None default config will be used.
    :return: Metadata object
    """
    global_config = read_config()
    if not metadata_providers_map:
        metadata_providers_map = {
            provider.name: provider for provider in global_config.api
        }
    try:
        title, season, episode = parse_season_and_episode(filename_or_path)
        for key, provider in tv_metadata_providers.mapping.items():
            if key in metadata_providers_map:
                config = metadata_providers_map[key]
                return await provider(config=config).query(title, season, episode)
        raise MetadataProviderConfigError(
            f"Missing metadata provider configuration, available: {tv_metadata_providers.mapping.keys()}, "
            f"found in configuration: {metadata_providers_map.keys()}"
        )
    except ParsingError:
        pass

    title, year, _ = parse_movie_name(filename_or_path)
    for key, provider in movie_metadata_providers.mapping.items():
        if key in metadata_providers_map:
            config = metadata_providers_map[key]
            return await provider(config=config).query(title, year)
        provider.query()

    raise MetadataQueryError(
        f"Search yielded no results: '{filename_or_path}'. "
        f"Search term does not match any tv show nor movie."
    )
