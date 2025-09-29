# src/aegis/core/orchestrator.py
import asyncio
import os
import json
from loguru import logger
from typing import List, Dict, Any
import uuid
import copy

from aegis.adapters.outbound.browser_adapter_factory import get_browser_adapter
from aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from aegis.adapters.outbound.omni_parser_adapter_factory import get_omni_parser_adapter
from aegis.adapters.outbound.native_os_adapter_factory import get_native_os_adapter
from aegis.core.context_manager import ContextManager
from aegis.core.models import AegisContext, Playbook, Step, ToolCall, ToolResponse, Message
from aegis.core.models import substitute_params

def step_requires_vision(step: Step) -> bool:
    if step.type != "agent_step": return False
    prompt_lower = step.prompt.lower().strip()
    non_visual_keywords = ["navigate to", "selector", "wait for", "paste_image", "type_text", "click", "press_key"]
    return not any(keyword in prompt_lower for keyword in non_visual_keywords)

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.browser_adapter = get_browser_adapter(config)
        self.omni_parser_adapter = get_omni_parser_adapter(config)
        self.native_os_adapter = get_native_os_adapter(config)
        
        self.tool_dispatch_map, all_tool_definitions = self._build_tool_registries()
        
        self.llm_adapter = get_llm_adapter(config, tools=all_tool_definitions)
        
        self.context_manager = ContextManager()
        logger.info("Orchestrator initialized with all adapters and unified tool registry.")

    def _build_tool_registries(self) -> (Dict[str, Any], List[Dict[str, Any]]):
        """Creates a dispatch map and a list of tool definitions for the LLM."""
        dispatch_map = {}
        definitions = []

        # Aggregate from all adapters that have a get_tools method
        adapters_with_tools = [self.browser_adapter, self.native_os_adapter]
        
        for adapter in adapters_with_tools:
            if hasattr(adapter, 'get_tools') and callable(getattr(adapter, 'get_tools')):
                adapter_tools = adapter.get_tools()
                definitions.extend(adapter_tools)
                for tool in adapter_tools:
                    dispatch_map[tool['name']] = adapter
        
        logger.info(f"Built tool registry with {len(definitions)} tools.")
        logger.debug(f"Available tools: {list(dispatch_map.keys())}")
        return dispatch_map, definitions

    async def execute_playbook(self, playbook: Playbook):
        playbook_run_id = f"playbook-run-{uuid.uuid4()}"
        run_log = logger.bind(playbook_run_id=playbook_run_id)
        
        aegis_context = self.context_manager.create_context(playbook)
        
        run_log.info("Starting playbook execution", playbook_name=playbook.name)
        run_log.debug("Playbook definition", definition=playbook.model_dump())
        
        for i, step in enumerate(playbook.steps):
            await self.execute_step(step, aegis_context, run_log, step_number=f"{i+1}/{len(playbook.steps)}")

        run_log.info("Playbook execution finished successfully.")
        return aegis_context

    async def execute_step(self, step: Step, aegis_context: AegisContext, run_log: logger, step_number: str = "N/A"):
        """Recursive function to execute a single step or a routine."""
        step_log = run_log.bind(step_name=step.name, step_number=step_number, step_type=step.type)
        step_log.info("--- Starting Step ---")
        
        aegis_context.current_step = step
        
        if step.type == "human_intervention": self.handle_human_intervention(step, step_log)
        elif step.type == "skill_step": await self.execute_skill_step(step, aegis_context, step_log)
        elif step.type == "agent_step": await self.execute_agent_step(aegis_context, step, step_log)
        elif step.type == "run_routine": await self.execute_routine(step, aegis_context, step_log)
        else: step_log.warning("Unknown step type detected")

        step_log.debug("Step completed. Current agent context snapshot.", 
                       context_messages=[msg.model_dump(exclude_none=True) for msg in aegis_context.messages])

    async def execute_routine(self, step: Step, aegis_context: AegisContext, step_log: logger):
        """Handles the execution of a routine, including looping."""
        if not step.routine_name or not aegis_context.playbook.routines or step.routine_name not in aegis_context.playbook.routines:
            step_log.error(f"Routine '{step.routine_name}' not found in playbook definitions.")
            return

        routine_template = aegis_context.playbook.routines[step.routine_name]
        param_sets = step.loop_with if step.loop_with else [{}]

        for i, params in enumerate(param_sets):
            loop_log = step_log.bind(loop_iteration=f"{i+1}/{len(param_sets)}", loop_params=params)
            loop_log.info(f"Running routine '{step.routine_name}'")
            
            for j, routine_step_template in enumerate(routine_template):
                step_instance_data = routine_step_template.model_dump()
                substituted_data = substitute_params(step_instance_data, params)
                step_instance = Step(**substituted_data)
                await self.execute_step(step_instance, aegis_context, loop_log, step_number=f"Routine Step {j+1}/{len(routine_template)}")

    async def execute_agent_step(self, aegis_context: AegisContext, step: Step, step_log: logger):
        requires_vision = step_requires_vision(step)
        step_log.debug("Executing agent step", requires_vision=requires_vision)

        if requires_vision:
            pass # Vision logic remains the same
        else:
            aegis_context.messages.append(Message(role="user", content=step.prompt))

        response_message = await self.llm_adapter.chat_completion(aegis_context.messages)
        aegis_context.messages.append(response_message)
        
        if response_message.tool_calls:
            await self.handle_tool_calls(response_message.tool_calls, aegis_context, step_log)
        else:
            step_log.debug("LLM response contained no tool calls.")

    def handle_human_intervention(self, step: Step, step_log: logger):
        step_log.info(f"Human intervention required: {step.prompt}")
        input("Press Enter to continue...")

    async def execute_skill_step(self, step: Step, aegis_context: AegisContext, step_log: logger):
        step_log.debug("Executing skill", adapter_name=step.skill_name, function_name=step.function_name, params=step.params)
        
        adapter = self.tool_dispatch_map.get(step.function_name)

        if not adapter or not hasattr(adapter, step.function_name):
            error_msg = f"Function '{step.function_name}' not found in any registered adapter."
            step_log.error(error_msg)
            aegis_context.messages.append(Message(role="user", content=f"Error: {error_msg}"))
            return

        try:
            skill_function = getattr(adapter, step.function_name)
            result = await skill_function(**(step.params or {}))
            step_log.info("Skill executed successfully.")
            aegis_context.messages.append(Message(role="user", content=f"Skill '{step.name}' completed. Result: {json.dumps(result) if isinstance(result, dict) else result}"))
        except Exception as e:
            step_log.error("Error executing skill", error=str(e))
            aegis_context.messages.append(Message(role="user", content=f"Error executing skill '{step.name}': {e}"))
            
    async def handle_tool_calls(self, tool_calls: list[ToolCall], aegis_context: AegisContext, step_log: logger):
        step_log.debug(f"Handling {len(tool_calls)} tool calls.")
        tool_responses = []
        
        for call in tool_calls:
            call_log = step_log.bind(tool_name=call.function_name, tool_args=call.function_args)
            
            adapter = self.tool_dispatch_map.get(call.function_name)
            
            if adapter and hasattr(adapter, call.function_name):
                tool_function = getattr(adapter, call.function_name)
                try:
                    result = await tool_function(**call.function_args)
                    tool_responses.append(ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content=json.dumps(result) if isinstance(result, dict) else str(result) or "Success"))
                except Exception as e:
                    call_log.error("Error executing tool", error=str(e))
                    tool_responses.append(ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content=f"Error: {e}"))
            else:
                call_log.warning(f"Tool '{call.function_name}' not found in any adapter.")
                tool_responses.append(ToolResponse(tool_call_id=call.id, tool_name=call.function_name, content="Error: Tool not found"))
        
        if aegis_context.messages and aegis_context.messages[-1].role == "assistant":
            aegis_context.messages[-1].tool_responses = tool_responses
        else:
            logger.error("Could not find a preceding assistant message to attach tool responses to.")
            aegis_context.messages.append(Message(role="tool", tool_responses=tool_responses))