# src/aegis/core/context_manager.py
from typing import Dict
from loguru import logger

from .models import AegisContext, Playbook, Message

class ContextManager:
    """
    Manages the runtime context for playbook executions.
    """
    _contexts: Dict[str, AegisContext] = {}

    def create_context(self, playbook: Playbook) -> AegisContext:
        """
        Creates a new AegisContext for a given playbook.
        """
        # Using playbook name as a simple key for this context
        context_key = playbook.name
        logger.info(f"Creating new context for playbook: '{context_key}'")

        # Initialize with the system message from the playbook's persona
        initial_message = Message(role="system", content=playbook.persona)
        
        aegis_context = AegisContext(
            playbook=playbook,
            messages=[initial_message]
        )
        
        self._contexts[context_key] = aegis_context
        return aegis_context

    def get_context(self, context_key: str) -> AegisContext:
        """
        Retrieves an existing context by its key.
        """
        if context_key not in self._contexts:
            raise ValueError(f"Context for key '{context_key}' not found.")
        return self._contexts[context_key]

    def clear_context(self, context_key: str):
        """
        Clears a context from the manager.
        """
        if context_key in self._contexts:
            del self._contexts[context_key]
            logger.info(f"Context for key '{context_key}' cleared.")