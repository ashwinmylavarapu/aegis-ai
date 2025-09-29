"""
Aegis Developer Tools - Main CLI Entry Point.
This script orchestrates the different toolsets like 'playbook' and 'skills'.
"""
import typer
from . import playbook_ops, skill_ops

# Create the main Typer application instance
app = typer.Typer(
    name="aegis-tools",
    help="A suite of developer joy tools for the Aegis Automation Framework.",
    add_completion=False
)

# Add the subcommand groups from other modules
app.add_typer(playbook_ops.app, name="playbook", help="Commands for creating and validating playbooks.")
app.add_typer(skill_ops.app, name="skills", help="Commands for discovering available agent skills.")

if __name__ == "__main__":
    app()