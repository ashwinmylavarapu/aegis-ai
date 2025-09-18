
# Aegis Automation Framework

A resilient, adaptive agent for robust UI automation.

---

## 1. The "Why": The Big Picture

### The Problem: Brittle UI Automation
Traditional UI automation is fundamentally fragile. Scripts are tightly coupled to the Document Object Model (DOM) through CSS selectors and XPaths. When a developer refactors the front-end—even for a minor style change—these selectors break, causing automation to fail. This leads to constant, expensive maintenance, flaky tests, and a lack of trust in automated processes.

### The Mission: A Resilient, Adaptive Agent
The Aegis Framework is designed to solve this problem by creating a robust automation agent that can adapt to change. Our mission is a two-phase journey:

1.  **Perfect the DOM-based Agent:** First, we've built a highly resilient agent that mitigates the fragility of the DOM. By decomposing complex goals into manageable tasks and equipping the agent with a persistent **checklist memory**, it can reliably execute multi-step workflows without getting lost or stuck in loops.
2.  **Evolve to a Visual Agent:** The ultimate goal is to make the agent **self-healing** by giving it vision. The next evolution of Aegis will use a multimodal model to *see* and *understand* a UI like a human, making it almost completely immune to underlying code changes.

---

## 2. The "What": Core Concepts & Architecture

### Core Architecture: Checklist-Driven Cognition
The framework is built on Hexagonal Architecture principles, centered around an intelligent orchestrator that uses a stateful memory to guide its reasoning.

* **Orchestrator (The Brain):** The cognitive core of the agent. It uses an LLM (e.g., Gemini) to interpret high-level goals from a Playbook and decide on the next action.
* **Persistent Memory (The Checklist):** To prevent loops and combat context window limitations, the agent maintains a stateful **checklist** of completed actions for each task. Before thinking, the agent is always reminded of what it has already accomplished, allowing it to make accurate decisions even with a limited short-term memory (the LLM's chat history).
* **Adapters (The Hands):** Following the Ports and Adapters pattern, all external interactions are handled by swappable adapters. The primary adapter is the `PlaywrightAdapter`, which executes commands like `click` and `type_text` in the browser.

### The Playbook Concept
We do not write scripts; we write **Playbooks**. This approach enhances "developer joy" and aligns with our **Maintainability** ethos.

* **Location:** All playbooks are stored in the `playbooks/` directory.
* **Format:** A playbook is a `.yaml` file that describes a high-level objective broken down into a series of logical tasks.
* **Declarative, Not Imperative:** Playbooks describe *what* the agent should achieve in human-readable language. This makes them easy to write, review, and maintain.

### Directory & File Structure
The project is organized to separate concerns, making it easy to navigate and extend.

```

.
├── playbooks/                \# Contains all high-level automation plans (Playbooks).
│   ├── character-sheet-base/
│   │   └── goal.yaml
│   └── character-sheet-extended/
│       └── goal\_lighting\_and\_angles.yaml
│
├── src/
│   └── aegis/
│       ├── adapters/           \# Hexagonal pattern: all outbound communication.
│       │   ├── outbound/
│       │   │   ├── playwright\_adapter.py  \# The "Hands" - controls the browser.
│       │   │   └── google\_genai\_adapter.py  \# Connects to the LLM.
│       │
│       ├── core/               \# The heart of the agent.
│       │   ├── orchestrator.py \# The "Brain" - manages the agent's state and loop.
│       │   ├── models.py       \# Pydantic models for state, goals, and plans.
│       │   └── context\_manager.py \# The safety net for context window management.
│       │
│       ├── skills/             \# Reusable, complex business logic functions.
│       │
│       └── main.py             \# The application's main entry point.
│
├── config.yaml               \# Your local configuration (API keys, endpoints).
├── example\_config.yaml       \# A template for configuration.
├── requirements.txt          \# Project dependencies.
└── scorecard.yaml            \# Production readiness checklist (enforced by ethos).

````

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

## 4. The Future: A Self-Healing Visual Agent

The ultimate vision for Aegis is to eliminate the final piece of brittle logic—CSS selectors—by giving the agent **vision**. This future architecture is called **"Eyes, Brain, Hands"**.

* **Eyes (The Visual Adapter):** A future component that will use a multimodal model (like **Microsoft OmniParser**) to *see* the UI. It will take a screenshot and return a labeled list of all interactive elements and their coordinates.
* **Brain (Upgraded):** The agent's brain will be upgraded to correlate the playbook's human-like instructions (e.g., "click the send button") with the visual labels provided by the "Eyes."
* **Hands (Upgraded):** The hands will learn new skills to act on visual cues, such as `click_element(label='e3')`, which will click coordinates instead of selectors.

This will make our playbooks 100% declarative and create a truly self-healing system that is almost completely immune to front-end code changes. This is the project's primary strategic goal.
````