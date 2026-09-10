def test_help(cli):
    assert "Usage:" in cli(["--help"]).output
    assert cli(["--help"]).exit_code == 0


def test_version(cli):
    from mediasorter import __version__

    result = cli(["version"])
    assert __version__ in result.output
    assert result.exit_code == 0


def test_sort_happy_path(cli, test_folder, tmp_path):
    source_dir = test_folder / "one_movie_e2e"

    result = cli(["sort", str(source_dir), str(tmp_path), str(tmp_path)], input="y")
    if result.exception:
        raise result.exception

    assert "OK: 1" in result.output
    assert "Transfusion 2023.mp4" in result.output
    assert result.exit_code == 0
