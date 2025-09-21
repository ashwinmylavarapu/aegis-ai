# src/aegis/main.py
import asyncio
import sys
import yaml
from loguru import logger

from aegis.core.orchestrator import Orchestrator
from aegis.core.models import Playbook


def setup_logging(config: dict):
    """Configures the logging level based on the config file."""
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO").upper()
    
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=log_level)
    logger.info(f"Logging initialized with level: {log_level}")


async def main():
    """Main entry point for the Aegis application."""
    if len(sys.argv) < 3 or sys.argv[1] != "run":
        print("Usage: python src/aegis/main.py run <path_to_playbook.yaml>")
        sys.exit(1)

    playbook_path = sys.argv[2]
    
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        # Use a basic logger for this critical error
        logger.error("config.yaml not found. Please ensure it exists.")
        return

    # Setup logging as the very first step
    setup_logging(config)

    logger.info(f"Loading playbook from: {playbook_path}")
    try:
        with open(playbook_path, "r") as f:
            playbook_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Playbook file not found at: {playbook_path}")
        return

    try:
        playbook = Playbook(**playbook_data)
    except Exception as e:
        logger.error(f"Failed to validate playbook '{playbook_path}'. Error: {e}")
        return

    orchestrator = Orchestrator(config)

    async with orchestrator.browser_adapter as browser:
        logger.info("Browser session started.")
        final_context = await orchestrator.execute_playbook(playbook)
        logger.info("Playbook execution finished.")
        logger.debug(f"Final context messages: {final_context.messages}")


if __name__ == "__main__":
    asyncio.run(main())