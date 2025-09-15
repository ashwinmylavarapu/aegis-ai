from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field
import uuid

class Goal(BaseModel):
    """Represents the initial user goal."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    goal_type: Literal["natural_language"]
    prompt: str

class Step(BaseModel):
    """Represents a single action decided by the agent."""
    action: str
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
    direction: Optional[str] = None
    duration_seconds: Optional[int] = None
    limit: Optional[int] = None
    fields: Optional[Dict[str, str]] = None