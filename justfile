mediasorter *ARGS:
  uv run mediasorter {{ARGS}}

test:
  uv run pytest -n 4

tox:
  uv run tox -p all

format:
  uv run ruff format .

lint *ARGS:
  uv run ruff check {{ARGS}}

publish:
  @rm -rf ./dist
  uv version --bump patch
  uv build
  uv publish

[parallel]
ci: lint test format
