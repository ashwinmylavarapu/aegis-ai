from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Action(BaseModel):
    """A single tool call requested by the agent."""
    tool_name: str = Field(..., description="The name of the tool to be executed.")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="The arguments to be passed to the tool.")

class Plan(BaseModel):
    """The agent's plan of action, consisting of one or more tool calls."""
    thoughts: str = Field(..., description="The agent's reasoning and thought process for the current step.")
    actions: List[Action] = Field(..., description="A list of tool calls to be executed.")

class Goal(BaseModel):
    """The user-defined goal for the agent to achieve."""
    run_id: str
    description: str
    prompt: str
    goal_type: str = "natural_language"

# UPDATED: We've added 'completed_steps' to give the agent a persistent memory for each task.
# This prevents looping by reminding the agent what it has already accomplished.
class AgentState(BaseModel):
    goal: Goal
    history: List[Dict[str, Any]] = Field(default_factory=list)
    max_steps: int
    steps_taken: int = 0
    completed_steps: List[str] = Field(default_factory=list) # The new checklist memory