"""
Temporal client for starting workflows from the CLI.
"""

import os
import time
import uuid
from typing import Dict, List, Optional

from temporalio.client import Client

from llmstxt_architect.temporal import TASK_QUEUE
from llmstxt_architect.temporal.workflows import CrawlAndSummarizeInput


async def run_temporal_workflow(
    urls: List[str],
    max_depth: int = 5,
    llm_name: str = "claude-3-sonnet-20240229",
    llm_provider: str = "anthropic",
    project_dir: str = "llms_txt",
    output_dir: str = "summaries",
    output_file: str = "llms.txt",
    summary_prompt: str = "",
    blacklist_file: Optional[str] = None,
    extractor_name: str = "default",
    existing_llms_file: Optional[str] = None,
    update_descriptions_only: bool = False,
    max_concurrent_summaries: int = 5,
    temporal_address: str = "localhost:7233",
) -> str:
    """
    Start the crawl-and-summarize workflow via Temporal.

    Args:
        urls: List of root URLs to process
        max_depth: Maximum crawl depth
        llm_name: LLM model name
        llm_provider: LLM provider
        project_dir: Output project directory
        output_dir: Summaries subdirectory name
        output_file: Output filename
        summary_prompt: Prompt for summarization
        blacklist_file: Path to blacklist file
        extractor_name: Content extractor name
        existing_llms_file: Existing llms.txt to update
        update_descriptions_only: Preserve structure when updating
        max_concurrent_summaries: Max concurrent LLM calls
        temporal_address: Temporal server address

    Returns:
        Path to the generated output file
    """
    # Load blacklisted URLs if file provided
    blacklisted_urls: List[str] = []
    if blacklist_file and os.path.exists(blacklist_file):
        with open(blacklist_file, "r") as f:
            lines = [line.strip() for line in f.readlines()]
            blacklisted_urls = [url.rstrip("/") for url in lines if url and not url.startswith("#")]

    # Load file structure if preserving
    file_structure: Optional[List[str]] = None
    url_titles: Dict[str, str] = {}
    if existing_llms_file and update_descriptions_only:
        if existing_llms_file.startswith(("http://", "https://")):
            from llmstxt_architect.loader import (
                fetch_llms_txt_from_url,
                parse_existing_llms_file_content,
            )

            content = await fetch_llms_txt_from_url(existing_llms_file)
            file_lines = content.splitlines(True)
            _, file_structure = parse_existing_llms_file_content(file_lines)
        else:
            from llmstxt_architect.loader import parse_existing_llms_file

            _, file_structure = parse_existing_llms_file(existing_llms_file)

    # Use default summary prompt if none provided
    if not summary_prompt:
        summary_prompt = (
            "You are creating a summary for a webpage to be used in a llms.txt file "
            "to help LLMs in the future know what is on this page. Produce a concise "
            "summary of the key items on this page and when an LLM should access it."
        )

    start_time = time.time()

    # Create project directory
    os.makedirs(project_dir, exist_ok=True)

    print(f"Connecting to Temporal at {temporal_address}...")
    client = await Client.connect(temporal_address)

    workflow_id = f"llmstxt-{uuid.uuid4().hex[:8]}"
    print(f"Starting workflow {workflow_id}...")

    workflow_input = CrawlAndSummarizeInput(
        urls=urls,
        max_depth=max_depth,
        llm_name=llm_name,
        llm_provider=llm_provider,
        summary_prompt=summary_prompt,
        project_dir=project_dir,
        output_dir=output_dir,
        output_file=output_file,
        blacklist_file=blacklist_file,
        extractor_name=extractor_name,
        existing_llms_file=existing_llms_file,
        update_descriptions_only=update_descriptions_only,
        max_concurrent_summaries=max_concurrent_summaries,
        blacklisted_urls=blacklisted_urls,
        url_titles=url_titles,
        file_structure=file_structure,
    )

    result = await client.execute_workflow(
        "CrawlAndSummarizeWorkflow",
        workflow_input,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    elapsed = time.time() - start_time
    print(f"Workflow completed in {elapsed:.1f}s")
    print(f"Output: {result}")
    print(f"View workflow history at: http://localhost:8233/namespaces/default/workflows/{workflow_id}")

    return result


async def get_workflow_result(
    workflow_id: str,
    temporal_address: str = "localhost:7233",
) -> str:
    """
    Reconnect to an existing workflow and wait for its result.

    Args:
        workflow_id: The workflow ID to reconnect to
        temporal_address: Temporal server address

    Returns:
        The workflow result (path to the generated output file)
    """
    print(f"Connecting to Temporal at {temporal_address}...")
    client = await Client.connect(temporal_address)

    handle = client.get_workflow_handle(workflow_id)

    # Get current status
    desc = await handle.describe()
    status = desc.status.name
    print(f"Workflow {workflow_id} status: {status}")

    if status == "COMPLETED":
        result = await handle.result()
        print(f"Output: {result}")
        return result
    elif status in ("FAILED", "CANCELED", "TERMINATED", "TIMED_OUT"):
        print(f"Workflow {workflow_id} ended with status: {status}")
        raise RuntimeError(f"Workflow {workflow_id} has status {status}")
    else:
        print(f"Waiting for workflow {workflow_id} to complete (Ctrl+C to disconnect)...")
        result = await handle.result()
        print(f"Workflow completed. Output: {result}")
        return result
