# Aegis Framework

## Project Mission & Vision

**Problem:** Production-grade browser automation is often plagued by brittle, non-repeatable, and insecure scripts. Hardcoded logic, changing selectors, and timing issues lead to high maintenance overhead and unreliable operations.

**Mission:** The Aegis Framework aims to solve this by introducing rigor and reliability to the browser automation process. It enforces a strict separation of intent (the "what") from execution (the "how"). An operator declares a goal, and the framework compiles it into an explicit, verifiable, and policy-approved execution plan. This creates an "abstraction firewall," ensuring the automation process is deterministic, observable, and secure by design.

## Core Principles

This framework is a reference implementation of our shared coding ethos, emphasizing:

*   **Security by Default:** A "plan, approve, execute" workflow, enforced by a mandatory Policy-as-Code gate, is the primary defense against unintended actions and prompt injection.
*   **Hexagonal Architecture:** Core logic is isolated from external integrations (CLI, API, LLM, Browser Engine) via swappable "Adapters."
*   **Comprehensive & Pragmatic Testing:** Supplements high unit test coverage with mutation testing for critical logic and integration tests against mock adapters.
*   **Production-Ready Observability:** An unbreakable audit trail is created using a unique `run_id` that correlates OpenTelemetry traces and structured logs across all components.

## Architecture Overview

The Aegis Framework follows a core three-layer architecture: **Goal** → **Planning** → **Approval** → **Execution**.

1.  **Goal (The "What"):** An operator defines a high-level automation objective in a `goal.yaml` file.
2.  **Planning (The "Compiler"):** An AI Decomposer (LLM) converts the natural language goal into a detailed, structured `plan.json` using available "Skills" and "Actions."
3.  **Approval (The "Gate"):** The generated `plan.json` undergoes automated validation by an Open Policy Agent (OPA) and can optionally be subjected to human approval. Only approved plans proceed.
4.  **Execution (The "Runner"):** A locked, immutable `plan.lock.json` is created and executed step-by-step by the Orchestrator, interacting with external systems via adapters.

## Technology Stack

*   **Language:** Python 3.11+
*   **Dependency Management:** `requirements.txt` (using a `.venv` virtual environment)
*   **Orchestration:** LangGraph
*   **Core Logic & State:** Pydantic
*   **CLI/API Adapters:** Click / FastAPI
*   **Testing:** Pytest, mutmut
*   **Policy Engine:** Open Policy Agent (OPA)
*   **Browser Interaction:** BrowserMCP Server (Node.js application) via `fastmcp` (Python client library)

## Directory Structure

The project adheres closely to the proposed structure from the architecture document:

```
/aegis-framework
├── config.yaml             # Example configuration (example_config.yaml)
├── requirements.txt        # Python dependencies
├── skills/                 # Placeholder for skill definitions
│   └── *.skill.yaml
├── src/
│   └── aegis/
│       ├── core/
│       │   ├── orchestrator.py   # Main orchestration logic
│       │   └── agents/           # Planner agent logic
│       ├── adapters/
│       │   ├── inbound/
│       │   │   ├── cli.py        # CLI adapter
│       │   │   └── api/          # API adapter
│       │   └── outbound/
│       │       ├── browser_mcp_adapter.py # Browser interaction adapter
│       │       └── llm_adapter_factory.py # LLM integration
│       └── main.py             # CLI entry point
│       └── policy/             # OPA policies
│           └── allow.rego
└── tests/                  # Unit and integration tests
```

## Current Status & Progress

The core framework is set up, and significant progress has been made on integrating the BrowserMCP.

*   **Initial Setup:** Project structure and basic components are in place.
*   **Dependency Management:** All Python dependencies from `requirements.txt` are successfully installed within the `.venv` virtual environment. `fastmcp` is confirmed to be installed and used.
*   **Core Orchestrator:** The LangGraph-based orchestrator runs successfully through the planning, policy check, and human approval (auto-approved for now) stages.
*   **Browser Adapter Refactoring:** The `browser_mcp_adapter.py` has been refactored to use `fastmcp.Client` for asynchronous communication with the BrowserMCP server. All browser interaction methods are now `async`.
*   **Asynchronous Execution:** The entire orchestration flow (`main.py`, `orchestrator.py`, `browser_mcp_adapter.py`) has been updated to support `asyncio`.

**Current Challenge:**

The `fastmcp.Client` is failing to connect to the BrowserMCP server with the error: `Client failed to connect: All connection attempts failed`.

*   **Debugging Step Taken:** The `_start_server` method in `browser_mcp_adapter.py` has been modified to print the `stdout` and `stderr` of the `npx @browsermcp/mcp@latest` process. This is crucial for identifying the actual port/URL the BrowserMCP server is listening on or any startup errors it might be encountering. The `asyncio.sleep` duration before attempting connection has also been increased to 10 seconds.

## Next Steps

The immediate next steps are focused on resolving the BrowserMCP connection issue and then proceeding with the full implementation of the automation flow:

1.  **Analyze BrowserMCP Server Output:** Run the application and carefully examine the `BrowserMCP Server STDOUT` and `BrowserMCP Server STDERR` logs. This output will reveal:
    *   The exact URL and port the BrowserMCP server is listening on.
    *   Any errors or warnings during the BrowserMCP server's startup.
2.  **Adjust BrowserMCP Connection:** Based on the server output, update the `url` in the `config` dictionary within `browser_mcp_adapter.py` to the correct address and protocol (e.g., `http://localhost:XXXX/mcp/` or `ws://localhost:XXXX`).
3.  **Verify Browser Interaction:** Once connected, ensure that `navigate`, `type_text`, `click`, `wait_for_element`, and `extract_data` methods correctly interact with a browser instance.
4.  **Implement `internal_auth.login` Skill:** Develop the actual logic for the `internal_auth.login` skill, which is currently a placeholder.
5.  **Integrate OPA:** Fully integrate Open Policy Agent for robust policy enforcement on generated plans.
6.  **Full Observability:** Implement comprehensive OpenTelemetry tracing and structured logging across all components.
7.  **Testing:** Develop and integrate unit, mutation, and integration tests as per the core principles.

## How to Run

To set up and run the Aegis Framework:

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd aegis-framework
    ```
2.  **Create and activate virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the application:**
    ```bash
    PYTHONPATH=src .venv/bin/python src/aegis/main.py run goal.yaml
    ```
    *(Note: The `goal.yaml` file defines the automation task to be executed.)*