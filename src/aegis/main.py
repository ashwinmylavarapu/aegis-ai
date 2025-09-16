import asyncio
import yaml
import os
import click
from loguru import logger
import json

from aegis.core.orchestrator import Orchestrator
from aegis.core.models import Goal

def setup_logging(config: dict):
    """
    Sets up a two-tiered logging system based on the config.
    - SUCCESS level logs are for high-level milestones and are formatted cleanly.
    - Other logs (INFO, DEBUG, etc.) are for detailed tracking.
    """
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO").upper()

    logger.remove() # Remove the default handler

    # Add a handler specifically for SUCCESS milestones
    # This will always print, unless the log_level is WARNING or ERROR
    logger.add(
        lambda msg: click.echo(msg, err=True),
        level="SUCCESS",
        format="<green>✅ SUCCESS:</green> <bold>{message}</bold>",
        colorize=True
    )

    # Add a handler for all other levels, controlled by the config file
    logger.add(
        lambda msg: click.echo(msg, err=True),
        level=log_level,
        format="<level>{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}</level>",
        colorize=True,
        # Filter out SUCCESS messages so they aren't printed twice
        filter=lambda record: record["level"].name != "SUCCESS"
    )
    logger.info(f"Logging initialized at level: {log_level}")


def load_config(config_path: str) -> dict:
    """Loads a YAML configuration file and expands environment variables."""
    with open(config_path, 'r') as f:
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
def run(goal_file, config_file):
    """Run a goal from a YAML file."""
    # --- THIS IS THE FIX ---
    # Load config FIRST, then set up logging.
    try:
        config = load_config(config_file)
        setup_logging(config)
        
        logger.info(f"Aegis framework starting to run goal from: {goal_file}")
        
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
                        logger.success(f"Final Outcome: {summary}") # Use SUCCESS for the final outcome
                        # Pretty print the summary if it's a JSON string
                        try:
                            parsed_summary = json.loads(summary)
                            pretty_summary = json.dumps(parsed_summary, indent=2)
                            click.echo(pretty_summary)
                        except (json.JSONDecodeError, TypeError):
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
        raise

if __name__ == "__main__":
    cli()