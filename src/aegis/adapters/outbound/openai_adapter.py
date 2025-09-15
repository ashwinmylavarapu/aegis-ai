import json
from typing import Dict, Any, List
from loguru import logger
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import LLMAdapter

class OpenAIAdapter(LLMAdapter):
    """An LLM adapter that uses the OpenAI API."""

    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("openai", {})
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")  # For OpenAI-compliant proxies
        self.model = llm_config.get("model", "gpt-4o")

        if not api_key:
            raise ValueError("OpenAI config missing 'api_key' in config.yaml")

        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        logger.info(f"OpenAIAdapter initialized for model: {self.model}")

        # Define the available actions as tools for the LLM
        self.tools = [
            {"type": "function", "function": {"name": "get_page_content", "description": "Gets a simplified summary of the page's interactive elements."}},
            {"type": "function", "function": {"name": "navigate", "description": "Navigates to a URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "type_text", "description": "Types text into an element.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}}},
            {"type": "function", "function": {"name": "click", "description": "Clicks an element.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
            {"type": "function", "function": {"name": "press_key", "description": "Presses a key on an element.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "key": {"type": "string"}}, "required": ["selector", "key"]}}},
            {"type": "function", "function": {"name": "wait", "description": "Pauses execution for a specified number of seconds.", "parameters": {"type": "object", "properties": {"duration_seconds": {"type": "integer"}}, "required": ["duration_seconds"]}}},
            {"type": "function", "function": {"name": "scroll", "description": "Scrolls the page.", "parameters": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]}}, "required": ["direction"]}}},
            {"type": "function", "function": {"name": "extract_data", "description": "Extracts data from a list of elements.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "limit": {"type": "integer"}, "fields": {"type": "object", "description": "A dictionary where keys are field names and values are CSS selectors."}}}}},
            {"type": "function", "function": {"name": "finish_task", "description": "Call when the goal is accomplished.", "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
        ]
        
        self.system_instruction = (
            "You are an expert AI web automation agent. You operate in a 'Look, Think, Act' cycle. "
            "1. **Look**: Always use `get_page_content` to understand the page. "
            "2. **Think**: Based on the content and goal, decide the next action and construct a precise CSS selector. "
            "3. **Act**: Execute the tool (`type_text`, `click`, etc.). "
            "**Strategy**: For long tasks like image generation, you MUST use the `wait` tool to pause. For feeds, you MUST use `scroll`. "
            "If an action fails, use `get_page_content` again to re-evaluate. When the goal is complete, use `finish_task`."
        )

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def generate_plan(self, goal: str, history: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        logger.info(f"Generating next step for goal: '{goal.strip()}'")
        
        messages = [{"role": "system", "content": self.system_instruction}]
        if not history:
            messages.append({"role": "user", "content": goal})
        else:
            messages.extend(history)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message
            logger.debug(f"OpenAI response: {response_message}")
            
            steps = []
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    steps.append({"action": function_name, **function_args})
            
            return steps
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise