"""Temporal worker for Minesweeper game."""
import asyncio
import logging
from temporalio.worker import Worker
from src.workflows import MinesweeperWorkflow
from src import activities
from src.client_provider import get_temporal_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start the Temporal worker."""
    # Connect to Temporal server
    client = await get_temporal_client()

    # Create worker
    worker = Worker(
        client,
        task_queue="minesweeper-task-queue",
        workflows=[MinesweeperWorkflow],
        activities=[
            activities.create_game_board,
            activities.reveal_cell,
            activities.toggle_flag,
            activities.chord_reveal,
        ],
    )

    logger.info("Worker started, connected to Temporal")
    logger.info("Listening on task queue: minesweeper-task-queue")

    # Run the worker
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
