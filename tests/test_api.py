import pytest

from mediasorter import MovieMetadata, TvShowMetadata, whats_this
from mediasorter.lib.models import MediaType


@pytest.mark.asyncio
async def test_whats_this_real_show(real_config):
    result = await whats_this("S.W.A.T.2017.S06E11.HDTV.x264-PHOENiX.avi")
    assert isinstance(result, TvShowMetadata)
    assert result.type == MediaType.TV_SHOW
    assert result.season_id == 6
    assert result.episode_id == 11
    assert result.series_title == "S.W.A.T."
    assert len(result.episode_summary) > 1


@pytest.mark.asyncio
async def test_whats_this_real_movie(real_config):
    result = await whats_this(
        "The.Wedding.Veil.Journey.2023.1080p.PCOK.WEBRip.1400MB.DD5.1.x264-GalaxyRG.mkv"
    )
    assert isinstance(result, MovieMetadata)
    assert result.type == MediaType.MOVIE
    assert result.title == "The Wedding Veil Journey"
    assert result.year == 2023
    assert len(result.summary) > 1
