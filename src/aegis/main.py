import click
import yaml
import asyncio
import sys
from loguru import logger
from aegis.core.orchestrator import Orchestrator
from aegis.core.models import Goal

# --- Config Loading & Logger Setup ---

def load_config():
    """Loads config.yaml"""
    try:
        with open("config.yaml", 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("config.yaml not found, using default settings.")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")
        return {}

config = load_config()

# Configure Loguru for rich, structured logging
log_level = config.get("logging", {}).get("level", "INFO")
logger.remove() # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    level=log_level,
    enqueue=True, # Make logging async-safe
    backtrace=True, # Show full stack trace on exceptions
    diagnose=True # Add exception values
)



@click.group()
def cli():
    """Aegis Framework CLI"""
    pass

@cli.command()
@click.argument('goal_file', type=click.Path(exists=True))
def run(goal_file: str):
    """Runs an automation goal from a specified YAML file."""
    logger.info(f"Aegis framework starting to run goal from: {goal_file}")

    try:
        with open(goal_file, 'r') as f:
            goal_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        return

    try:
        goal = Goal(**goal_data)
    except Exception as e:
        logger.error(f"Error validating goal file content: {e}")
        return

    orchestrator = Orchestrator(config=config)
    final_state = asyncio.run(orchestrator.run(goal=goal))

    logger.info("Orchestrator finished.")
    logger.info("--- Final State ---")
    for key, value in final_state.items():
        logger.info(f"- {key}: {value}")

if __name__ == '__main__':
    cli()