import asyncio
import html
import logging
import os
import re

import aiohttp
import pytest

from mediasorter.lib.config import MediaSorterConfig, read_config

logger = logging.getLogger()


@pytest.fixture(scope="session")
def default_config() -> MediaSorterConfig:
    return MediaSorterConfig(cache_path=None)


@pytest.fixture(scope="session")
def real_config() -> MediaSorterConfig:
    try:
        cfg = read_config()
        cfg.cache_path = None  # turn cache off
        return cfg
    except RuntimeError as e:
        pytest.skip(f"A real config with valid API tokens is needed for this test.")


@pytest.fixture(scope="session")
def test_folder():
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__), "test_data"
    ))


@pytest.fixture(scope="session")
def shows_dir(test_folder):
    return os.path.join(test_folder, "shows")


@pytest.fixture(scope="session")
def shows(shows_dir):
    return os.listdir(shows_dir)


@pytest.fixture(scope="session")
def movies_dir(test_folder):
    return os.path.join(test_folder, "movies")


@pytest.fixture(scope="session")
def movies(movies_dir):
    return os.listdir(movies_dir)


async def fetch_html(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as result:
            document = await result.text(encoding="utf-8")
            return html.unescape(document)


def skip_media(string):
    for p in (
            r"complete", "WWE", "UFC", "AEW dynamite",
            r"season [0-9]", r"movie.pack", "trilogy", "sex",
            r"The[. ]Railway[. ]Men", "PrimeShots", "The Jetty"
    ):
        if re.search(p, string, re.IGNORECASE):
            return True
        continue


def fetch_trending_shows():
    """Grab all the currently trending torrents file names from 1337"""
    url = "https://1337x.to/trending/w/tv/"

    document = asyncio.run(fetch_html(url))
    torrents = re.findall(r'<a href="/torrent/\d+/.*>(.*)</a>', document)
    x = [f"{torr}.avi" for torr in torrents if not skip_media(torr)]
    return x


@pytest.fixture()
def trending_shows():
    return fetch_trending_shows()


def fetch_trending_movies():
    """Grab all the currently trending torrents file names from 1337"""
    url = "https://1337x.to/trending/d/movies/"

    document = asyncio.run(fetch_html(url))
    torrents = re.findall(r'<a href="/torrent/\d+/.*>(.*)</a>', document)
    x = [f"{torr}.avi" for torr in torrents if not skip_media(torr)]
    return x


def pytest_generate_tests(metafunc):

    if "trending_show" in metafunc.fixturenames:
        metafunc.parametrize("trending_show", fetch_trending_shows())

    if "trending_movie" in metafunc.fixturenames:
        metafunc.parametrize("trending_movie", fetch_trending_movies())