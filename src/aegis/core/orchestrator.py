"""
Core orchestrator for the Aegis Framework, powered by LangGraph.
"""
import json
import hashlib
import datetime
from typing import List, Dict, Any, TypedDict, Literal, Optional

from langgraph.graph import StateGraph, END

from aegis.core.models import Goal, Plan, Step, LockedPlan
from aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from aegis.adapters.outbound.browser_mcp_adapter import get_browser_adapter

# --- State Definition ---

class AegisState(TypedDict):
    """Represents the state of the Aegis automation graph."""
    run_id: str
    goal: Goal
    plan: Optional[Plan]
    locked_plan: Optional[LockedPlan]
    policy_decision: Optional[Literal["allow", "deny"]]
    human_decision: Optional[Literal["approve", "reject"]]
    execution_log: List[str]
    result: Any

# --- Node Definitions ---

def planner_step(state: AegisState):
    print(">>> In planner_step")
    goal = state['goal']
    
    llm_adapter = get_llm_adapter()
    # In a real scenario, we would construct a more detailed meta-prompt
    plan_steps_dict = llm_adapter.generate_plan(goal.prompt)
    
    plan = Plan(
        run_id=goal.run_id,
        summary=f"Plan for goal: {goal.description}",
        steps=[Step(**s) for s in plan_steps_dict]
    )
    
    print(f"    Generated Plan (run_id: {plan.run_id})")
    return {"plan": plan}

def policy_check_step(state: AegisState):
    print(">>> In policy_check_step")
    plan = state['plan']
    
    # Mock OPA check: In a real system, this would call an OPA server.
    # For now, we'll just check if any step involves a disallowed action.
    # Let's pretend 'extract_data' is allowed but others might not be.
    print("    Submitting plan to OPA for validation...")
    decision = "allow" # Optimistic default
    
    # Example policy: check for allowed domains (simplified)
    for step in plan.steps:
        if step.action == "navigate" and "our-company.com" not in step.url:
            print(f"    OPA Policy Violation: Navigation to non-allowed domain '{step.url}'")
            decision = "deny"
            break
            
    print(f"    OPA Decision: {decision}")
    return {"policy_decision": decision}

def human_approval_step(state: AegisState):
    print(">>> In human_approval_step")
    
    # Mock Human Approval: In a CLI, this would be a real prompt.
    # For now, we auto-approve.
    print("    (Auto-approving plan)")
    decision = "approve"
    
    return {"human_decision": decision}

def plan_locker_step(state: AegisState):
    print(">>> In plan_locker_step")
    plan = state['plan']
    
    # Create a hash of the plan for integrity
    plan_json = plan.model_dump_json()
    plan_hash = hashlib.sha256(plan_json.encode('utf-8')).hexdigest()
    
    locked_plan = LockedPlan(
        **plan.model_dump(),
        plan_hash=f"sha256:{plan_hash}",
        approved_by="user:auto-approver", # Placeholder
        approved_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    
    print(f"    Plan locked with hash: {locked_plan.plan_hash}")
    # In a real system, we would save this to plan.lock.json
    return {"locked_plan": locked_plan}

def executor_step(state: AegisState):
    print(">>> In executor_step")
    log = state.get('execution_log', [])
    plan = state['locked_plan']
    
    browser = get_browser_adapter()

    for i, step in enumerate(plan.steps):
        log.append(f"Executing step {i+1}: {step.model_dump_json()}")
        
        try:
            if step.skill:
                # Skill expansion would happen here. For now, just log it.
                log.append(f"    Expanding and executing skill '{step.skill}'...")
            elif step.action == 'navigate':
                browser.navigate(step.url)
            elif step.action == 'type_text':
                browser.type_text(step.selector, step.text)
            elif step.action == 'click':
                browser.click(step.selector)
            elif step.action == 'wait_for_element':
                browser.wait_for_element(step.selector)
            elif step.action == 'extract_data':
                data = browser.extract_data(step.selector, step.fields, step.limit)
                log.append(f"    Extracted data: {data}")
            else:
                raise ValueError(f"Unknown action: {step.action}")
            log.append(f"    Step {i+1} completed successfully.")
        except Exception as e:
            log.append(f"    ERROR executing step {i+1}: {e}")
            # Stop execution on failure
            return {"execution_log": log, "result": "Workflow failed."}
            
    return {"execution_log": log, "result": "Workflow finished successfully."}

# --- Conditional Edges ---

def should_continue_after_policy(state: AegisState):
    if state["policy_decision"] == "allow":
        return "human_approval"
    return "end"

def should_continue_after_human(state: AegisState):
    if state["human_decision"] == "approve":
        return "locker"
    return "end"

# --- Orchestrator ---

class Orchestrator:
    def __init__(self):
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AegisState)

        # Add nodes
        workflow.add_node("planner", planner_step)
        workflow.add_node("policy_checker", policy_check_step)
        workflow.add_node("human_approval", human_approval_step)
        workflow.add_node("locker", plan_locker_step)
        workflow.add_node("executor", executor_step)

        # Define edges
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "policy_checker")
        workflow.add_conditional_edges(
            "policy_checker",
            should_continue_after_policy,
            {"human_approval": "human_approval", "end": END}
        )
        workflow.add_conditional_edges(
            "human_approval",
            should_continue_after_human,
            {"locker": "locker", "end": END}
        )
        workflow.add_edge("locker", "executor")
        workflow.add_edge("executor", END)

        return workflow.compile()

    def run(self, goal: Goal):
        initial_state = {
            "run_id": goal.run_id,
            "goal": goal,
            "plan": None,
            "locked_plan": None,
            "policy_decision": None,
            "human_decision": None,
            "execution_log": [],
            "result": None,
        }
        return self.workflow.invoke(initial_state)