# src/aegis/core/orchestrator.py
import asyncio
import os
from datetime import datetime

from loguru import logger

from aegis.adapters.outbound.browser_adapter_factory import get_browser_adapter
from aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from aegis.adapters.outbound.omni_parser_adapter_factory import (
    get_omni_parser_adapter,
)
from aegis.core.context_manager import ContextManager
from aegis.core.models import AegisContext, Playbook, Step, ToolCall, ToolResponse, Message
from aegis.skills import linkedin


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

        for step in playbook.steps:
            aegis_context.current_step = step
            if step.type == "human_intervention":
                self.handle_human_intervention(step)
            elif step.type == "agent_step":
                await self.agent_step(aegis_context, step)
            elif step.type == "skill_step":
                await self.skill_step(step, aegis_context)
            else:
                logger.warning(f"Unknown step type: {step.type}")
        return aegis_context

    async def agent_step(self, aegis_context: AegisContext, step: Step):
        logger.info(f"Executing agent step: {step.name}")

        screenshot_dir = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_filename = (
            f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        screenshot_path = os.path.join(screenshot_dir, screenshot_filename)

        try:
            await self.browser_adapter.take_screenshot(screenshot_path)
            logger.info(f"Screenshot taken: {screenshot_path}")

            visual_elements = await self.omni_parser_adapter.see_the_page(
                screenshot_path
            )
            logger.info(f"OmniParser identified {len(visual_elements)} elements.")

            if visual_elements:
                visual_prompt_snippet = "\n\n# Visible Elements On Page\n"
                formatted_elements = []
                for el in visual_elements:
                    ocr = f" It contains the text: '{el.get('ocr_text', 'N/A')}'. " if el.get('ocr_text') else ""
                    formatted_elements.append(
                        f"- **{el['element_id']}**: A '{el.get('label')}' described as '{el.get('caption', 'N/A')}'."
                        f"{ocr}"
                        f"Location: {el.get('xyxy')}."
                    )
                visual_prompt_snippet += "\n".join(formatted_elements)
                step.prompt += visual_prompt_snippet
            else:
                logger.warning("No visual elements were detected by OmniParser.")

        except Exception as e:
            logger.error(f"Failed to perform visual analysis: {e}")
            pass

        aegis_context.add_message(role="user", content=step.prompt)
        response_message = await self.llm_adapter.chat_completion(aegis_context.messages)

        # Add the assistant's response (thoughts + tool calls) to context
        aegis_context.messages.append(response_message)

        if response_message.tool_calls:
            await self.handle_tool_calls(response_message.tool_calls, aegis_context)

    def handle_human_intervention(self, step: Step):
        logger.info(f"Human intervention required: {step.prompt}")
        input("Press Enter to continue...")

    async def skill_step(self, step, aegis_context: AegisContext):
        # ... (skill step logic remains the same)
        pass

    async def handle_tool_calls(self, tool_calls: list[ToolCall], aegis_context: AegisContext):
        tool_responses = []
        for tool_call in tool_calls:
            tool_name = tool_call.function_name
            tool_args = tool_call.function_args
            tool_found = False

            if hasattr(self.browser_adapter, tool_name):
                tool_function = getattr(self.browser_adapter, tool_name)
                tool_found = True
            
            if tool_found:
                try:
                    result = await tool_function(**tool_args)
                    tool_responses.append(
                        ToolResponse(
                            tool_call_id=tool_call.id,
                            tool_name=tool_name,
                            content=str(result) if result is not None else "Success",
                        )
                    )
                except Exception as e:
                    logger.error(f"Error executing tool '{tool_name}': {e}")
                    tool_responses.append(
                        ToolResponse(
                            tool_call_id=tool_call.id,
                            tool_name=tool_name,
                            content=f"Error: {e}",
                        )
                    )
            else:
                logger.warning(f"Tool '{tool_name}' not found.")
                tool_responses.append(
                    ToolResponse(
                        tool_call_id=tool_call.id,
                        tool_name=tool_name,
                        content="Error: Tool not found.",
                    )
                )

        # Add all tool responses in a single message to the context.
        # This is the end of the current agent step. The orchestrator loop will now proceed.
        aegis_context.add_message(role="tool", content="", tool_responses=tool_responses)