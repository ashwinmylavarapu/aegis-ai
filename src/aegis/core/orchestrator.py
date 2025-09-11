import json
from typing import List, Dict, Any, TypedDict
from loguru import logger
from langgraph.graph import StateGraph, END

from aegis.core.models import Goal
from aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from aegis.adapters.outbound.browser_adapter_factory import get_browser_adapter

class AegisState(TypedDict):
    run_id: str
    goal: Goal
    config: Dict[str, Any]
    history: List[Dict[str, Any]]
    result: str

async def agent_step(state: AegisState):
    logger.info("--- AGENT STEP (THINK) ---")
    goal, config, history = state['goal'], state['config'], state.get('history', [])
    llm_adapter = get_llm_adapter(config)
    next_steps = await llm_adapter.generate_plan(goal.prompt, history)
    if not next_steps:
        logger.warning("Agent proposed no action. Finishing.")
        next_steps = [{"action": "finish_task", "summary": "Agent finished: No further action proposed."}]
    next_action = next_steps[0]
    history.append({"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{len(history)}", "function": {"name": next_action['action'], "arguments": json.dumps({k: v for k, v in next_action.items() if k != 'action'})}, "type": "function"}]})
    return {"history": history}

async def executor_step(state: AegisState):
    logger.info("--- EXECUTOR STEP (ACT) ---")
    config, history = state['config'], state['history']
    action_to_execute = history[-1]['tool_calls'][0]['function']
    action_name = action_to_execute['name']
    args = json.loads(action_to_execute['arguments'])
    
    logger.info(f"Executing action: {action_name} with args {args}")
    browser, observation = get_browser_adapter(config), ""
    
    try:
        if action_name == 'navigate': await browser.navigate(args['url'])
        elif action_name == 'type_text': await browser.type_text(args['selector'], args['text'])
        elif action_name == 'press_key': await browser.press_key(args['selector'], args['key'])
        elif action_name == 'click': await browser.click(args['selector'])
        elif action_name == 'get_page_content': observation = await browser.get_page_content()
        elif action_name == 'wait': await browser.wait(args['duration_seconds'])
        elif action_name == 'scroll': await browser.scroll(args['direction'])
        
        if not observation: observation = f"Action '{action_name}' completed successfully."
    except Exception as e:
        logger.error(f"Error executing action '{action_name}': {e}", exc_info=True)
        observation = f"Error executing action '{action_name}': {e}"
    
    history.append({"role": "tool", "name": action_name, "content": observation, "tool_call_id": f"call_{len(history)-1}"})
    return {"history": history}

def should_continue(state: AegisState):
    if not state.get('history'): return "agent"
    last_message = state['history'][-1]
    if last_message.get("role") == "assistant":
        return END if last_message['tool_calls'][0]['function']['name'] == 'finish_task' else "executor"
    return "agent"

class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.workflow = self._build_graph()
        self.browser_adapter = get_browser_adapter(config)

    def _build_graph(self):
        workflow = StateGraph(AegisState)
        workflow.add_node("agent", agent_step)
        workflow.add_node("executor", executor_step)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue, {"executor": "executor", END: END})
        workflow.add_edge("executor", "agent")
        return workflow.compile()

    async def run(self, goal: Goal):
        initial_state = {"run_id": goal.run_id, "goal": goal, "config": self.config, "history": [], "result": None}
        final_state = initial_state
        try:
            await self.browser_adapter.connect()
            async for event in self.workflow.astream(initial_state, {"recursion_limit": 100}):
                logger.debug(f"Workflow event: {event}")
                if "agent" in event: final_state = event["agent"]
                if "executor" in event: final_state = event["executor"]
                if END in event: final_state = event[END]; break
        finally:
            await self.browser_adapter.close()
        return final_state