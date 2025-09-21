# src/aegis/core/orchestrator.py
import asyncio
import os
from datetime import datetime
import json

from loguru import logger

from aegis.adapters.outbound.browser_adapter_factory import get_browser_adapter
from aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from aegis.adapters.outbound.omni_parser_adapter_factory import (
    get_omni_parser_adapter,
)
from aegis.core.context_manager import ContextManager
from aegis.core.models import AegisContext, Playbook, Step, ToolCall, ToolResponse, Message
from aegis.skills import linkedin

def step_requires_vision(step: Step) -> bool:
    if step.type != "agent_step":
        return False
    prompt_lower = step.prompt.lower().strip()
    non_visual_keywords = ["navigate to", "selector", "wait for", "paste_image", "type_text", "click"]
    return not any(keyword in prompt_lower for keyword in non_visual_keywords)

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.browser_adapter = get_browser_adapter(config)
        self.llm_adapter = get_llm_adapter(config)
        self.omni_parser_adapter = get_omni_parser_adapter(config)
        self.context_manager = ContextManager()

    async def execute_playbook(self, playbook: Playbook):
        aegis_context = self.context_manager.create_context(playbook)
        logger.info(f"Executing playbook: {playbook.name}")
        logger.debug(f"Playbook full definition: {playbook.model_dump_json(indent=2)}")


        for i, step in enumerate(playbook.steps):
            logger.info(f"--- Starting Step {i+1}/{len(playbook.steps)}: '{step.name}' ---")
            aegis_context.current_step = step
            if step.type == "human_intervention":
                self.handle_human_intervention(step)
            elif step.type in ["agent_step", "skill_step"]:
                await self.execute_step(aegis_context, step)
            else:
                logger.warning(f"Unknown step type: {step.type}")
        return aegis_context

    async def execute_step(self, aegis_context: AegisContext, step: Step):
        logger.debug(f"Executing step '{step.name}' of type '{step.type}'")
        if step.type == "skill_step":
            await self.skill_step(step, aegis_context)
            return

        use_vision = step_requires_vision(step)
        logger.debug(f"Step '{step.name}' requires vision: {use_vision}")

        if use_vision:
            logger.info("Vision mode enabled for this step.")
            # ... (vision logic will go here)
        else:
            logger.debug("Bypassing observation for non-visual step.")

        logger.debug(f"Adding user message to context for step '{step.name}':\n{step.prompt}")
        aegis_context.add_message(role="user", content=step.prompt)
        
        logger.debug("Sending context to LLM...")
        response_message = await self.llm_adapter.chat_completion(aegis_context.messages)
        
        logger.debug(f"Received LLM response: {response_message.model_dump_json(indent=2)}")
        aegis_context.messages.append(response_message)

        if response_message.tool_calls:
            await self.handle_tool_calls(response_message.tool_calls, aegis_context)
        else:
            logger.debug("LLM response contained no tool calls.")

    def handle_human_intervention(self, step: Step):
        logger.info(f"Human intervention required: {step.prompt}")
        input("Press Enter to continue...")

    async def skill_step(self, step, aegis_context: AegisContext):
        logger.debug(f"Executing skill '{step.skill_name}.{step.function_name}' with params: {step.params}")
        # ... (actual skill execution logic)
        pass

    async def handle_tool_calls(self, tool_calls: list[ToolCall], aegis_context: AegisContext):
        logger.debug(f"Handling {len(tool_calls)} tool calls...")
        tool_responses = []
        for call in tool_calls:
            logger.debug(f"Executing tool: {call.function_name} with args: {call.function_args}")
            if hasattr(self.browser_adapter, call.function_name):
                tool_function = getattr(self.browser_adapter, call.function_name)
                try:
                    result = await tool_function(**call.function_args)
                    tool_responses.append(
                        ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content=str(result) or "Success")
                    )
                except Exception as e:
                    logger.error(f"Error executing tool '{call.function_name}': {e}")
                    tool_responses.append(
                        ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content=f"Error: {e}")
                    )
            else:
                logger.warning(f"Tool '{call.function_name}' not found in browser adapter.")
                tool_responses.append(
                    ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content="Error: Tool not found")
                )
        
        logger.debug(f"Adding tool responses to context:\n{json.dumps([tr.model_dump() for tr in tool_responses], indent=2)}")
        aegis_context.add_message(role="tool", content="", tool_responses=tool_responses)