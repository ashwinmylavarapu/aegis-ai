# src/aegis/main.py
import asyncio
import sys
from loguru import logger
import yaml

from aegis.core.orchestrator import Orchestrator
from aegis.core.models import Playbook

# Configure logging to intercept standard logging calls
logger.remove()
logger.add(sys.stderr, level="INFO")


async def main():
    """
    Main entry point for the Aegis application.
    Parses command-line arguments to run a specified playbook.
    """
    if len(sys.argv) < 3 or sys.argv[1] != "run":
        print("Usage: python src/aegis/main.py run <path_to_playbook.yaml>")
        sys.exit(1)

    playbook_path = sys.argv[2]
    logger.info(f"Loading playbook from: {playbook_path}")

    # Load configuration
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config.yaml not found. Please ensure it exists in the root directory.")
        return

    # Load the specified playbook
    try:
        with open(playbook_path, "r") as f:
            playbook_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Playbook file not found at: {playbook_path}")
        return

    # Pydantic will validate the structure of the playbook here
    try:
        playbook = Playbook(**playbook_data)
    except Exception as e:
        logger.error(f"Failed to validate playbook '{playbook_path}'. Error: {e}")
        return

    # Initialize and run the orchestrator
    orchestrator = Orchestrator(config)

    # The browser needs to be managed as a context
    async with orchestrator.browser_adapter as browser:
        logger.info("Browser session started.")
        final_context = await orchestrator.execute_playbook(playbook)
        logger.info("Playbook execution finished.")
        # Using logger for structured output
        logger.info(f"Final context messages: {final_context.messages}")


if __name__ == "__main__":
    asyncio.run(main())