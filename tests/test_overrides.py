from mediasorter.lib.overrides import SearchOverrides


def test_overrides_casefold() -> None:
    overrides = SearchOverrides(movies={"Foo": "BAR"}, shows={"bar": "fOO"})
    assert overrides.movies == {"foo": "bar"}
    assert overrides.shows == {"bar": "foo"}


def test_flat() -> None:
    overrides = SearchOverrides(movies={"Foo": "BAR"}, shows={"bar": "fOO"})
    assert overrides.flat_overrides == {"foo": "bar", "bar": "foo"}
