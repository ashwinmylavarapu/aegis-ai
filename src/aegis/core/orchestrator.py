from typing import Dict, Any, List, TypedDict, Annotated
import operator
import json
from loguru import logger
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from .models import Goal
from ..adapters.outbound.browser_adapter_factory import get_browser_adapter
from ..adapters.outbound.llm_adapter_factory import get_llm_adapter
from ..adapters.outbound.opa_client_factory import get_opa_client
from aegis.skills.linkedin import linkedin_login
from aegis.skills.batch_processing import process_posts_in_batches
from aegis.skills.activity_processing import process_activity_posts_in_batches
from aegis.core.context_manager import ContextManager


class AgentState(TypedDict):
    goal: Goal
    history: Annotated[list, operator.add]
    max_steps: int
    steps_taken: int


async def agent_step(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    logger.info("--- AGENT STEP (THINK) ---")
    main_config = config.get("configurable", {})
    llm_adapter = get_llm_adapter(main_config)

    context_manager_config = main_config.get("context_management", {})
    context_manager = ContextManager(
        max_history_items=context_manager_config.get("max_history_items", 10),
        max_tool_output_tokens=context_manager_config.get("max_tool_output_tokens", 2000),
    )
    managed_history = context_manager.manage(state['history'])
    logger.info(f"Managed history has {len(managed_history)} items.")

    plan = await llm_adapter.generate_plan(history=managed_history)

    if not plan:
        logger.warning("Agent returned an empty plan. Ending execution.")
        return {"steps_taken": state["steps_taken"] + 1}

    ai_turn = {"type": "ai", "content": plan}
    return {"history": [ai_turn], "steps_taken": state["steps_taken"] + 1}


async def tool_step(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    logger.info("--- TOOL STEP (ACT) ---")
    main_config = config.get("configurable", {})
    orchestrator_instance = main_config.get("orchestrator_instance")
    if not orchestrator_instance:
        raise ValueError("Orchestrator instance not found in config.")

    context_manager_config = main_config.get("context_management", {})
    context_manager = ContextManager(
        max_history_items=context_manager_config.get("max_history_items", 10),
        max_tool_output_tokens=context_manager_config.get("max_tool_output_tokens", 2000),
    )

    ai_response = state['history'][-1]
    tool_calls = ai_response.get("content", [])

    tool_outputs = []
    for call in tool_calls:
        tool_name = call.get("tool_name")
        tool_args = call.get("tool_args", {})

        logger.success(f"Executing tool: '{tool_name}' with args: {tool_args}")

        output = await orchestrator_instance.execute_tool(tool_name, tool_args)

        if isinstance(output, str):
            truncated_output = context_manager._truncate_content(output)
        else:
            truncated_output = context_manager._truncate_content(json.dumps(output))

        tool_outputs.append({"tool_name": tool_name, "tool_output": truncated_output})

    tool_turn = {"type": "tool", "content": tool_outputs}
    return {"history": [tool_turn]}


def should_continue(state: AgentState) -> str:
    if state["steps_taken"] >= state["max_steps"]:
        logger.warning(f"Max steps ({state['max_steps']}) reached. Halting execution.")
        return "end"

    last_turn = state['history'][-1]
    if last_turn['type'] == 'ai':
        for tool_call in last_turn.get('content', []):
            if tool_call.get('tool_name') == 'finish_task':
                logger.success("Task complete. `finish_task` was called.")
                return "end"

    return "continue"


class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_adapter = get_browser_adapter(config)
        self.opa_client = get_opa_client(config)
        self.skills = {
            "linkedin_login": linkedin_login,
            "process_posts_in_batches": process_posts_in_batches,
            "process_activity_posts_in_batches": process_activity_posts_in_batches,
        }
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", agent_step)
        workflow.add_node("tools", tool_step)
        workflow.add_conditional_edges("agent", should_continue, {"continue": "tools", "end": END})
        workflow.add_edge("tools", "agent")
        workflow.set_entry_point("agent")
        return workflow.compile()

    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        if tool_name in self.skills:
            skill_func = self.skills[tool_name]
            return await skill_func(orchestrator=self, **tool_args)
        
        if hasattr(self.browser_adapter, tool_name):
            method = getattr(self.browser_adapter, tool_name)
            return await method(**tool_args)
        
        logger.error(f"Unknown tool called: {tool_name}")
        return f"Error: Tool '{tool_name}' not found."

    async def run(self, goal_data: Dict[str, Any], max_steps_per_task: int = 50):
        run_id = goal_data.get('run_id', 'not_defined')
        logger.info(f"--- STARTING GOAL: {run_id} ---")

        await self.browser_adapter.connect()

        tasks = goal_data.get("tasks", [])
        if not tasks:
            logger.warning("No tasks found in the goal file. Nothing to execute.")

        for i, task in enumerate(tasks):
            task_name = task.get("name", f"Task {i+1}")
            task_prompt = task.get("prompt")
            if not task_prompt:
                logger.warning(f"Task '{task_name}' is missing a 'prompt'. Skipping.")
                continue

            logger.info(f"--- EXECUTING TASK ({i+1}/{len(tasks)}): {task_name} ---")

            # FIXED: Added the required 'goal_type' field.
            task_goal = Goal(run_id=f"{run_id}_{i+1}", description=task_name, prompt=task_prompt, goal_type="natural_language")

            initial_state = {
                "goal": task_goal,
                "history": [{"type": "human", "content": task_goal.prompt}],
                "max_steps": max_steps_per_task,
                "steps_taken": 0,
            }
            
            runnable_config = {"configurable": {"orchestrator_instance": self, **self.config}, "recursion_limit": max_steps_per_task}
            
            async for event in self.workflow.astream(initial_state, runnable_config):
                pass
            
            logger.success(f"--- COMPLETED TASK: {task_name} ---")

        await self.browser_adapter.close()
        logger.success(f"--- GOAL FINISHED: {run_id} ---")