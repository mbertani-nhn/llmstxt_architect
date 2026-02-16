"""
Temporal workflow definitions for LLMsTxt Architect.

CrawlAndSummarizeWorkflow is the top-level workflow that orchestrates the
entire pipeline. It uses child workflows (BatchProcessWorkflow) to process
documents in batches, keeping event histories small.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from llmstxt_architect.temporal.activities import (
        DiscoverUrlsInput,
        GenerateOutputInput,
        LoadBatchInput,
        SaveCheckpointInput,
        SummarizeDocInput,
        SummarizeDocOutput,
        discover_urls,
        generate_output_file,
        load_batch,
        save_checkpoint,
        summarize_document,
    )


BATCH_SIZE = 10


@dataclass
class CrawlAndSummarizeInput:
    """Input for the top-level workflow."""

    urls: List[str]
    max_depth: int = 5
    llm_name: str = "claude-3-sonnet-20240229"
    llm_provider: str = "anthropic"
    summary_prompt: str = ""
    project_dir: str = "llms_txt"
    output_dir: str = "summaries"
    output_file: str = "llms.txt"
    output_format: str = "txt"
    blacklist_file: Optional[str] = None
    extractor_name: str = "default"
    existing_llms_file: Optional[str] = None
    update_descriptions_only: bool = False
    max_concurrent_summaries: int = 5
    blacklisted_urls: List[str] = field(default_factory=list)
    url_titles: Dict[str, str] = field(default_factory=dict)
    file_structure: Optional[List[str]] = None


@dataclass
class BatchProcessInput:
    """Input for a batch processing child workflow."""

    doc_urls: List[str]
    doc_content_files: List[str]
    doc_titles: List[str]
    llm_name: str
    llm_provider: str
    summary_prompt: str
    output_dir: str
    blacklisted_urls: List[str] = field(default_factory=list)
    url_titles: Dict[str, str] = field(default_factory=dict)
    max_concurrent_summaries: int = 5
    output_format: str = "txt"


@dataclass
class JsonlEntryData:
    """JSONL entry data for workflow."""

    url: str
    content: str
    summary: str
    keywords: List[str]


@dataclass
class BatchProcessOutput:
    """Output from a batch processing child workflow."""

    summaries: List[str]
    summarized_urls: Dict[str, str]
    jsonl_entries: List[Dict[str, Any]] = field(default_factory=list)


@workflow.defn
class BatchProcessWorkflow:
    """
    Child workflow that processes a batch of documents.

    Each batch gets its own event history to stay under the 50K event limit.
    Documents within a batch are summarized concurrently.
    """

    @workflow.run
    async def run(self, input: BatchProcessInput) -> BatchProcessOutput:
        """Process a batch of documents."""
        summaries: List[str] = []
        summarized_urls: Dict[str, str] = {}
        # JSONL entries are saved to disk during summarization, not returned here

        # Create activity inputs for all docs in the batch
        tasks = []
        for url, content_file, title in zip(input.doc_urls, input.doc_content_files, input.doc_titles):
            task_input = SummarizeDocInput(
                url=url,
                content_file=content_file,
                title=title,
                llm_name=input.llm_name,
                llm_provider=input.llm_provider,
                summary_prompt=input.summary_prompt,
                output_dir=input.output_dir,
                blacklisted_urls=input.blacklisted_urls,
                url_titles=input.url_titles,
                output_format=input.output_format,
            )
            tasks.append(
                workflow.execute_activity(
                    summarize_document,
                    task_input,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=3,
                        backoff_coefficient=2.0,
                    ),
                )
            )

        # Execute all activities in the batch concurrently
        import asyncio

        results: List[SummarizeDocOutput] = await asyncio.gather(*tasks)

        for result in results:
            if result.summary and result.filename:
                summaries.append(result.summary)
                summarized_urls[result.url] = result.filename
                # JSONL entries are saved to disk in the activity, not collected here
            elif result.error:
                workflow.logger.warning(f"Failed to summarize {result.url}: {result.error}")

        # Save checkpoint after batch
        await workflow.execute_activity(
            save_checkpoint,
            SaveCheckpointInput(
                output_dir=input.output_dir,
                summarized_urls=summarized_urls,
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )

        return BatchProcessOutput(
            summaries=summaries,
            summarized_urls=summarized_urls,
            # jsonl_entries are read from disk, not passed through workflow
        )


@workflow.defn
class CrawlAndSummarizeWorkflow:
    """
    Top-level workflow that orchestrates the full crawl-and-summarize pipeline.

    1. Discovers all URLs via the discover_urls activity
    2. Spawns child BatchProcessWorkflow for each batch of documents
    3. Generates the final llms.txt output file

    Uses continue_as_new as a safety valve for very large crawls.
    """

    @workflow.run
    async def run(self, input: CrawlAndSummarizeInput) -> str:
        """Run the full pipeline."""
        # Construct paths (avoid os.path inside workflow sandbox)
        summaries_path = f"{input.project_dir}/{input.output_dir}"
        output_file_path = f"{input.project_dir}/{input.output_file}"

        workflow.logger.info(f"Starting crawl-and-summarize workflow for {len(input.urls)} URLs")

        # Phase 1: Discover URLs (saves content to disk, returns manifest path)
        discover_output = await workflow.execute_activity(
            discover_urls,
            DiscoverUrlsInput(
                urls=input.urls,
                project_dir=input.project_dir,
                max_depth=input.max_depth,
                extractor_name=input.extractor_name,
                existing_llms_file=input.existing_llms_file,
            ),
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(minutes=2),
                maximum_attempts=3,
            ),
        )

        total_docs = discover_output.total_docs
        manifest_path = discover_output.manifest_path
        workflow.logger.info(f"Discovered {total_docs} documents to summarize")

        # Phase 2: Process documents in batches via child workflows
        all_summaries: List[str] = []
        all_summarized_urls: Dict[str, str] = {}
        # Note: JSONL entries are saved to disk during summarization and read back
        # in generate_output_file to avoid exceeding Temporal's gRPC message size limit

        for batch_start in range(0, total_docs, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_docs)

            # Load batch metadata from manifest (small payload)
            batch_data = await workflow.execute_activity(
                load_batch,
                LoadBatchInput(
                    manifest_path=manifest_path,
                    batch_start=batch_start,
                    batch_end=batch_end,
                ),
                start_to_close_timeout=timedelta(seconds=30),
            )

            batch_input = BatchProcessInput(
                doc_urls=batch_data.doc_urls,
                doc_content_files=batch_data.doc_content_files,
                doc_titles=batch_data.doc_titles,
                llm_name=input.llm_name,
                llm_provider=input.llm_provider,
                summary_prompt=input.summary_prompt,
                output_dir=summaries_path,
                blacklisted_urls=input.blacklisted_urls,
                url_titles=input.url_titles,
                max_concurrent_summaries=input.max_concurrent_summaries,
                output_format=input.output_format,
            )

            batch_output = await workflow.execute_child_workflow(
                BatchProcessWorkflow.run,
                batch_input,
                id=f"batch-{batch_start}-{batch_end}",
            )

            all_summaries.extend(batch_output.summaries)
            all_summarized_urls.update(batch_output.summarized_urls)
            # JSONL entries are read from disk, not passed through workflow

            workflow.logger.info(
                f"Batch {batch_start}-{batch_end} complete: {len(batch_output.summaries)} summaries"
            )

            # Safety valve: continue_as_new if we've processed many batches
            # to avoid hitting the 50K event limit on the parent workflow
            if batch_end < total_docs and batch_end >= 500:
                workflow.logger.info(f"Continuing as new after {batch_end} documents")
                remaining_input = CrawlAndSummarizeInput(
                    urls=input.urls,
                    max_depth=0,
                    llm_name=input.llm_name,
                    llm_provider=input.llm_provider,
                    summary_prompt=input.summary_prompt,
                    project_dir=input.project_dir,
                    output_dir=input.output_dir,
                    output_file=input.output_file,
                    output_format=input.output_format,
                    blacklist_file=input.blacklist_file,
                    extractor_name=input.extractor_name,
                    existing_llms_file=input.existing_llms_file,
                    update_descriptions_only=input.update_descriptions_only,
                    max_concurrent_summaries=input.max_concurrent_summaries,
                    blacklisted_urls=input.blacklisted_urls,
                    url_titles=input.url_titles,
                    file_structure=input.file_structure,
                )
                workflow.continue_as_new(remaining_input)

        # Phase 3: Generate final output file
        # Note: JSONL entries are read from disk in the activity, not passed here
        output_path = await workflow.execute_activity(
            generate_output_file,
            GenerateOutputInput(
                summaries=all_summaries,
                output_file=output_file_path,
                output_dir=summaries_path,
                blacklisted_urls=input.blacklisted_urls,
                file_structure=input.file_structure,
                output_format=input.output_format,
            ),
            start_to_close_timeout=timedelta(minutes=5),
        )

        workflow.logger.info(f"Workflow complete: {len(all_summaries)} summaries -> {output_path}")
        return output_path
