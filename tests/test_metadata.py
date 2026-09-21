import pytest

from mediasorter.lib.config import MetadataProviderApi
from mediasorter.lib.metadata import (
    TMDB,
    MetadataQueryError,
    MovieMetadata,
    TvMaze,
    TvShowMetadata,
)


@pytest.fixture
def tv_maze_config():
    return MetadataProviderApi(
        name="tvmaze",
        url="https://api.tvmaze.com",
        path="singlesearch/shows?q={title}&embed=episodes",
    )


@pytest.fixture
def tv_maze(tv_maze_config) -> TvMaze:
    return TvMaze(config=tv_maze_config)


@pytest.fixture
def tmdb(real_config) -> TMDB:
    api_config = {a.name: a for a in real_config.api}.get("tmdb")
    if not api_config:
        pytest.skip("TMDB API details need to be configured for this test.")
    return TMDB(config=api_config)


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms", [("nosuchtvshow", 1, 1)])
async def test_query_tv_show_not_fond(tv_maze, search_terms):
    with pytest.raises(MetadataQueryError):
        await tv_maze.query(*search_terms)


@pytest.mark.asyncio
@pytest.mark.parametrize("search_terms", [("mash", 99, 999)])
async def test_query_tv_show_no_episode(tv_maze, search_terms):
    with pytest.raises(MetadataQueryError, match=r"found, BUT there are NO episodes"):
        await tv_maze.query(*search_terms)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "search_terms, expected_out",
    [
        (
            ("mash", 5, 3),
            TvShowMetadata(
                series_title="M*A*S*H",
                season_id=5,
                episode_title="Out of Sight, Out of Mind",
                episode_id=3,
                episode_summary="<p>Hawkeye tries to help the nurses out when their stove goes out in the freezing weather and is injured when the stove blows up in his face.</p>",
            ),
        ),
        (
            ("the witcher us", 1, 4),  # language marker can get in the search terms
            TvShowMetadata(
                series_title="The Witcher",
                season_id=1,
                episode_title="Of Banquets, Bastards and Burials",
                episode_id=4,
                episode_summary="<p>Against his better judgment, Geralt accompanies Jaskier to a royal ball. Ciri wanders into an enchanted forest. Yennefer tries to protect her charges.</p>",
            ),
        ),
        (
            ("friends", 9, 19),
            TvShowMetadata(
                series_title="Friends",
                season_id=9,
                episode_title="The One With Rachel's Dream",
                episode_id=19,
                episode_summary="<p>Nervous because his daytime-drama role requires him to act as if he's deeply in love with a woman, Joey rehearses with Rachel.</p>",
            ),
        ),
        (
            ("the good doctor", 6, 10),
            TvShowMetadata(
                series_title="The Good Doctor",
                season_id=6,
                episode_title="Quiet and Loud",
                episode_id=10,
                episode_summary="<p>Shaun and Lea soon learn that their surprise pregnancy may also come with additional complications. Meanwhile, Doctors Park, Reznick and Allen treat a teen with Gardner's syndrome whose past surgical history jeopardizes the outcome of his current one.\xa0</p>",
            ),
        ),
        (
            ("s w a t", 6, 10),
            TvShowMetadata(
                series_title="S.W.A.T.",
                season_id=6,
                episode_title="Witness",
                episode_id=10,
                episode_summary="<p>The SWAT team races to locate a young boy abducted from a homeless shelter. Also, Street allows his personal history to cloud his judgement on the kidnapping case, and Hondo and Nichelle find themselves at odds over their spiritual beliefs.</p>",
            ),
        ),
        (
            # This is a tough one - a "special" episode.
            ("All Creatures Great and Small", 3, 7),
            TvShowMetadata(
                series_title="All Creatures Great and Small",
                season_id=3,
                episode_title="Merry Bloody Christmas",
                episode_id=7,
                episode_summary="<p>It's Christmas in Darrowby and everyone is trying to make the most of things while the world is at war. A young guest brings some wonder, mischief and cheer to Skeldale House while everyone waits for important news. When Mrs Pumphrey heralds the arrival of a kitten in need of some extra care at Pumphrey Manor, James has just the person to take him under their wing. Siegfried is asked to pay a visit to an injured River just before a big race and makes an important discovery which Sebright Saunders uses as leverage to get River back on the racetrack.</p>",
            ),
        ),
        (
            ("archer", 5, 12),
            TvShowMetadata(
                series_title="Archer",
                season_id=5,
                episode_title="Filibuster",
                episode_id=12,
                episode_summary="<p>Cyril becomes the new president of San Marcos, Cherlene becomes the first lady of country music, and Archer becomes a resistance fighter.</p>",
            ),
        ),
    ],
)
async def test_query_tv_show(tv_maze, search_terms, expected_out):
    assert await tv_maze.query(*search_terms) == expected_out


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "search_terms, expected_out",
    [
        (
            ("Emanuelle nera Orient Reportage Emmanuelle in Bangkok", 1976),
            MovieMetadata(
                title="Emanuelle in Bangkok",
                year=1976,
                summary="A reporter travels the world's hot spots, looking for lurid stories that usually involve her sexual participation in gaining those behind-the-scenes exclusives.",
            ),
        ),
        (
            ("Roald Dahl's Matilda the Musical", 2022),
            MovieMetadata(
                title="Roald Dahl's Matilda the Musical",
                year=2022,
                summary="An extraordinary young girl discovers her superpower and summons the remarkable courage, against all odds, to help others change their stories, whilst also taking charge of her own destiny. Standing up for what's right, she's met with miraculous results.",
            ),
        ),
        (
            ("ipersonnia", 2022),
            MovieMetadata(
                title="Hypersleep",  # English title
                year=2022,
                summary="The old and overcrowded penitentiaries are just a memory. Inmates now serve their sentence in a state of deep sleep that renders them harmless, and has drastically reduced recidivism. Until one day, a psychologist in charge of monitoring the mental state of inmates finds himself confronted with a prisoner over whom he's lost all control.",
            ),
        ),
        (
            ("Císařův pekař a pekařův císař", 1951),
            MovieMetadata(
                title="The Emperor and the Golem",  # English title
                year=1951,
                summary="The Emperor's mismanagement of his country is provoking some in his court to plot to overthrow him.  He feels successful, at least, when he discovers the legendary Golem, which he believes can protect him and even cure his imaginary illnesses but, when he disappears while on a bender, his kindly baker, who looks just like him, is mistaken for him, and begins to put things in order.  However, the conspirators, not to be outdone, determine to bring the Golem back to life to do their bidding.",
            ),
        ),
        # (
        #     ("one flew over the cuckoo nest BrRip x264 YIFY", None),
        #     MovieMetadata(
        #         title="One Flew Over the Cuckoo's Nest",
        #         year=1975
        #      )
        # ),
        # (
        #     ("the witness", 1969),
        #     MovieMetadata(
        #         title="The Witness",
        #         year=1969
        #      )
        # ),
    ],
)
async def test_query_movie(tmdb, search_terms, expected_out):
    assert await tmdb.query(*search_terms) == expected_out


# @pytest.mark.asyncio
# @pytest.mark.parametrize("search_terms", [
#     ("Stephen King's IT", 1990),  # TMDB just can't find this one...
# ])
# async def test_query_movie_neg(tmdb, search_terms):
#     with pytest.raises(MetadataQueryError):
#         await tmdb.query(*search_terms)
