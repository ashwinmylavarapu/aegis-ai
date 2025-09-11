import click
import yaml
from aegis.core.orchestrator import Orchestrator
from aegis.core.models import Goal

@click.group()
def cli():
    """Aegis Framework CLI"""
    pass

@cli.command()
@click.argument('goal_file', type=click.Path(exists=True))
def run(goal_file: str):
    """Runs an automation goal from a specified YAML file."""
    click.echo(f"Aegis framework starting to run goal from: {goal_file}")

    try:
        with open(goal_file, 'r') as f:
            # PyYAML is already a dependency of uvicorn, so this should work
            goal_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        click.echo(f"Error parsing YAML file: {e}", err=True)
        return

    try:
        # Use the Goal model for validation
        goal = Goal(**goal_data)
    except Exception as e:
        click.echo(f"Error validating goal file content: {e}", err=True)
        return

    orchestrator = Orchestrator()
    final_state = orchestrator.run(goal=goal)

    click.echo("\nOrchestrator finished.")
    click.echo("--- Final State ---")
    for key, value in final_state.items():
        click.echo(f"- {key}: {value}")

if __name__ == '__main__':
    cli()
