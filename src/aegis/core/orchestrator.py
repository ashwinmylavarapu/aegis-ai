# src/aegis/core/orchestrator.py
import asyncio
import os
import json
from loguru import logger
from typing import List
import uuid

from aegis.adapters.outbound.browser_adapter_factory import get_browser_adapter
from aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from aegis.adapters.outbound.omni_parser_adapter_factory import get_omni_parser_adapter
from aegis.core.context_manager import ContextManager
from aegis.core.models import AegisContext, Playbook, Step, ToolCall, ToolResponse, Message

# Import native skills
from aegis.skills import native_keyboard, native_screen_reader

def step_requires_vision(step: Step) -> bool:
    if step.type != "agent_step": return False
    prompt_lower = step.prompt.lower().strip()
    non_visual_keywords = ["navigate to", "selector", "wait for", "paste_image", "type_text", "click", "press_key"]
    return not any(keyword in prompt_lower for keyword in non_visual_keywords)

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.browser_adapter = get_browser_adapter(config)
        self.llm_adapter = get_llm_adapter(config)
        self.omni_parser_adapter = get_omni_parser_adapter(config)
        self.context_manager = ContextManager()
        
        self.skills = {
            "native_keyboard": {
                "press_key_native": native_keyboard.press_key_native,
                "type_text_native": native_keyboard.type_text_native
            },
            "native_screen_reader": {
                "read_screen_content": native_screen_reader.read_screen_content
            }
        }
        logger.info("Orchestrator initialized with native skills.")

    async def execute_playbook(self, playbook: Playbook):
        # --- OBSERVABILITY: Add a unique ID for this entire playbook run ---
        playbook_run_id = f"playbook-run-{uuid.uuid4()}"
        run_log = logger.bind(playbook_run_id=playbook_run_id)
        
        aegis_context = self.context_manager.create_context(playbook)
        
        run_log.info("Starting playbook execution", playbook_name=playbook.name)
        run_log.debug("Playbook definition", definition=playbook.model_dump())
        
        # TRACING: A new trace span for the playbook run would start here.
        # METRICS: Increment a 'playbook_runs_total' counter.
        
        for i, step in enumerate(playbook.steps):
            step_log = run_log.bind(step_name=step.name, step_number=f"{i+1}/{len(playbook.steps)}", step_type=step.type)
            step_log.info("--- Starting Step ---")
            
            aegis_context.current_step = step
            
            # TRACING: A new child span for the step would start here.
            
            if step.type == "human_intervention": self.handle_human_intervention(step, step_log)
            elif step.type == "skill_step": await self.skill_step(step, aegis_context, step_log)
            elif step.type == "agent_step": await self.execute_agent_step(aegis_context, step, step_log)
            else: step_log.warning("Unknown step type detected")

            # --- OBSERVABILITY: Log a snapshot of the agent's memory after each step ---
            step_log.debug("Step completed. Current agent context snapshot.", 
                           context_messages=[msg.model_dump() for msg in aegis_context.messages])
                           
            # TRACING: The step span would end here.
            
        run_log.info("Playbook execution finished successfully.")
        # METRICS: Increment a 'playbook_runs_completed' counter.
        # TRACING: The playbook run span would end here.
        return aegis_context

    async def execute_agent_step(self, aegis_context: AegisContext, step: Step, step_log: logger):
        requires_vision = step_requires_vision(step)
        step_log.debug("Executing agent step", requires_vision=requires_vision)

        if requires_vision:
            # Vision logic would go here
            pass
        else:
            aegis_context.add_message(role="user", content=step.prompt)

        response_message = await self.llm_adapter.chat_completion(aegis_context.messages)
        aegis_context.messages.append(response_message)
        
        if response_message.tool_calls:
            await self.handle_tool_calls(response_message.tool_calls, aegis_context, step_log)
        else:
            step_log.debug("LLM response contained no tool calls.")

    def handle_human_intervention(self, step: Step, step_log: logger):
        step_log.info(f"Human intervention required: {step.prompt}")
        input("Press Enter to continue...")

    async def skill_step(self, step: Step, aegis_context: AegisContext, step_log: logger):
        step_log.debug("Executing skill", skill_name=step.skill_name, function_name=step.function_name, params=step.params)
        try:
            skill_module = self.skills.get(step.skill_name)
            if not skill_module: raise ValueError(f"Skill module '{step.skill_name}' not found.")
            
            skill_function = skill_module.get(step.function_name)
            if not skill_function: raise ValueError(f"Function '{step.function_name}' not found in skill '{step.skill_name}'.")

            result = await skill_function(**(step.params or {}))
            step_log.info("Skill executed successfully.")
            aegis_context.add_message(role="user", content=f"Skill '{step.name}' completed. Result: {result}")

        except Exception as e:
            # --- OBSERVABILITY: Log full context on error ---
            step_log.error("Error executing skill", error=str(e), context_snapshot=[msg.model_dump() for msg in aegis_context.messages])
            aegis_context.add_message(role="user", content=f"Error executing skill '{step.name}': {e}")

    async def handle_tool_calls(self, tool_calls: list[ToolCall], aegis_context: AegisContext, step_log: logger):
        step_log.debug(f"Handling {len(tool_calls)} tool calls.")
        tool_responses = []
        for call in tool_calls:
            call_log = step_log.bind(tool_name=call.function_name, tool_args=call.function_args)
            
            if hasattr(self.browser_adapter, call.function_name):
                tool_function = getattr(self.browser_adapter, call.function_name)
                try:
                    result = await tool_function(**call.function_args)
                    tool_responses.append(ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content=str(result) or "Success"))
                except Exception as e:
                    # --- OBSERVABILITY: Log full context on error ---
                    call_log.error("Error executing tool", error=str(e), context_snapshot=[msg.model_dump() for msg in aegis_context.messages])
                    tool_responses.append(ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content=f"Error: {e}"))
            else:
                call_log.warning("Tool not found in browser adapter.")
                tool_responses.append(ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content="Error: Tool not found"))
        
        aegis_context.add_message(role="tool", content="", tool_responses=tool_responses)