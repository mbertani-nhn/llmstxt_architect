# Load environment variables from .env file
#set dotenv-load := true
#set dotenv-path := ".env"

# show available commands
show-commands:
  just -l

# create python environment
[working-directory: '.']
create-python-env:
  uv venv --python 3.10
  uv sync

# --- Testing ---

# run all tests
test:
  uv run python tests/test_cli.py
  uv run python tests/test_async_pipeline.py
  uv run python tests/test_temporal.py

# run CLI argument parsing tests
test-cli:
  uv run python tests/test_cli.py

# run async pipeline tests
test-async:
  uv run python tests/test_async_pipeline.py

# run temporal integration tests
test-temporal:
  uv run python tests/test_temporal.py

# run API integration test (requires LLM API key)
test-api:
  uv run python tests/test_api.py

# run the full test suite including integration tests
test-all:
  uv run python tests/test_all.py

# --- Formatting & Linting ---

# format code with black and isort
format:
  uv run ruff format

# run linter with auto-fix
lint-fix:
  uv run ruff check --fix .

# run type checker
typecheck:
  uv run mypy llmstxt_architect/

# run all checks (format, lint, typecheck)
check: format lint-fix typecheck
