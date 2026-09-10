mediasorter *ARGS:
  uv run mediasorter {{ARGS}}

test:
  uv run pytest

tox:
  uv run tox -p all

format:
  uv run ruff format .

lint:
  uv run ruff check

publish:
  @rm -rf ./dist
  uv version --bump patch
  uv build
  uv publish

[parallel]
ci: lint test format
