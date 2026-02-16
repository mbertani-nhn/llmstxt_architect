#!/usr/bin/env python3
"""
Tests for the async pipeline changes.

Verifies that:
- .ainvoke() is used instead of .invoke()
- asyncio.to_thread() wraps file I/O and extractors
- Concurrent summarization uses Semaphore + gather
- Concurrent crawling uses Semaphore + gather
- Log lock protects concurrent writes
- New params (max_concurrent_*) are threaded through
"""

import inspect
import sys


def test_summarizer_uses_ainvoke():
    """Verify summarize_document uses .ainvoke() not .invoke()."""
    try:
        from llmstxt_architect.summarizer import Summarizer

        source = inspect.getsource(Summarizer.summarize_document)
        assert "ainvoke" in source, ".ainvoke() not found in summarize_document"
        assert ".invoke(" not in source.replace(".ainvoke(", ""), (
            "Sync .invoke() still present in summarize_document"
        )

        print("  ainvoke test passed!")
        return True
    except Exception as e:
        print(f"  ainvoke test failed: {e}")
        return False


def test_summarizer_async_file_io():
    """Verify summarize_document uses asyncio.to_thread for file I/O."""
    try:
        from llmstxt_architect.summarizer import Summarizer

        source = inspect.getsource(Summarizer.summarize_document)
        assert "asyncio.to_thread" in source, "asyncio.to_thread not found in summarize_document"
        # Check both read and write paths
        assert "_write_file" in source, "_write_file helper not used in summarize_document"
        assert "_read_file" in source, "_read_file helper not used in summarize_document"

        print("  Async file I/O test passed!")
        return True
    except Exception as e:
        print(f"  Async file I/O test failed: {e}")
        return False


def test_summarizer_has_log_lock():
    """Verify Summarizer creates an asyncio.Lock for log writes."""
    try:
        from llmstxt_architect.summarizer import Summarizer

        source = inspect.getsource(Summarizer.__init__)
        assert "asyncio.Lock()" in source, "asyncio.Lock() not created in __init__"

        source_doc = inspect.getsource(Summarizer.summarize_document)
        assert "_log_lock" in source_doc, "_log_lock not used in summarize_document"

        print("  Log lock test passed!")
        return True
    except Exception as e:
        print(f"  Log lock test failed: {e}")
        return False


def test_summarizer_concurrent_summarize_all():
    """Verify summarize_all uses Semaphore + gather for concurrency."""
    try:
        from llmstxt_architect.summarizer import Summarizer

        source = inspect.getsource(Summarizer.summarize_all)
        assert "asyncio.Semaphore" in source, "asyncio.Semaphore not found in summarize_all"
        assert "asyncio.gather" in source, "asyncio.gather not found in summarize_all"

        print("  Concurrent summarize_all test passed!")
        return True
    except Exception as e:
        print(f"  Concurrent summarize_all test failed: {e}")
        return False


def test_summarizer_max_concurrent_param():
    """Verify Summarizer.__init__ accepts max_concurrent_summaries."""
    try:
        from llmstxt_architect.summarizer import Summarizer

        sig = inspect.signature(Summarizer.__init__)
        assert "max_concurrent_summaries" in sig.parameters, (
            "max_concurrent_summaries not in Summarizer.__init__"
        )
        # Check default value
        default = sig.parameters["max_concurrent_summaries"].default
        assert default == 5, f"Expected default 5, got {default}"

        print("  Summarizer max_concurrent param test passed!")
        return True
    except Exception as e:
        print(f"  Summarizer max_concurrent param test failed: {e}")
        return False


def test_loader_concurrent_crawling():
    """Verify load_urls uses Semaphore + gather for concurrent crawling."""
    try:
        from llmstxt_architect.loader import load_urls

        source = inspect.getsource(load_urls)
        assert "asyncio.Semaphore" in source, "asyncio.Semaphore not found in load_urls"
        assert "asyncio.gather" in source, "asyncio.gather not found in load_urls"

        print("  Concurrent crawling test passed!")
        return True
    except Exception as e:
        print(f"  Concurrent crawling test failed: {e}")
        return False


def test_loader_max_concurrent_param():
    """Verify load_urls accepts max_concurrent_crawls param."""
    try:
        from llmstxt_architect.loader import load_urls

        sig = inspect.signature(load_urls)
        assert "max_concurrent_crawls" in sig.parameters, "max_concurrent_crawls not in load_urls"
        default = sig.parameters["max_concurrent_crawls"].default
        assert default == 3, f"Expected default 3, got {default}"

        print("  Loader max_concurrent param test passed!")
        return True
    except Exception as e:
        print(f"  Loader max_concurrent param test failed: {e}")
        return False


def test_loader_extractor_to_thread():
    """Verify fetch_url wraps extractor in asyncio.to_thread."""
    try:
        from llmstxt_architect.loader import fetch_url

        source = inspect.getsource(fetch_url)
        assert "asyncio.to_thread" in source, "asyncio.to_thread not found in fetch_url"

        print("  Extractor to_thread test passed!")
        return True
    except Exception as e:
        print(f"  Extractor to_thread test failed: {e}")
        return False


def test_main_threads_concurrency_params():
    """Verify generate_llms_txt accepts both concurrency params."""
    try:
        from llmstxt_architect.main import generate_llms_txt

        sig = inspect.signature(generate_llms_txt)
        assert "max_concurrent_crawls" in sig.parameters
        assert "max_concurrent_summaries" in sig.parameters

        print("  Main concurrency params test passed!")
        return True
    except Exception as e:
        print(f"  Main concurrency params test failed: {e}")
        return False


def test_summarizer_write_read_helpers():
    """Verify _write_file and _read_file static methods exist."""
    try:
        from llmstxt_architect.summarizer import Summarizer

        assert hasattr(Summarizer, "_write_file"), "_write_file not found on Summarizer"
        assert hasattr(Summarizer, "_read_file"), "_read_file not found on Summarizer"
        # Verify they are static methods
        assert isinstance(
            inspect.getattr_static(Summarizer, "_write_file"),
            staticmethod,
        ), "_write_file is not a staticmethod"
        assert isinstance(
            inspect.getattr_static(Summarizer, "_read_file"),
            staticmethod,
        ), "_read_file is not a staticmethod"

        print("  Write/read helpers test passed!")
        return True
    except Exception as e:
        print(f"  Write/read helpers test failed: {e}")
        return False


def run_tests():
    """Run all async pipeline tests."""
    results = {}

    print("\nSummarizer async tests:")
    results["ainvoke"] = test_summarizer_uses_ainvoke()
    results["async_file_io"] = test_summarizer_async_file_io()
    results["log_lock"] = test_summarizer_has_log_lock()
    results["concurrent_summarize"] = test_summarizer_concurrent_summarize_all()
    results["summarizer_param"] = test_summarizer_max_concurrent_param()
    results["write_read_helpers"] = test_summarizer_write_read_helpers()

    print("\nLoader async tests:")
    results["concurrent_crawl"] = test_loader_concurrent_crawling()
    results["loader_param"] = test_loader_max_concurrent_param()
    results["extractor_to_thread"] = test_loader_extractor_to_thread()

    print("\nMain integration tests:")
    results["main_params"] = test_main_threads_concurrency_params()

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
