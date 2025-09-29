# Aegis Automation Framework

A resilient, adaptive agent for robust UI automation, now with visual intelligence.

---

## 1. The "Why": The Big Picture

### The Problem: Brittle UI Automation
Traditional UI automation is fundamentally fragile. Scripts are tightly coupled to the Document Object Model (DOM) through CSS selectors and XPaths. When a developer refactors the front-end—even for a minor style change—these selectors break, causing automation to fail. This leads to constant, expensive maintenance, flaky tests, and a lack of trust in automated processes.

### The Mission: A Resilient, Self-Healing Agent
The Aegis Framework is designed to solve this problem by creating a robust automation agent that can see and adapt to change. Our mission is to build a **self-healing** agent by giving it vision, making it almost completely immune to underlying code changes.

---

## 2. The "What": Core Concepts & Architecture

### Core Architecture: Eyes, Brain, Hands
The framework has evolved to a visual-first architecture, significantly reducing reliance on brittle selectors.

* **👀 Eyes (The OmniParser Adapter):** The agent now *sees* the UI. It uses the `OmniParserAdapter` to run a sophisticated visual analysis script (`omni_parser.test.py`) on screenshots. This process identifies, labels, and provides coordinates for all interactive elements, turning a picture of the UI into a machine-readable format.
* **🧠 Brain (The Orchestrator & LLM):** The cognitive core of the agent. The `Orchestrator` uses an LLM (e.g., Gemini) to interpret high-level goals from a Playbook. It then correlates these goals with the visual information from the "Eyes" to decide on the next action. It uses a `ContextManager` to manage memory and prevent getting lost in long workflows.
* **✋ Hands (The Browser & Native Skills):** The agent executes actions through swappable adapters and skills. The `PlaywrightAdapter` can still perform traditional browser actions, but it's now complemented by native OS-level skills like `native_keyboard` and `native_screen_reader`, which can interact with the system directly, for example, to invoke a browser extension via a shortcut.

### The Playbook Concept
We do not write scripts; we write **Playbooks**. This approach enhances "developer joy" and aligns with our **Maintainability** ethos.

* **Location:** All playbooks are stored in the `playbooks/` directory.
* **Format:** A playbook is a `.yaml` file that describes a high-level objective broken down into a series of logical steps.
* **Declarative, Not Imperative:** Playbooks describe *what* the agent should achieve in human-readable language, making them easy to write, review, and maintain.

---

## 3. The "How": Getting Started

### Quickstart Guide

1.  **Prerequisites:**
    * Python 3.11+
    * A running instance of a Chromium-based browser (like Google Chrome).

2.  **Installation:**
    ```bash
    # Clone the repository
    git clone <your-repo-url>
    cd aegis-framework

    # Create and activate a virtual environment
    python3 -m venv .venv
    source .venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    ```

3.  **Browser Setup:**
    The agent connects to an existing browser instance. You must launch your browser with the remote debugging port enabled.
    ```bash
    # Example for Google Chrome on macOS
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=~/chrome-dev-session
    ```

4.  **Configuration:**
    Copy the example config and add your API keys.
    ```bash
    cp example_config.yaml config.yaml
    # Now, edit config.yaml to add your GOOGLE_API_KEY
    ```

5.  **Running a Playbook:**
    Execute a playbook using the `main.py` entry point.
    ```bash
    PYTHONPATH=src .venv/bin/python src/aegis/main.py run playbooks/character-sheet-base/goal.yaml
    ```

---

## 4. Next Steps: Reducing Tech Debt

Our immediate priority is to refactor the agent's core to pay down technical debt and prepare for future expansion. This work will be done on the `feature/unified-tool-registry` branch.

### The "Why": An Architectural Flaw
As we've added new capabilities like the `NativeOSAdapter`, we've uncovered an architectural flaw: the agent's LLM "brain" cannot see or use any tools outside of the browser. This is because the tool list is hardcoded in the `LLMAdapter`, and the tool execution logic is hardcoded in the `Orchestrator`. This severely limits the agent's autonomy and violates our "Automate Everything" ethos.

### The "What": A Unified Tool Registry
The solution is to create a single, centralized **Tool Registry** within the `Orchestrator`. This registry will be the single source of truth for all actions the agent can perform, regardless of which adapter provides them.

### The "How": The Refactoring Plan
1.  **Standardize Tool Definitions:** Every adapter (`PlaywrightAdapter`, `NativeOSAdapter`, etc.) will be responsible for defining the tools it provides via a common `get_tools()` method.
2.  **Build the Registry:** The `Orchestrator` will initialize a `ToolRegistry`. Upon startup, it will query each adapter for its tools and populate the registry. This registry will map each tool name to the adapter that owns it.
3.  **Unify the Tool List:** The `Orchestrator` will pass the complete, unified list of all tools from the registry to the `LLMAdapter`. This will make the LLM aware of every capability the agent possesses (both browser and native).
4.  **Implement Dynamic Dispatch:** The `Orchestrator`'s `handle_tool_calls` method will be rewritten. Instead of assuming the `browser_adapter`, it will now use the `ToolRegistry` to look up the correct adapter for any given tool call and dispatch the request accordingly.

This refactor will result in a clean, scalable architecture where adding new tools for the LLM to use is as simple as defining them in the appropriate adapter.