#!/usr/bin/env python3
"""
Test script to test CLI argument parsing.

Tests both the original args and the new concurrency / orchestrator args
added with the async pipeline and Temporal integration.
"""

import argparse
import sys


def parse_args(test_args=None):
    """
    Mirror of the real CLI parser for isolated testing.

    Keeps this test runnable without installing the package (e.g. in CI
    where only the source tree is available).
    """
    parser = argparse.ArgumentParser(description="Test CLI parser")

    # Create mutually exclusive group for URL input sources
    url_group = parser.add_mutually_exclusive_group(required=True)

    url_group.add_argument("--urls", nargs="+", help="List of URLs to process")

    url_group.add_argument(
        "--existing-llms-file",
        help="Path to an existing llms.txt file",
    )

    parser.add_argument(
        "--update-descriptions-only",
        action="store_true",
        help="Update only descriptions in existing llms.txt",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Maximum recursion depth (default: 5)",
    )

    parser.add_argument(
        "--max-concurrent-crawls",
        type=int,
        default=3,
        help="Max concurrent root URL crawls (default: 3)",
    )

    parser.add_argument(
        "--max-concurrent-summaries",
        type=int,
        default=5,
        help="Max concurrent LLM summarization calls (default: 5)",
    )

    parser.add_argument(
        "--orchestrator",
        default="local",
        choices=["local", "temporal"],
        help="Orchestrator to use (default: local)",
    )

    parser.add_argument(
        "--temporal-address",
        default="localhost:7233",
        help="Temporal server address (default: localhost:7233)",
    )

    parser.add_argument(
        "--output-file",
        default=None,
        help="Output file name (default: based on format)",
    )

    parser.add_argument(
        "--output-format",
        default="txt",
        choices=["txt", "jsonl"],
        help="Output format (default: txt)",
    )

    if test_args:
        return parser.parse_args(test_args)
    return parser.parse_args()


# --- Original tests ---


def test_url_args():
    """Test with URL arguments."""
    try:
        test_args = [
            "--urls",
            "https://example.com",
            "https://example.org",
        ]
        args = parse_args(test_args)

        assert args.urls == [
            "https://example.com",
            "https://example.org",
        ], "URLs not parsed correctly"
        assert args.existing_llms_file is None
        assert args.update_descriptions_only is False

        print("  URL args test passed!")
        return True
    except Exception as e:
        print(f"  URL args test failed: {e}")
        return False


def test_existing_file_args():
    """Test with existing-llms-file argument."""
    try:
        test_args = [
            "--existing-llms-file",
            "path/to/llms.txt",
            "--update-descriptions-only",
        ]
        args = parse_args(test_args)

        assert args.urls is None
        assert args.existing_llms_file == "path/to/llms.txt"
        assert args.update_descriptions_only is True

        print("  Existing file args test passed!")
        return True
    except Exception as e:
        print(f"  Existing file args test failed: {e}")
        return False


# --- New concurrency arg tests ---


def test_concurrency_defaults():
    """Test that concurrency args have correct defaults."""
    try:
        args = parse_args(["--urls", "https://example.com"])

        assert args.max_concurrent_crawls == 3, f"Expected 3, got {args.max_concurrent_crawls}"
        assert args.max_concurrent_summaries == 5, f"Expected 5, got {args.max_concurrent_summaries}"

        print("  Concurrency defaults test passed!")
        return True
    except Exception as e:
        print(f"  Concurrency defaults test failed: {e}")
        return False


def test_concurrency_custom_values():
    """Test custom concurrency values."""
    try:
        args = parse_args(
            [
                "--urls",
                "https://example.com",
                "--max-concurrent-crawls",
                "10",
                "--max-concurrent-summaries",
                "8",
            ]
        )

        assert args.max_concurrent_crawls == 10, f"Expected 10, got {args.max_concurrent_crawls}"
        assert args.max_concurrent_summaries == 8, f"Expected 8, got {args.max_concurrent_summaries}"

        print("  Concurrency custom values test passed!")
        return True
    except Exception as e:
        print(f"  Concurrency custom values test failed: {e}")
        return False


# --- Orchestrator arg tests ---


def test_orchestrator_default():
    """Test that orchestrator defaults to 'local'."""
    try:
        args = parse_args(["--urls", "https://example.com"])

        assert args.orchestrator == "local", f"Expected 'local', got '{args.orchestrator}'"
        assert args.temporal_address == "localhost:7233", (
            f"Expected 'localhost:7233', got '{args.temporal_address}'"
        )

        print("  Orchestrator default test passed!")
        return True
    except Exception as e:
        print(f"  Orchestrator default test failed: {e}")
        return False


