"""
Temporal worker process for LLMsTxt Architect.

Run this to start a worker that hosts the workflows and activities:

    llmstxt-architect-worker
    llmstxt-architect-worker --temporal-address localhost:7233
"""

import argparse
import asyncio
import concurrent.futures

from temporalio.client import Client
from temporalio.worker import Worker

from llmstxt_architect.temporal import TASK_QUEUE
from llmstxt_architect.temporal.activities import (
    discover_urls,
    generate_output_file,
    load_batch,
    save_checkpoint,
    summarize_document,
)
from llmstxt_architect.temporal.workflows import (
    BatchProcessWorkflow,
    CrawlAndSummarizeWorkflow,
)


async def run_worker(temporal_address: str = "localhost:7233") -> None:
    """
    Connect to Temporal and run the worker.

    Args:
        temporal_address: Address of the Temporal server
    """
    print(f"Connecting to Temporal at {temporal_address}...")
    client = await Client.connect(temporal_address)

    print(f"Starting worker on task queue: {TASK_QUEUE}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[CrawlAndSummarizeWorkflow, BatchProcessWorkflow],
            activities=[
                discover_urls,
                load_batch,
                summarize_document,
                save_checkpoint,
                generate_output_file,
            ],
            activity_executor=executor,
        )
        print("Worker started. Ctrl+C to stop.")
        await worker.run()


def parse_args() -> argparse.Namespace:
    """Parse worker CLI arguments."""
    parser = argparse.ArgumentParser(description="LLMsTxt Architect Temporal Worker")
    parser.add_argument(
        "--temporal-address",
        default="localhost:7233",
        help="Temporal server address (default: localhost:7233)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the worker CLI."""
    args = parse_args()
    try:
        asyncio.run(run_worker(temporal_address=args.temporal_address))
    except KeyboardInterrupt:
        print("\nWorker stopped.")


if __name__ == "__main__":
    main()
