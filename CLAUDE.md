# CLAUDE.md

## Project Overview

LLMsTxt Architect is a Python package that generates `llms.txt` files using LLMs. It crawls websites, summarizes pages via LLM providers (Anthropic, OpenAI, Ollama), and outputs a standardized `llms.txt` file. The pipeline is fully async with concurrent crawling and summarization, and optionally orchestrated via Temporal workflows.

## Tech Stack

- **Language:** Python 3.10+
- **Build system:** Hatchling
- **Package manager:** uv
- **Task runner:** just
- **Core deps:** langchain, langchain-anthropic, langchain-ollama, beautifulsoup4, httpx, markdownify, lxml
- **Optional deps:** temporalio (for Temporal workflow orchestration)
- **Dev deps:** black, isort, mypy, pytest, ruff

## Common Commands

```bash
# Set up environment
just create-python-env      # Creates venv with Python 3.10 and syncs deps
uv venv --python 3.10 && uv sync  # Manual equivalent

# Run the tool (local async pipeline)
llmstxt-architect --urls https://example.com --max-depth 1 --llm-name claude-3-7-sonnet-latest --llm-provider anthropic --project-dir output

# Run with concurrency tuning
llmstxt-architect --urls https://example.com --max-concurrent-crawls 5 --max-concurrent-summaries 10

# Run with Temporal orchestration (requires: pip install 'llmstxt_architect[temporal]')
llmstxt-architect-worker                     # Start the Temporal worker (separate terminal)
llmstxt-architect --urls https://example.com --orchestrator temporal

# Run tests
just test                    # Unit tests (CLI + async pipeline + temporal)
just test-cli                # CLI argument parsing tests only
just test-async              # Async pipeline tests only
just test-temporal           # Temporal integration tests only
just test-api                # API integration test (requires LLM API key)
just test-all                # Full suite including integration tests

# Formatting and linting
just format                  # Format with black + isort
just lint                    # Lint with ruff
just lint-fix                # Lint with auto-fix
just typecheck               # Type check with mypy
just check                   # All of the above
```

## Project Structure

```
llmstxt_architect/
  __init__.py       # Package init, version (0.6.1)
  cli.py            # CLI entry point (argparse), registered as `llmstxt-architect`
  main.py           # Core async orchestration: generate_llms_txt()
  summarizer.py     # Summarizer class: concurrent LLM summarization, checkpoint/resume, deduplication
  loader.py         # URL fetching, concurrent recursive crawling, llms.txt parsing, batch processing
  extractor.py      # HTML content extraction (BeautifulSoup, markdownify)
  styling.py        # Terminal styling utilities (colors, status messages, report formatting)
  temporal/
    __init__.py     # Package init, TASK_QUEUE constant
    activities.py   # Temporal activities: discover_urls, summarize_document, save_checkpoint, generate_output_file
    workflows.py    # CrawlAndSummarizeWorkflow (parent) + BatchProcessWorkflow (child, batches of 10)
    worker.py       # Worker process, registered as `llmstxt-architect-worker`
    client.py       # Client to start workflows from CLI
tests/
  test_all.py             # Master test runner (all tests)
  test_cli.py             # CLI argument parsing (original + concurrency + orchestrator args)
  test_async_pipeline.py  # Async pipeline: ainvoke, to_thread, concurrency, log lock, params
  test_temporal.py        # Temporal: dataclass serialization, imports, entry points
  test_api.py             # API integration (requires LLM API key)
  test_script_claude.py   # Script import testing
  test_uvx_claude.py      # UVX + Claude integration
  test_uvx_ollama.py      # UVX + Ollama integration
  cleanup.py              # Test artifact cleanup
```

## Architecture

### Async Pipeline (default: `--orchestrator local`)
- **Concurrent crawling:** Root URLs are crawled in parallel via `asyncio.gather()` bounded by `asyncio.Semaphore(max_concurrent_crawls)` (default: 3)
- **Concurrent summarization:** Documents are summarized in parallel via `asyncio.gather()` bounded by `asyncio.Semaphore(max_concurrent_summaries)` (default: 5)
- **Non-blocking LLM calls:** Uses `.ainvoke()` instead of `.invoke()`
- **Non-blocking I/O:** File reads/writes and CPU-bound extractors wrapped in `asyncio.to_thread()`
- **Thread-safe logging:** `asyncio.Lock` protects concurrent checkpoint writes

### Temporal Orchestration (`--orchestrator temporal`)
- **Optional dependency:** Install with `pip install "llmstxt_architect[temporal]"`
- **Durable execution:** Workflows survive process crashes and resume automatically
- **Child workflows:** Documents are processed in batches of 10 (separate event histories)
- **continue_as_new:** Safety valve after 500 documents to avoid 50K event limit
- **Worker:** Run `llmstxt-architect-worker` to host workflows and activities

## Code Conventions

- **All functions must have type annotations** (mypy strict mode: `disallow_untyped_defs`, `disallow_incomplete_defs`)
- **Docstrings** on all modules, classes, and public functions
- **Async/await** pattern throughout (core logic is async)
- **Line length:** 88 characters (black default)
- **Import sorting:** isort with black profile
- **Formatting:** black
- Entry points: `llmstxt_architect.cli:main`, `llmstxt_architect.temporal.worker:main`
