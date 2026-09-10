mediasorter *ARGS:
  uv run mediasorter {{ARGS}}

test:
  uv run pytest

tox:
  uv run tox -p all

format:
  uv run ruff format .

