import asyncio
import json
from typing import Dict, Any

import click
from loguru import logger
import yaml

from aegis.core.models import Goal
from aegis.core.orchestrator import Orchestrator

def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration from a YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_logging(level: str):
    """Configures the logger."""
    logger.remove()
    logger.add(
        "aegis.log",
        level=level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="10 days",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    logger.add(
        lambda msg: click.echo(msg, err=True),
        level=level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

@click.group()
def cli():
    """Aegis AI Automation Framework CLI"""
    pass

@cli.command()
@click.argument('goal_file', type=click.Path(exists=True))
@click.option('--config', 'config_file', type=click.Path(exists=True), default='config.yaml', help='Path to config file.')
def run(goal_file, config_file):
    """Runs the Aegis framework with a given goal."""
    config = load_config(config_file)
    setup_logging(config.get("logging", {}).get("level", "INFO"))

    logger.info(f"Aegis framework starting to run goal from: {goal_file}")

    with open(goal_file, 'r') as f:
        goal_data = yaml.safe_load(f)
    goal = Goal(**goal_data)

    orchestrator = Orchestrator(config=config)
    final_state = asyncio.run(orchestrator.run(goal=goal))

    logger.info("Orchestrator finished.")
    logger.info("--- Final State ---")

    if final_state:
        # Log the final result at the SUCCESS level for clarity
        summary = "Workflow completed, but the agent did not explicitly finish."
        history = final_state.get('history', [])
        if history:
            last_tool_call = history[-1].get('tool_calls', [{}])[0].get('function', {})
            if last_tool_call and last_tool_call.get('name') == 'finish_task':
                args = json.loads(last_tool_call.get('arguments', '{}'))
                summary = args.get('summary', 'No summary provided by agent.')
        logger.success(f"Final Outcome: {summary}")
        
        # Log the full state at DEBUG level for troubleshooting
        for key, value in final_state.items():
            logger.debug(f"- {key}: {value}")
    else:
        logger.error("Workflow did not return a final state.")

if __name__ == '__main__':
    cli()