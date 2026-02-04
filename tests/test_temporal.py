#!/usr/bin/env python3
"""
Tests for the Temporal integration module.

These tests verify the structure and serialization of the temporal
package without requiring a running Temporal server. They check:
- Package imports and constants
- Dataclass serialization (activities, workflows)
- CLI graceful fallback when temporalio is not installed
"""

import sys
from dataclasses import asdict


def test_temporal_package_imports():
    """Verify the temporal package and TASK_QUEUE constant import."""
    try:
        from llmstxt_architect.temporal import TASK_QUEUE

        assert TASK_QUEUE == "llmstxt-architect", f"Expected 'llmstxt-architect', got '{TASK_QUEUE}'"

        print("  Package imports test passed!")
        return True
    except Exception as e:
        print(f"  Package imports test failed: {e}")
        return False


def test_activity_dataclasses_serializable():
    """Verify activity input/output dataclasses are serializable."""
    try:
        try:
            from llmstxt_architect.temporal.activities import (
                DiscoverUrlsInput,
                DiscoverUrlsOutput,
                GenerateOutputInput,
                SaveCheckpointInput,
                SummarizeDocInput,
                SummarizeDocOutput,
            )
        except ImportError:
            print("  Activity dataclasses test skipped (temporalio not installed)")
            return True

        # Test DiscoverUrlsInput
        d = DiscoverUrlsInput(
            urls=["https://example.com"],
            max_depth=2,
            extractor_name="bs4",
        )
        data = asdict(d)
        assert data["urls"] == ["https://example.com"]
        assert data["max_depth"] == 2
        assert data["extractor_name"] == "bs4"
        assert data["existing_llms_file"] is None

        # Test DiscoverUrlsOutput
        out = DiscoverUrlsOutput(
            urls=["https://example.com"],
            doc_contents=["content"],
            doc_sources=["https://example.com"],
            doc_titles=["Example"],
        )
        data = asdict(out)
        assert len(data["doc_contents"]) == 1

        # Test SummarizeDocInput
        s = SummarizeDocInput(
            url="https://example.com",
            content="test content",
            title="Test",
            llm_name="claude-3",
            llm_provider="anthropic",
            summary_prompt="Summarize",
            output_dir="/tmp/out",
        )
        data = asdict(s)
        assert data["url"] == "https://example.com"
        assert data["blacklisted_urls"] == []
        assert data["url_titles"] == {}

        # Test SummarizeDocOutput
        so = SummarizeDocOutput(
            url="https://example.com",
            summary="A summary",
            filename="example.txt",
        )
        data = asdict(so)
        assert data["skipped"] is False
        assert data["error"] is None

        # Test SaveCheckpointInput
        sc = SaveCheckpointInput(
            output_dir="/tmp/out",
            summarized_urls={"url": "file.txt"},
        )
        data = asdict(sc)
        assert "url" in data["summarized_urls"]

        # Test GenerateOutputInput
        go = GenerateOutputInput(
            summaries=["summary1"],
            output_file="llms.txt",
            output_dir="/tmp/summaries",
        )
        data = asdict(go)
        assert data["file_structure"] is None
        assert data["blacklisted_urls"] == []

        print("  Activity dataclasses test passed!")
        return True
    except Exception as e:
        print(f"  Activity dataclasses test failed: {e}")
        return False


def test_workflow_dataclasses_serializable():
    """Verify workflow input dataclasses are serializable."""
    try:
        from llmstxt_architect.temporal.workflows import (
            BatchProcessInput,
            BatchProcessOutput,
            CrawlAndSummarizeInput,
        )

        # Test CrawlAndSummarizeInput with defaults
        c = CrawlAndSummarizeInput(
            urls=["https://example.com"],
        )
        data = asdict(c)
        assert data["max_depth"] == 5
        assert data["llm_provider"] == "anthropic"
        assert data["max_concurrent_summaries"] == 5
        assert data["blacklisted_urls"] == []
        assert data["file_structure"] is None

        # Test BatchProcessInput
        b = BatchProcessInput(
            doc_urls=["https://a.com", "https://b.com"],
            doc_contents=["content a", "content b"],
            doc_titles=["A", "B"],
            llm_name="claude-3",
            llm_provider="anthropic",
            summary_prompt="Summarize",
            output_dir="/tmp/out",
        )
        data = asdict(b)
        assert len(data["doc_urls"]) == 2
        assert data["max_concurrent_summaries"] == 5

        # Test BatchProcessOutput
        bo = BatchProcessOutput(
            summaries=["s1"],
            summarized_urls={"url": "file.txt"},
        )
        data = asdict(bo)
        assert len(data["summaries"]) == 1

        print("  Workflow dataclasses test passed!")
        return True
    except ImportError:
        # temporalio not installed — workflows import it
        print("  Workflow dataclasses test skipped (temporalio not installed)")
        return True
    except Exception as e:
        print(f"  Workflow dataclasses test failed: {e}")
        return False


def test_temporal_client_graceful_import():
    """Verify temporal client fails gracefully without temporalio."""
    try:
        import importlib.util

        # Check if temporalio is available
        temporalio_spec = importlib.util.find_spec("temporalio")
        if temporalio_spec is not None:
            # temporalio is installed — client should import fine
            from llmstxt_architect.temporal.client import (
                run_temporal_workflow,
            )

            assert callable(run_temporal_workflow)
            print("  Client import test passed! (temporalio installed)")
            return True
        else:
            # temporalio not installed — import should raise
            try:
                from llmstxt_architect.temporal.client import (
                    run_temporal_workflow,
                )

                print("  Client import test failed: should raise without temporalio")
                return False
            except ImportError:
                print("  Client import test passed! (graceful ImportError)")
                return True
    except Exception as e:
        print(f"  Client import test failed: {e}")
        return False


def test_worker_entry_point_defined():
    """Verify pyproject.toml has llmstxt-architect-worker entry point."""
    try:
        import os

        # Find pyproject.toml relative to tests/
        test_dir = os.path.dirname(os.path.abspath(__file__))
        pyproject = os.path.join(test_dir, "..", "pyproject.toml")

        with open(pyproject, "r") as f:
            content = f.read()

        assert "llmstxt-architect-worker" in content, "Worker entry point not in pyproject.toml"
        assert "temporalio" in content, "temporalio not in pyproject.toml optional deps"

        print("  Worker entry point test passed!")
        return True
    except Exception as e:
        print(f"  Worker entry point test failed: {e}")
        return False


def test_batch_size_constant():
    """Verify BATCH_SIZE is defined in workflows module."""
    try:
        from llmstxt_architect.temporal.workflows import BATCH_SIZE

        assert isinstance(BATCH_SIZE, int)
        assert BATCH_SIZE > 0

        print("  Batch size constant test passed!")
        return True
    except ImportError:
        print("  Batch size constant test skipped (temporalio not installed)")
        return True
    except Exception as e:
        print(f"  Batch size constant test failed: {e}")
        return False


def run_tests():
    """Run all temporal tests."""
    results = {}

    print("\nTemporal package tests:")
    results["package_imports"] = test_temporal_package_imports()
    results["activity_dataclasses"] = test_activity_dataclasses_serializable()
    results["workflow_dataclasses"] = test_workflow_dataclasses_serializable()
    results["client_graceful_import"] = test_temporal_client_graceful_import()
    results["worker_entry_point"] = test_worker_entry_point_defined()
    results["batch_size"] = test_batch_size_constant()

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
