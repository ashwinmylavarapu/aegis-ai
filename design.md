# Aegis Automation Framework: Architecture & Design

**Version:** 1.1
**Status:** Living Document

## 1. Vision & Mission (The "Why")

This document outlines the architecture and design principles of the Aegis Automation Framework. It is intended to be the "north star" for development, providing a comprehensive overview for new team members and forming the basis for future Architecture Decision Records (ADRs).

### 1.1. The Problem: The Fragility of UI Automation
Traditional UI automation is fundamentally brittle. Scripts are tightly coupled to the Document Object Model (DOM) through fragile CSS selectors and XPaths. Any change to the front-end codebase, even a minor cosmetic refactor, can break these selectors, leading to failing tests and high maintenance costs.

### 1.2. The North Star: A Self-Healing, Adaptive Agent
The mission of Aegis is to create a **resilient, self-healing automation agent** that perceives and interacts with user interfaces like a human. By decoupling our agent from the underlying code structure, we aim to build a system that is almost completely immune to cosmetic code changes.

### 1.3. Core Principles
Our development is guided by "The Agent's Code Ethos — V7". From this, we derive our primary project principles:

* **Observability Foremost:** Every action the agent takes must be transparent and easily debuggable.
* **Maintainability through Abstraction:** We favor clean, decoupled code. We do not write scripts; we build a resilient framework.
* **Developer Joy:** We build tools that make the development and maintenance of automations a pleasant and efficient experience.
* **Automated Enforcement:** Our principles are designed to be enforced by automated CI/CD gates.

---

## 2. Core Architecture: Eyes, Brain, Hands

The Aegis framework is modeled on a simple but powerful metaphor for intelligent action: perceiving the environment, thinking about what to do, and then acting upon it.

### 2.1. 👀 The "Eyes" - The Perception Layer
**Purpose:** To decouple the agent from the DOM by perceiving the UI visually through the `OmniParserAdapter`.

### 2.2. 🧠 The "Brain" - The Cognitive Layer
**Purpose:** To interpret goals, reason about the state of the UI, formulate plans, and make decisions.

**Components:**
* **Orchestrator (`orchestrator.py`):** The agent's central cognitive loop.
* **LLM Adapter (`google_genai_adapter.py`):** The core reasoning engine.
* **Context Manager (`context_manager.py`):** The agent's short-term memory.

### 2.3. ✋ The "Hands" - The Action Layer
**Purpose:** To execute the "Brain's" decisions and interact with the target environment using a suite of adapters.

**Adapters:**
* **`PlaywrightAdapter`:** For all browser-based interactions.
* **`NativeOSAdapter`:** For all OS-level interactions (implemented via `AppleScriptOSAdapter` on macOS).

---

## 3. Key Design Patterns & Concepts

### 3.1. Hexagonal Architecture (Ports & Adapters)
This is the foundational pattern of the Aegis framework. The `Orchestrator` is the core application, and it interacts with the outside world through abstract "ports" (`LLMAdapter`, `BrowserAdapter`, etc.). Concrete "adapters" (`GoogleGenAIAdapter`, `PlaywrightAdapter`) provide the specific implementations. This keeps the core logic clean and independent of external technologies.

### 3.2. The Playbook
Playbooks are declarative YAML files that define a high-level objective. They focus on **what** to achieve, not **how**.

**Step Types:**
* `agent_step`: For tasks requiring reasoning by the LLM.
* `skill_step`: For direct, deterministic calls to adapter methods (e.g., `launch_app`).
* `human_intervention`: Pauses execution for manual verification.
* `run_routine`: Executes a predefined sequence of steps, optionally in a loop.

**Routines and Loops:** To eliminate repetition and promote maintainability, playbooks support a `routines` block.
* **Definition:** A routine is a named, reusable template of steps. Placeholders like `{{params.variable}}` can be used within these steps.
* **Execution:** The `run_routine` step executes a routine. It can be combined with a `loop_with` key, which provides a list of parameter sets to run the routine multiple times, once for each set. This is the primary mechanism for handling repetitive tasks in a clean, declarative way.

### 3.3. Developer Tooling: `aegis-tools`
In line with our "Developer Joy" principle, the project includes a dedicated CLI toolset, `aegis-tools`, for common development tasks. This toolset is designed to be extensible, with a `noun verb` command structure (e.g., `playbook create`).

**Key Tools:**
* **`playbook create`:** An LLM-powered tool that takes a natural language story and automatically generates a valid, structured playbook YAML file. This is the preferred way to start a new playbook.
* **`playbook validate`:** A linter that checks a playbook's syntax against the framework's Pydantic models.

---

## 4. The "North Star": Future Architecture & Development

### 4.1. Immediate Priority: The Unified Tool Registry
**The Problem:** The LLM "Brain" is blind to our native OS tools because the tool list is hardcoded to the browser adapter.
**The Solution (`feature/unified-tool-registry`):**
1.  Create a central `ToolRegistry` in the `Orchestrator`.
2.  All adapters will implement a `get_tools()` method to declare their capabilities.
3.  The `Orchestrator` will populate the registry at startup and pass the unified tool list to the LLM.
4.  The `Orchestrator` will use the registry to dynamically dispatch tool calls to the correct adapter.

This refactor is our top priority to enable the agent to be truly autonomous.

### 4.2. Mid-Term Goals
* **Deeper System Control:** Implement more native skills for clipboard, mouse, and secure shell access.
* **Cross-Platform Support:** Create new `NativeOSAdapter` implementations for Windows and Linux.
* **Enhance `aegis-tools`:** Add more developer joy tools, such as a playbook visualizer and a dry-run executor.

### 4.3. Long-Term Vision: The Fully Autonomous Agent
The ultimate goal is to move beyond step-by-step playbooks for most tasks. The agent will be given a high-level objective and will autonomously chain together perception, reasoning, and action in a closed loop until the objective is complete.