import asyncio
import html
import logging
import os
import re
from collections.abc import Callable
from functools import partial
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
import yaml
from typer.testing import CliRunner, Result

from mediasorter.cli import app
from mediasorter.lib.config import MediaSorterConfig, read_config
from mediasorter.lib.overrides import SearchOverrides

logger = logging.getLogger()


@pytest.fixture(scope="session", autouse=True)
def mock_overrides():
    with patch(
        "mediasorter.lib.overrides.read_search_overrides"
    ) as read_search_overrides:
        path = Path(__file__).parent / ".." / "mediasorter.search.overrides.yml"
        with open(path, "r") as local_copy:
            data = yaml.load(local_copy.read(), yaml.SafeLoader)
            read_search_overrides.return_value = SearchOverrides(**data)


@pytest.fixture(scope="session")
def default_config() -> MediaSorterConfig:
    cfg = MediaSorterConfig(cache_path=None)
    cfg.cache_path = None  # turn cache off
    return cfg


@pytest.fixture(scope="session")
def metainfo_map():
    return {
        # Cuts
        r"Extended.*": "Extended Edition",
        r"Director.*": "Directors Cut",
        r"Theatr.*": "Theatrical Cut",
        # Resolutions
        r"720[pP]": "720p",
        r"720[iI]": "720i",
        r"1080[pP]": "1080p",
        r"1080[iI]": "1080i",
        r"2160[pP]": "2160p",
        r"4[kK]": "2160p",
        # Qualities/Sources
        r"[Ww][Ee][Bb].*": "Web",
        r"BD": "BD",
        r"[Bb]lu": "BD",
        r"[Bb]lu[Rr]ay": "BD",
        r"[Bb]lu-[Rr]ay": "BD",
        r"[Dd][Vv][Dd]": "DVD",
        r".*[Rr][Ee][Mm][Uu][Xx].*": "Remux",
        # HDR
        r"DoVi": "DoVi",
        r"Vision": "DoVi",
        r"HDR.*": "HDR",
        # Audio
        r"5": "5.x",
        r"7": "7.x",
        r"2": "2.x",
        r"Atmos": "Atmos",
        r"TrueHD": "TrueHD",
    }


@pytest.fixture(scope="session")
def real_config(metainfo_map) -> MediaSorterConfig:
    try:
        cfg = read_config()
        cfg.cache_path = None  # turn cache off
        cfg.metainfo_map = metainfo_map  # override metainfo map
        return cfg
    except RuntimeError as e:
        raise pytest.skip(
            f"A real config with valid API tokens is needed for this test: {e}"
        )


@pytest.fixture(scope="session")
def test_folder() -> Path:
    return Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data")))


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
    async with aiohttp.ClientSession() as session, session.get(url) as result:
        document = await result.text(encoding="utf-8")
        return html.unescape(document)


def skip_media(string):
    for p in (
        r"complete",
        "WWE",
        "UFC",
        "AEW dynamite",
        r"season [0-9]",
        r"movie.pack",
        "trilogy",
        "sex",
        r"The[. ]Railway[. ]Men",
        "PrimeShots",
        "The Jetty",
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


@pytest.fixture
def cli() -> Callable[..., Result]:
    runner = CliRunner()
    return partial(runner.invoke, app)
