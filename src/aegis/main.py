import asyncio
import yaml
import os
import click
from loguru import logger
import json

from aegis.core.orchestrator import Orchestrator
from aegis.core.models import Goal

def setup_logging(level="INFO"):
    logger.remove()
    # Using click.echo to ensure logs are visible with the `tee` command
    logger.add(lambda msg: click.echo(msg, err=True), level=level, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")

def load_config(config_path: str) -> dict:
    """Loads a YAML configuration file and expands environment variables."""
    with open(config_path, 'r') as f:
        # Expand environment variables like ${VAR_NAME}
        config_str = os.path.expandvars(f.read())
        return yaml.safe_load(config_str)

def load_goal(goal_path: str) -> Goal:
    """Loads a goal from a YAML file."""
    with open(goal_path, 'r') as f:
        goal_dict = yaml.safe_load(f)
    return Goal(**goal_dict)

@click.group()
def cli():
    """Aegis AI Framework CLI"""
    pass

@cli.command()
@click.argument('goal_file', type=click.Path(exists=True))
@click.option('--config', 'config_file', default='config.yaml', help='Path to the configuration file.')
@click.option('--log-level', default='INFO', help='Set the logging level (e.g., DEBUG, INFO, WARNING).')
def run(goal_file, config_file, log_level):
    """Run a goal from a YAML file."""
    setup_logging(level=log_level.upper())
    logger.info(f"Aegis framework starting to run goal from: {goal_file}")

    try:
        config = load_config(config_file)
        goal = load_goal(goal_file)

        orchestrator = Orchestrator(config=config)
        final_state = asyncio.run(orchestrator.run(goal=goal))

        logger.info("Orchestrator finished.")
        logger.info("--- Final State ---")
        
        if final_state:
            last_ai_turn = next((turn for turn in reversed(final_state.get('history', [])) if turn.get('type') == 'ai'), None)
            
            if last_ai_turn:
                tool_calls = last_ai_turn.get('content', [])
                for call in tool_calls:
                    if call.get('tool_name') == 'finish_task':
                        summary = call.get('tool_args', {}).get('summary', 'No summary provided.')
                        logger.success(f"Final Outcome: {summary}")
                        # Pretty print the summary if it's a JSON string
                        try:
                            parsed_summary = json.loads(summary)
                            pretty_summary = json.dumps(parsed_summary, indent=2)
                            click.echo(pretty_summary)
                        except json.JSONDecodeError:
                            pass # It's just a regular string
                        break
                else:
                    logger.warning("Workflow completed, but the agent did not explicitly call finish_task.")
            else:
                 logger.success("Workflow completed without a final AI turn.")

            debug_state = {k: v for k, v in final_state.items()}
            for key, value in debug_state.items():
                logger.debug(f"- {key}: {value}")
        else:
            logger.error("Workflow did not return a final state.")

    except Exception as e:
        logger.error(f"An unrecoverable error occurred during execution: {e}")
        # Re-raise to ensure the script exits with a non-zero code and shows the full stack trace
        raise

if __name__ == "__main__":
    cli()