# CLAUDE.md

## Project Overview

LLMsTxt Architect is a Python package that generates `llms.txt` files using LLMs. It crawls websites, summarizes pages via LLM providers (Anthropic, OpenAI, Ollama), and outputs a standardized `llms.txt` file.

## Tech Stack

- **Language:** Python 3.10+
- **Build system:** Hatchling
- **Package manager:** uv
- **Core deps:** langchain, langchain-anthropic, langchain-ollama, beautifulsoup4, httpx, markdownify, lxml
- **Dev deps:** black, isort, mypy, pytest, ruff

## Common Commands

```bash
# Set up environment
just create-python-env      # Creates venv with Python 3.10 and syncs deps
uv venv --python 3.10 && uv sync  # Manual equivalent

# Run the tool
llmstxt-architect --urls https://example.com --max-depth 1 --llm-name claude-3-7-sonnet-latest --llm-provider anthropic --project-dir output

# Run tests
python tests/test_all.py          # All tests
python tests/test_cli.py          # CLI parsing tests
python tests/test_api.py          # API tests
python tests/cleanup.py           # Clean test artifacts

# Formatting and linting
black .                           # Format (line-length 88)
isort .                           # Sort imports (black profile)
ruff check .                      # Lint (rules: E, F, I)
mypy .                            # Type check (strict: disallow_untyped_defs)
```

## Project Structure

```
llmstxt_architect/
  __init__.py       # Package init, version (0.6.1)
  cli.py            # CLI entry point (argparse), registered as `llmstxt-architect`
  main.py           # Core async orchestration: generate_llms_txt()
  summarizer.py     # Summarizer class: LLM-based summarization, checkpoint/resume, deduplication
  loader.py         # URL fetching, recursive crawling, llms.txt parsing, batch processing
  extractor.py      # HTML content extraction (BeautifulSoup, markdownify)
tests/
  test_all.py       # Master test runner
  test_cli.py       # CLI argument parsing
  test_api.py       # API usage
  test_script_claude.py  # Script import testing
  test_uvx_claude.py     # UVX + Claude integration
  test_uvx_ollama.py     # UVX + Ollama integration
  cleanup.py        # Test artifact cleanup
```

## Code Conventions

- **All functions must have type annotations** (mypy strict mode: `disallow_untyped_defs`, `disallow_incomplete_defs`)
- **Docstrings** on all modules, classes, and public functions
- **Async/await** pattern throughout (core logic is async)
- **Line length:** 88 characters (black default)
- **Import sorting:** isort with black profile
- **Formatting:** black
- Entry point: `llmstxt_architect.cli:main`
