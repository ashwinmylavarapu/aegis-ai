from typing import Dict, Any, List, TypedDict, Annotated
import operator
from loguru import logger
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from .models import Goal
from ..adapters.outbound.browser_adapter_factory import get_browser_adapter
from ..adapters.outbound.llm_adapter_factory import get_llm_adapter
from ..adapters.outbound.opa_client_factory import get_opa_client
from aegis.skills.linkedin import linkedin_login

class AgentState(TypedDict):
    goal: Goal
    history: Annotated[list, operator.add]
    max_steps: int
    steps_taken: int

async def agent_step(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    logger.info("--- AGENT STEP (THINK) ---")
    main_config = config.get("configurable", {})
    llm_adapter = get_llm_adapter(main_config)
    
    plan = await llm_adapter.generate_plan(history=state['history'])
    
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
        
    ai_response = state['history'][-1]
    tool_calls = ai_response.get("content", [])
    
    tool_outputs = []
    for call in tool_calls:
        tool_name = call.get("tool_name")
        tool_args = call.get("tool_args", {})
        
        logger.info(f"Executing tool: '{tool_name}' with args: {tool_args}")
        
        output = await orchestrator_instance.execute_tool(tool_name, tool_args)
        tool_outputs.append({"tool_name": tool_name, "tool_output": str(output)})

    tool_turn = {"type": "tool", "content": tool_outputs}
    return {"history": [tool_turn], "steps_taken": state["steps_taken"] + 1}

def should_continue(state: AgentState) -> str:
    if state["steps_taken"] >= state["max_steps"]:
        logger.warning(f"Max steps ({state['max_steps']}) reached. Halting execution.")
        return "end"
    
    last_turn = state['history'][-1]
    if last_turn['type'] == 'ai':
        for tool_call in last_turn.get('content', []):
            if tool_call.get('tool_name') == 'finish_task':
                logger.success("Goal achieved. `finish_task` was called.")
                return "end"
    
    return "continue"

class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_adapter = get_browser_adapter(config)
        self.opa_client = get_opa_client(config)
        self.skills = {
            "linkedin_login": linkedin_login,
        }
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", agent_step)
        workflow.add_node("tools", tool_step)
        
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "tools",
                "end": END,
            },
        )
        workflow.add_edge("tools", "agent")
        workflow.set_entry_point("agent")
        return workflow.compile()

    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        is_allowed = await self.opa_client.check_policy(input_data={"tool_name": tool_name, "tool_args": tool_args})
        if not is_allowed:
            logger.warning(f"OPA policy denied execution of tool '{tool_name}'")
            return "Execution denied by policy."

        if tool_name in self.skills:
            skill_func = self.skills[tool_name]
            return await skill_func(orchestrator=self, **tool_args)
        
        if hasattr(self.browser_adapter, tool_name):
            method = getattr(self.browser_adapter, tool_name)
            return await method(**tool_args)
        
        logger.error(f"Unknown tool called: {tool_name}")
        return f"Error: Tool '{tool_name}' not found."

    async def run(self, goal: Goal, max_steps: int = 150): # Increased recursion limit
        initial_state = {
            "goal": goal,
            "history": [{"type": "human", "content": goal.prompt}],
            "max_steps": max_steps,
            "steps_taken": 0,
        }
        
        runnable_config = {"configurable": {"orchestrator_instance": self, **self.config}, "recursion_limit": max_steps}
        
        final_state = None
        async for event in self.workflow.astream(initial_state, runnable_config):
            if END in event:
                final_state = event[END]
                break
        
        await self.browser_adapter.close()
        return final_state