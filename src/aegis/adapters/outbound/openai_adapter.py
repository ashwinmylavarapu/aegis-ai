import json
from typing import Dict, Any, List
from loguru import logger
import openai

from .base import LLMAdapter

class OpenAIAdapter(LLMAdapter):
    """An LLM adapter that uses the OpenAI API's Tool Calling feature to generate a plan."""

    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("openai", {})
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")
        self.model = llm_config.get("model", "gpt-4o")

        if not api_key:
            raise ValueError("OpenAI config missing 'api_key' in config.yaml")

        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        logger.info(f"OpenAIAdapter initialized for model: {self.model}")
        
        # Define the available actions as tools for the LLM
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "navigate",
                    "description": "Navigates the browser to a specific URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The full URL to navigate to."}
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "type_text",
                    "description": "Types text into an element specified by a CSS selector.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "The CSS selector of the element."},
                            "text": {"type": "string", "description": "The text to type."},
                        },
                        "required": ["selector", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "click",
                    "description": "Clicks an element specified by a CSS selector.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "The CSS selector of the element."}
                        },
                        "required": ["selector"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wait_for_element",
                    "description": "Waits for an element to appear on the page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "The CSS selector to wait for."}
                        },
                        "required": ["selector"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_data",
                    "description": "Extracts structured data from the page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "CSS selector for the list of elements to extract from."},
                            "limit": {"type": "integer", "description": "The maximum number of items to extract."},
                             "fields": {
                                "type": "array", 
                                "items": {"type": "string"},
                                "description": "The names of the data fields to extract."
                            },
                        },
                        "required": ["selector", "limit", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "finish_task",
                    "description": "Call this function with a summary when the user's goal has been fully accomplished.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "A summary of the task outcome."}
                        },
                        "required": ["summary"],
                    },
                },
            },
        ]


    async def generate_plan(self, goal: str, history: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        logger.info(f"Generating next step for goal: '{goal.strip()}'")
        
        system_prompt = (
            "You are an expert AI automation agent. Based on the user's goal and the history of previous actions, "
            "decide on the single next best action to take. When the goal is complete, use the 'finish_task' tool."
        )

        messages = [{"role": "system", "content": system_prompt}]
        
        if not history:
            messages.append({"role": "user", "content": f"The user's goal is: {goal}"})
        else:
            messages.extend(history)


        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto", # Use auto for better compatibility
            )
            
            response_message = response.choices[0].message
            logger.debug(f"OpenAI response: {response_message}")

            steps = []
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    # Ensure arguments are valid JSON before parsing
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in tool call arguments: {tool_call.function.arguments}")
                        continue

                    step = {"action": function_name, **function_args}
                    steps.append(step)
            
            if not steps:
                logger.warning("LLM did not return any tool calls for the given goal.")

            return steps

        except Exception as e:
            logger.error(f"Error calling OpenAI API or parsing response: {e}")
            return []