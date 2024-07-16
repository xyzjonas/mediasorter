import contextlib

import pytest

from mediasorter.lib.sort import MediaSorter, MediaSorterError


@pytest.fixture(scope="function")
def media_sorter(real_config) -> MediaSorter:
    """*TMDB requires an API key, 'real' config needs to be used for these tests."""
    return MediaSorter(real_config)


@pytest.mark.asyncio
async def test_scan_movies(media_sorter, movies_dir, movies):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(movies_dir, media_type="movie")
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == len(movies)


@pytest.mark.asyncio
async def test_scan_movies_neg(media_sorter, movies_dir, movies):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(movies_dir, media_type="tv")
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == 0


@pytest.mark.asyncio
async def test_scan_tv_shows(media_sorter, shows_dir, shows):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(shows_dir, media_type="tv")
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == len(shows)


@pytest.mark.asyncio
async def test_scan_tv_shows_neg(media_sorter, shows_dir, shows):
    """Test that scan picks up all media files in a directory."""
    sort_operations = await media_sorter.scan(shows_dir, media_type="movie")
    sort_operations = [so for so in sort_operations if not so.is_error]
    assert len(sort_operations) == 0


def test_suggest_movie(media_sorter, movies):
    """Test a single movie media file."""
    assert media_sorter.suggest_movie(movies[0])


def test_suggest_show(media_sorter, shows):
    """Test a single TV show media file."""
    assert media_sorter.suggest_tv_show(shows[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("locals_key, type_, raises", [
    ("movies", "movie", contextlib.nullcontext()),
    ("movies", "tv", pytest.raises(MediaSorterError)),
    ("shows", "tv", contextlib.nullcontext()),
    ("shows", "movie", pytest.raises(MediaSorterError)),
    ("movies", "auto", contextlib.nullcontext()),
    ("shows", "auto", contextlib.nullcontext())
])
async def test_suggest(media_sorter, movies, shows, locals_key, type_, raises):
    """Test the sorter with 'test' data."""
    for media_file in locals().get(locals_key):
        with raises:
            result = await media_sorter.suggest(media_file, media_type=type_)
            result.raise_error()


@pytest.mark.parametrize("movie, md", [
    ("Detective Knight Independence 1080p DVD HDRip 5 mkv", ['1080p', 'DVD', 'HDR', '5.x'])
])
@pytest.mark.asyncio
async def test_suggest_metadata(media_sorter, movie, md, real_config):
    _, name_without_md = await media_sorter.suggest_movie(movie)

    config_md = real_config.copy()
    config_md.parameters.movie.allow_metadata_tagging = True
    _, name_with_md = await media_sorter.suggest_movie(movie)

    assert name_with_md == name_without_md + f" - [{' '.join(md)}]"


@pytest.mark.asyncio
async def test_suggest_trending_shows_from_torrent(media_sorter, trending_show):
    """Test the sorter with real 'trending' data."""
    directory, file = await media_sorter.suggest_tv_show(trending_show)
    assert directory
    assert file


@pytest.mark.asyncio
async def test_suggest_trending_movies_from_torrent(media_sorter, trending_movie):
    """Test the sorter on real 'trending' data."""
    assert await media_sorter.suggest_movie(trending_movie)