def test_orchestrator_temporal():
    """Test temporal orchestrator with custom address."""
    try:
        args = parse_args(
            [
                "--urls",
                "https://example.com",
                "--orchestrator",
                "temporal",
                "--temporal-address",
                "myhost:7233",
            ]
        )

        assert args.orchestrator == "temporal"
        assert args.temporal_address == "myhost:7233"

        print("  Orchestrator temporal test passed!")
        return True
    except Exception as e:
        print(f"  Orchestrator temporal test failed: {e}")
        return False


def test_orchestrator_invalid_choice():
    """Test that an invalid orchestrator choice is rejected."""
    try:
        parse_args(
            [
                "--urls",
                "https://example.com",
                "--orchestrator",
                "invalid",
            ]
        )
        print("  Orchestrator invalid choice test failed: no error raised")
        return False
    except SystemExit:
        # argparse exits on invalid choice — expected
        print("  Orchestrator invalid choice test passed!")
        return True
    except Exception as e:
        print(f"  Orchestrator invalid choice test failed: {e}")
        return False


# --- Output format arg tests ---


def test_output_format_default():
    """Test that output format defaults to 'txt'."""
    try:
        args = parse_args(["--urls", "https://example.com"])

        assert args.output_format == "txt", f"Expected 'txt', got '{args.output_format}'"
        assert args.output_file is None, f"Expected None, got '{args.output_file}'"

        print("  Output format default test passed!")
        return True
    except Exception as e:
        print(f"  Output format default test failed: {e}")
        return False


def test_output_format_jsonl():
    """Test JSONL output format."""
    try:
        args = parse_args(
            [
                "--urls",
                "https://example.com",
                "--output-format",
                "jsonl",
            ]
        )

        assert args.output_format == "jsonl", f"Expected 'jsonl', got '{args.output_format}'"

        print("  Output format jsonl test passed!")
        return True
    except Exception as e:
        print(f"  Output format jsonl test failed: {e}")
        return False


def test_output_format_with_custom_file():
    """Test output format with custom output file."""
    try:
        args = parse_args(
            [
                "--urls",
                "https://example.com",
                "--output-format",
                "jsonl",
                "--output-file",
                "custom_output.jsonl",
            ]
        )

        assert args.output_format == "jsonl"
        assert args.output_file == "custom_output.jsonl"

        print("  Output format with custom file test passed!")
        return True
    except Exception as e:
        print(f"  Output format with custom file test failed: {e}")
        return False


def test_output_format_invalid_choice():
    """Test that an invalid output format choice is rejected."""
    try:
        parse_args(
            [
                "--urls",
                "https://example.com",
                "--output-format",
                "xml",
            ]
        )
        print("  Output format invalid choice test failed: no error raised")
        return False
    except SystemExit:
        # argparse exits on invalid choice — expected
        print("  Output format invalid choice test passed!")
        return True
    except Exception as e:
        print(f"  Output format invalid choice test failed: {e}")
        return False


# --- Combined tests ---


def test_all_args_together():
    """Test all arguments combined."""
    try:
        args = parse_args(
            [
                "--existing-llms-file",
                "llms.txt",
                "--update-descriptions-only",
                "--max-depth",
                "2",
                "--max-concurrent-crawls",
                "6",
                "--max-concurrent-summaries",
                "12",
                "--orchestrator",
                "temporal",
                "--temporal-address",
                "cloud.temporal.io:7233",
                "--output-format",
                "jsonl",
                "--output-file",
                "output.jsonl",
            ]
        )

        assert args.existing_llms_file == "llms.txt"
        assert args.update_descriptions_only is True
        assert args.max_depth == 2
        assert args.max_concurrent_crawls == 6
        assert args.max_concurrent_summaries == 12
        assert args.orchestrator == "temporal"
        assert args.temporal_address == "cloud.temporal.io:7233"
        assert args.output_format == "jsonl"
        assert args.output_file == "output.jsonl"

        print("  All args combined test passed!")
        return True
    except Exception as e:
        print(f"  All args combined test failed: {e}")
        return False


def run_tests():
    """Run all parser tests."""
    results = {}

    print("\nOriginal arg tests:")
    results["url_args"] = test_url_args()
    results["existing_file_args"] = test_existing_file_args()

    print("\nConcurrency arg tests:")
    results["concurrency_defaults"] = test_concurrency_defaults()
    results["concurrency_custom"] = test_concurrency_custom_values()

    print("\nOrchestrator arg tests:")
    results["orchestrator_default"] = test_orchestrator_default()
    results["orchestrator_temporal"] = test_orchestrator_temporal()
    results["orchestrator_invalid"] = test_orchestrator_invalid_choice()

    print("\nOutput format arg tests:")
    results["output_format_default"] = test_output_format_default()
    results["output_format_jsonl"] = test_output_format_jsonl()
    results["output_format_custom_file"] = test_output_format_with_custom_file()
    results["output_format_invalid"] = test_output_format_invalid_choice()

    print("\nCombined arg tests:")
    results["all_args"] = test_all_args_together()

    print("\nTest Summary:")
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")

    return all(results.values())


def main():
    """Main test function."""
    success = run_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
