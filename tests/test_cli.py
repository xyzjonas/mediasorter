import tomllib
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def with_real_mediasorter(real_config):
    with mock.patch("mediasorter.cli._get_config", return_value=real_config):
        yield


def test_help(cli):
    assert "Usage:" in cli(["--help"]).output
    assert cli(["--help"]).exit_code == 0


def test_version(cli):
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text("utf-8"))
    version = pyproject["project"]["version"]

    result = cli(["version"])
    assert f"{version}\n" == result.output
    assert result.exit_code == 0


def test_sort_happy_path(cli, test_folder, tmp_path, with_real_mediasorter):
    source_dir = test_folder / "one_movie_e2e"

    result = cli(["sort", str(source_dir), str(tmp_path), str(tmp_path)], input="y")
    if result.exception:
        raise result.exception

    assert "OK: 1" in result.output
    assert "Transfusion 2023.mp4" in result.output
    assert result.exit_code == 0
