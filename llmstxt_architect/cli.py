"""
Command-line interface for LLMsTxt Architect.
"""

import argparse
import asyncio
import sys

from llmstxt_architect.extractor import bs4_extractor, default_extractor
from llmstxt_architect.main import generate_llms_txt
from llmstxt_architect.styling import color_text, draw_box


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate LLMs.txt from web content using LLMs for summarization"
    )

    # Create mutually exclusive group for URL input sources
    # Not required because --workflow-id can be used instead
    url_group = parser.add_mutually_exclusive_group(required=False)

    url_group.add_argument("--urls", nargs="+", help="List of URLs to process")

    url_group.add_argument(
        "--existing-llms-file",
        help="Path to an existing llms.txt file to extract URLs from and update",
    )

    # Support legacy format for compatibility (--urls is no longer required when --existing-llms-file is present)
    # This is a workaround for uvx which might be passing arguments differently
    # Handle the case when args are manually specified on command line

    parser.add_argument(
        "--update-descriptions-only",
        action="store_true",
        help="Update only descriptions in existing llms.txt while preserving structure and URL order",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Maximum recursion depth for URL crawling (default: 5)",
    )

    parser.add_argument(
        "--llm-name",
        default="claude-3-sonnet-20240229",
        help="LLM model name (default: claude-3-sonnet-20240229)",
    )

    parser.add_argument("--llm-provider", default="anthropic", help="LLM provider (default: anthropic)")

    parser.add_argument(
        "--project-dir",
        default="llms_txt",
        help="Main project directory to store all outputs (default: llms_txt)",
    )

    parser.add_argument(
        "--output-dir",
        default="summaries",
        help="Directory within project-dir to save individual summaries (default: summaries)",
    )

    parser.add_argument(
        "--output-file",
        default="llms.txt",
        help="Output file name for combined summaries (default: llms.txt)",
    )

    parser.add_argument(
        "--summary-prompt",
        default=(
            "You are creating a summary for a webpage to be used in a llms.txt file "
            "to help LLMs in the future know what is on this page. Produce a concise "
            "summary of the key items on this page and when an LLM should access it."
        ),
        help="Prompt to use for summarization",
    )

    parser.add_argument(
        "--blacklist-file",
        help="Path to a file containing blacklisted URLs to exclude (one per line)",
    )

    parser.add_argument(
        "--extractor",
        default="default",
        choices=["default", "bs4"],
        help="Content extractor to use (default: markdownify, bs4: BeautifulSoup)",
    )

    parser.add_argument(
        "--max-concurrent-crawls",
        type=int,
        default=3,
        help="Maximum number of concurrent root URL crawls (default: 3)",
    )

    parser.add_argument(
        "--max-concurrent-summaries",
        type=int,
        default=5,
        help="Maximum number of concurrent LLM summarization calls (default: 5)",
    )

    parser.add_argument(
        "--orchestrator",
        default="local",
        choices=["local", "temporal"],
        help=(
            "Orchestrator to use: 'local' for async pipeline, "
            "'temporal' for Temporal workflows (default: local)"
        ),
    )

    parser.add_argument(
        "--temporal-address",
        default="localhost:7233",
        help="Temporal server address (default: localhost:7233)",
    )

    parser.add_argument(
        "--workflow-id",
        help="Reconnect to an existing Temporal workflow by ID (e.g. llmstxt-db5b06ab)",
    )

    return parser.parse_args()


def show_splash() -> None:
    """Display the splash screen."""
    print(
        color_text(
            draw_box("LLMsTxt Architect - Generate LLMs.txt from web content", "green", 2),
            "green",
        )
    )
    print()


def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()

    # Show splash screen
    show_splash()

    # Map extractor choice to function (these are coroutines, will be awaited internally)
    extractor_map = {"default": default_extractor, "bs4": bs4_extractor}
    extractor_func = extractor_map[args.extractor]

    # Handle --workflow-id: reconnect to existing Temporal workflow
    if args.workflow_id:
        if args.orchestrator != "temporal":
            print(color_text("Error: --workflow-id requires --orchestrator temporal", "red"))
            sys.exit(1)
        try:
            from llmstxt_architect.temporal.client import get_workflow_result
        except ImportError:
            print(
                color_text(
                    "Error: Temporal dependencies not installed. "
                    "Install with: pip install 'llmstxt_architect[temporal]'",
                    "red",
                )
            )
            sys.exit(1)

        try:
            asyncio.run(
                get_workflow_result(
                    workflow_id=args.workflow_id,
                    temporal_address=args.temporal_address,
                )
            )
        except KeyboardInterrupt:
            print(color_text("\nDisconnected. The workflow continues running on the server.", "yellow"))
            sys.exit(0)
        except Exception as e:
            print(color_text(f"Error: {str(e)}", "red"))
            sys.exit(1)
        return

    # Validate that URLs or existing-llms-file is provided when not using --workflow-id
    if not args.urls and not args.existing_llms_file:
        print(color_text("Error: --urls or --existing-llms-file is required (or use --workflow-id to reconnect)", "red"))
        sys.exit(1)

    # Handle update-descriptions-only flag (requires existing-llms-file)
    if args.update_descriptions_only and not args.existing_llms_file:
        print(color_text("Error: --update-descriptions-only requires --existing-llms-file", "red"))
        sys.exit(1)

    # If using existing llms file but no URLs specified, will extract from file
    urls = args.urls or []

    # Print status message for clarity
    if args.existing_llms_file:
        print(color_text(f"Using existing llms file: {args.existing_llms_file}", "blue"))
        if args.update_descriptions_only:
            print(color_text("Mode: Update descriptions only (preserving structure)", "blue"))

    try:
        if args.orchestrator == "temporal":
            try:
                from llmstxt_architect.temporal.client import run_temporal_workflow
            except ImportError:
                print(
                    color_text(
                        "Error: Temporal dependencies not installed. "
                        "Install with: pip install 'llmstxt_architect[temporal]'",
                        "red",
                    )
                )
                sys.exit(1)

            asyncio.run(
                run_temporal_workflow(
                    urls=urls,
                    max_depth=args.max_depth,
                    llm_name=args.llm_name,
                    llm_provider=args.llm_provider,
                    project_dir=args.project_dir,
                    output_dir=args.output_dir,
                    output_file=args.output_file,
                    summary_prompt=args.summary_prompt,
                    blacklist_file=args.blacklist_file,
                    extractor_name=args.extractor,
                    existing_llms_file=args.existing_llms_file,
                    update_descriptions_only=args.update_descriptions_only,
                    max_concurrent_summaries=args.max_concurrent_summaries,
                    temporal_address=args.temporal_address,
                )
            )
        else:
            asyncio.run(
                generate_llms_txt(
                    urls=urls,
                    max_depth=args.max_depth,
                    llm_name=args.llm_name,
                    llm_provider=args.llm_provider,
                    project_dir=args.project_dir,
                    output_dir=args.output_dir,
                    output_file=args.output_file,
                    summary_prompt=args.summary_prompt,
                    blacklist_file=args.blacklist_file,
                    extractor=extractor_func,
                    existing_llms_file=args.existing_llms_file,
                    update_descriptions_only=args.update_descriptions_only,
                    max_concurrent_crawls=args.max_concurrent_crawls,
                    max_concurrent_summaries=args.max_concurrent_summaries,
                )
            )
    except KeyboardInterrupt:
        print(color_text("\nOperation cancelled by user.", "yellow"))
        sys.exit(1)
    except Exception as e:
        print(color_text(f"Error: {str(e)}", "red"))
        sys.exit(1)


if __name__ == "__main__":
    main()
