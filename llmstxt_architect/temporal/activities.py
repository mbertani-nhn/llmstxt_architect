"""
Temporal activities wrapping existing business logic.

Activities are the building blocks that perform actual work (fetch URLs,
summarize documents, write files). They use simple dataclass params for
serialization across the Temporal boundary.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from temporalio import activity


@dataclass
class DiscoverUrlsInput:
    """Input for the discover_urls activity."""

    urls: List[str]
    project_dir: str = "llms_txt"
    max_depth: int = 5
    extractor_name: str = "default"
    existing_llms_file: Optional[str] = None


@dataclass
class DiscoverUrlsOutput:
    """Output from the discover_urls activity.

    All data is saved to a manifest file on disk to avoid exceeding
    Temporal's payload size limit (~2MB). Only the manifest path and
    document count are returned through the Temporal boundary.
    """

    manifest_path: str
    total_docs: int


@dataclass
class LoadBatchInput:
    """Input for the load_batch activity."""

    manifest_path: str
    batch_start: int
    batch_end: int


@dataclass
class LoadBatchOutput:
    """Output from the load_batch activity (a single batch of doc metadata)."""

    doc_urls: List[str]
    doc_content_files: List[str]
    doc_titles: List[str]


@dataclass
class SummarizeDocInput:
    """Input for the summarize_document activity."""

    url: str
    content_file: str
    title: str
    llm_name: str
    llm_provider: str
    summary_prompt: str
    output_dir: str
    blacklisted_urls: List[str] = field(default_factory=list)
    url_titles: Dict[str, str] = field(default_factory=dict)


@dataclass
class SummarizeDocOutput:
    """Output from the summarize_document activity."""

    url: str
    summary: Optional[str] = None
    filename: Optional[str] = None
    skipped: bool = False
    error: Optional[str] = None


@dataclass
class SaveCheckpointInput:
    """Input for the save_checkpoint activity."""

    output_dir: str
    summarized_urls: Dict[str, str]


@dataclass
class GenerateOutputInput:
    """Input for the generate_output activity."""

    summaries: List[str]
    output_file: str
    output_dir: str
    blacklisted_urls: List[str] = field(default_factory=list)
    file_structure: Optional[List[str]] = None


@activity.defn
async def discover_urls(input: DiscoverUrlsInput) -> DiscoverUrlsOutput:
    """
    Discover and fetch all URLs to be summarized.

    All data (contents, URLs, titles) is saved to disk to avoid
    exceeding Temporal's payload size limit (~2MB). Returns only
    the manifest path and document count.
    """
    from llmstxt_architect.extractor import bs4_extractor, default_extractor
    from llmstxt_architect.loader import load_urls

    extractor_map = {"default": default_extractor, "bs4": bs4_extractor}
    extractor = extractor_map.get(input.extractor_name, default_extractor)

    activity.logger.info(f"Discovering URLs from {len(input.urls)} root URLs (max_depth={input.max_depth})")

    docs = await load_urls(
        urls=input.urls,
        max_depth=input.max_depth,
        extractor=extractor,
        existing_llms_file=input.existing_llms_file,
    )

    activity.logger.info(f"Discovered {len(docs)} documents")

    # Save document contents to staging files
    staging_dir = Path(input.project_dir) / ".staging"
    os.makedirs(staging_dir, exist_ok=True)

    manifest_entries: List[Dict[str, str]] = []
    for doc in docs:
        source = doc.metadata.get("source", "")
        title = doc.metadata.get("title", "")
        file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
        content_path = staging_dir / f"{file_hash}.txt"
        with open(content_path, "w") as f:
            f.write(doc.page_content)
        manifest_entries.append(
            {"url": source, "title": title, "content_file": str(content_path)}
        )

    # Save manifest
    manifest_path = staging_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest_entries, f)

    activity.logger.info(f"Saved {len(manifest_entries)} documents to staging directory")

    return DiscoverUrlsOutput(
        manifest_path=str(manifest_path),
        total_docs=len(manifest_entries),
    )


@activity.defn
async def load_batch(input: LoadBatchInput) -> LoadBatchOutput:
    """
    Load a batch slice of document metadata from the manifest.

    Reads the manifest file and returns only the requested range,
    keeping Temporal payloads small.
    """
    with open(input.manifest_path, "r") as f:
        manifest: List[Dict[str, str]] = json.load(f)

    batch = manifest[input.batch_start : input.batch_end]

    return LoadBatchOutput(
        doc_urls=[entry["url"] for entry in batch],
        doc_content_files=[entry["content_file"] for entry in batch],
        doc_titles=[entry["title"] for entry in batch],
    )


@activity.defn
async def summarize_document(input: SummarizeDocInput) -> SummarizeDocOutput:
    """
    Summarize a single document using the configured LLM.

    This wraps the core summarization logic but operates on plain data
    rather than Document objects.
    """
    from urllib.parse import urlparse

    from langchain.chat_models import init_chat_model

    url = input.url
    normalized_url = url.rstrip("/")

    # Check if URL is blacklisted
    if normalized_url in input.blacklisted_urls:
        activity.logger.info(f"Skipping blacklisted URL: {url}")
        return SummarizeDocOutput(url=url, skipped=True)

    # Check if already summarized (checkpoint file exists)
    output_dir = Path(input.output_dir)
    log_file = output_dir / "summarized_urls.json"
    if log_file.exists():
        with open(log_file, "r") as f:
            summarized_urls = json.load(f)
        if url in summarized_urls:
            summary_path = output_dir / summarized_urls[url]
            if summary_path.exists():
                with open(summary_path, "r") as f:
                    summary = f.read()
                activity.logger.info(f"Already summarized: {url}")
                return SummarizeDocOutput(
                    url=url,
                    summary=summary,
                    filename=summarized_urls[url],
                )

    try:
        activity.logger.info(f"Summarizing: {url}")

        # Read content from staging file
        with open(input.content_file, "r") as f:
            content = f.read()

        llm = init_chat_model(model=input.llm_name, model_provider=input.llm_provider)

        summary_response = await llm.ainvoke(
            [
                {"role": "system", "content": input.summary_prompt},
                {
                    "role": "human",
                    "content": (
                        f"Read and analyze this content: {content}\n\n"
                        "Now, provide a summary EXACTLY in this format:\n"
                        "Line 1: 'LLM should read this page when "
                        "(2-3 specific scenarios)'\n"
                        "Line 2: '(Direct summary of main topics)'\n\n"
                        "FOLLOW THIS FORMAT PRECISELY. No additional text. "
                        "Use parentheses () not square brackets []."
                    ),
                },
            ]
        )

        summary = summary_response.content

        # Extract page title
        if url in input.url_titles:
            title = input.url_titles[url]
        else:
            title = input.title or url.split("/")[-1]

        # Format summary
        clean_summary = summary.replace("\n\n", " ").replace("\n", " ").strip()
        formatted_summary = f"[{title}]({url}): {clean_summary}\n\n"

        # Generate filename
        parsed = urlparse(url)
        filename = f"{parsed.netloc}{parsed.path}".replace("/", "_")
        if not filename.endswith(".txt"):
            filename += ".txt"

        # Save individual summary
        os.makedirs(output_dir, exist_ok=True)
        with open(output_dir / filename, "w") as f:
            f.write(formatted_summary)

        return SummarizeDocOutput(url=url, summary=formatted_summary, filename=filename)

    except Exception as e:
        activity.logger.error(f"Error summarizing {url}: {str(e)}")
        return SummarizeDocOutput(url=url, error=str(e))


@activity.defn
async def save_checkpoint(input: SaveCheckpointInput) -> None:
    """Save the checkpoint log of summarized URLs."""
    output_dir = Path(input.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    log_file = output_dir / "summarized_urls.json"

    with open(log_file, "w") as f:
        json.dump(input.summarized_urls, f, indent=2)

    activity.logger.info(f"Checkpoint saved: {len(input.summarized_urls)} URLs logged")


@activity.defn
async def generate_output_file(input: GenerateOutputInput) -> str:
    """
    Generate the final llms.txt output file.

    Returns the path to the generated file.
    """
    url_pattern = re.compile(r"\[(.*?)\]\((https?://[^\s)]+)\)")

    if input.file_structure:
        # Structure-preserving mode
        url_to_summary: Dict[str, str] = {}
        for summary in input.summaries:
            match = url_pattern.search(summary)
            if match:
                url_to_summary[match.group(2)] = summary.strip()

        # Also check summary files in output dir
        output_dir = Path(input.output_dir)
        if output_dir.exists():
            for filename in os.listdir(output_dir):
                if filename.endswith(".txt") and filename != os.path.basename(input.output_file):
                    file_path = output_dir / filename
                    with open(file_path, "r") as f:
                        content = f.read()
                        match = url_pattern.search(content)
                        if match:
                            url = match.group(2)
                            if url not in url_to_summary:
                                url_to_summary[url] = content.strip()

        output_lines = []
        for line in input.file_structure:
            match = url_pattern.search(line)
            if match and match.group(2) in url_to_summary:
                output_lines.append(url_to_summary[match.group(2)] + "\n")
            else:
                output_lines.append(line)

        with open(input.output_file, "w") as f:
            f.writelines(output_lines)
    else:
        # Sorted mode (same logic as Summarizer.generate_llms_txt)
        summary_entries = []
        output_dir = Path(input.output_dir)

        if output_dir.exists():
            for filename in os.listdir(output_dir):
                if filename.endswith(".txt") and filename != os.path.basename(input.output_file):
                    file_path = output_dir / filename
                    with open(file_path, "r") as f:
                        content = f.read()
                        match = url_pattern.search(content)
                        url = match.group(2) if match else filename
                        normalized_url = url.rstrip("/")
                        if normalized_url not in input.blacklisted_urls:
                            summary_entries.append((normalized_url, content))

        # Deduplicate
        url_to_entries: Dict[str, List[str]] = {}
        for url, content in summary_entries:
            url_to_entries.setdefault(url, []).append(content)

        unique_entries = []
        for url, contents in url_to_entries.items():
            contents.sort(key=len, reverse=True)
            unique_entries.append((url, contents[0]))

        seen_content: set = set()
        final_entries = []
        for url, content in unique_entries:
            if content not in seen_content:
                final_entries.append((url, content))
                seen_content.add(content)

        sorted_entries = sorted(final_entries, key=lambda x: x[0])

        with open(input.output_file, "w") as f:
            for _, content in sorted_entries:
                f.write(content)

    activity.logger.info(f"Generated output file: {input.output_file}")
    return input.output_file
