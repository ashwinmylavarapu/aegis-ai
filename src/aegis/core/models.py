# src/aegis/core/models.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json


class ToolCall(BaseModel):
    """Represents a tool call from the LLM."""
    id: str
    function_name: str
    function_args: Dict[str, Any]

class ToolResponse(BaseModel):
    """Represents the response from a tool execution."""
    tool_call_id: str
    tool_name: str
    content: str

class Message(BaseModel):
    """Represents a single message in the chat history."""
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_responses: Optional[List[ToolResponse]] = None

class Step(BaseModel):
    """A single step within a playbook."""
    name: str
    type: str
    prompt: Optional[str] = None
    skill_name: Optional[str] = None
    function_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    routine_name: Optional[str] = None
    loop_with: Optional[List[Dict[str, Any]]] = None

class Playbook(BaseModel):
    """A playbook containing a series of steps for the agent to execute."""
    name: str
    description: str
    persona: str
    steps: List[Step]
    routines: Optional[Dict[str, List[Step]]] = None

class AegisContext(BaseModel):
    """The runtime context for a playbook execution."""
    playbook: Playbook
    messages: List[Message] = Field(default_factory=list)
    current_step: Optional[Step] = None

    def add_message(self, role: str, content: str, tool_responses: Optional[List[ToolResponse]] = None):
        """
        Adds a message to the context's history.
        """
        self.messages.append(
            Message(role=role, content=content, tool_responses=tool_responses)
        )

def substitute_params(data: Any, params: Dict[str, Any]) -> Any:
    """Recursively substitutes placeholders in a nested data structure."""
    if isinstance(data, str):
        for key, value in params.items():
            placeholder = f"{{{{params.{key}}}}}"
            data = data.replace(placeholder, str(value))
        return data
    elif isinstance(data, dict):
        return {k: substitute_params(v, params) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute_params(item, params) for item in data]
    else:
        return data