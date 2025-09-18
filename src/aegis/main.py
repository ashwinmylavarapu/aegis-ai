import asyncio
import yaml
import click
from loguru import logger
from typing import Dict, Any

# REFACTORED: Import the Orchestrator class instead of get_graph
from aegis.core.orchestrator import Orchestrator

# The main async function is now a simple wrapper
async def run_goal(goal_path: str, config: Dict[str, Any]):
    """
    Loads goal data, instantiates the orchestrator, and runs the goal.
    """
    try:
        with open(goal_path, 'r') as f:
            goal_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Goal file not found at path: {goal_path}")
        return
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML from goal file: {e}")
        return
    
    # Create an instance of the orchestrator
    orchestrator = Orchestrator(config)
    # Run the goal, which now contains the task-looping logic
    await orchestrator.run(goal_data)

@click.group()
def cli():
    """Aegis Framework CLI"""
    pass

@cli.command()
@click.argument('goal_file', type=click.Path(exists=True))
def run(goal_file: str):
    """

    Loads configuration and runs an automation goal.
    """
    logger.info("Loading configuration...")
    try:
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config.yaml not found. Please create it from the example.")
        return
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")
        return

    logger.info("Configuration loaded. Starting goal execution.")
    asyncio.run(run_goal(goal_file, config))

if __name__ == "__main__":
    cli()