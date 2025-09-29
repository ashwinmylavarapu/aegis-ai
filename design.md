# Aegis Automation Framework: Architecture & Design

**Version:** 1.0
**Status:** Living Document

## 1. Vision & Mission (The "Why")

This document outlines the architecture and design principles of the Aegis Automation Framework. It is intended to be the "north star" for development, providing a comprehensive overview for new team members and forming the basis for future Architecture Decision Records (ADRs).

### 1.1. The Problem: The Fragility of UI Automation

Traditional UI automation is fundamentally brittle. Scripts are tightly coupled to the Document Object Model (DOM) through fragile CSS selectors and XPaths. Any change to the front-end codebase, even a minor cosmetic refactor, can break these selectors, leading to failing tests, high maintenance costs, and a general lack of trust in automated processes.

### 1.2. The North Star: A Self-Healing, Adaptive Agent

The mission of Aegis is to create a **resilient, self-healing automation agent** that perceives and interacts with user interfaces like a human. By decoupling our agent from the underlying code structure (like the DOM), we aim to build a system that is almost completely immune to cosmetic code changes, thus solving the brittleness problem.

### 1.3. Core Principles

Our development is guided by "The Agent's Code Ethos — V7". From this, we derive our primary project principles:

* **Observability Foremost:** Every action the agent takes must be transparent and easily debuggable. If a failure occurs, the logs and artifacts must be sufficient to pinpoint the root cause without guesswork.
* **Maintainability through Abstraction:** We favor clean, decoupled code that is easy to understand, modify, and extend. We do not write scripts; we build a resilient framework.
* **Security by Default:** As the agent's capabilities grow to interact with the native OS, we must prioritize security, implementing safeguards like allow-lists and strict input validation.
* **Automated Enforcement:** Our principles and quality standards are designed to be enforced by automated CI/CD gates and fitness functions, as outlined in the ethos.

---

## 2. Core Architecture: Eyes, Brain, Hands

The Aegis framework is modeled on a simple but powerful metaphor for intelligent action: perceiving the environment, thinking about what to do, and then acting upon it.

### 2.1. 👀 The "Eyes" - The Perception Layer

**Purpose:** To decouple the agent from the DOM by perceiving the UI visually.

**Implementation:** The primary component is the `OmniParserAdapter`. It orchestrates an external Python script (`scripts/omni_parser.test.py`) that uses a multimodal model to analyze a screenshot of a UI.

**Data Flow:**
1.  The agent takes a screenshot of the current application state.
2.  The screenshot is passed to the `OmniParserAdapter`.
3.  The adapter returns a structured JSON object containing a list of all detected interactive UI elements, their text labels (via OCR), their visual descriptions (captions), and their bounding box coordinates.

This transforms a raw image into a machine-readable "map" of the UI, which the "Brain" can use for decision-making.

### 2.2. 🧠 The "Brain" - The Cognitive Layer

**Purpose:** To interpret goals, reason about the state of the UI, formulate plans, and make decisions.

**Components:**
* **Orchestrator (`orchestrator.py`):** This is the agent's central cognitive loop. It is responsible for loading a `Playbook` and executing its steps sequentially. It manages the agent's context and coordinates all other components.
* **LLM Adapter (`google_genai_adapter.py`):** This is the core reasoning engine, an implementation of the abstract `LLMAdapter`. For `agent_step`s, the `Orchestrator` provides the LLM with a goal, the conversation history, and a list of available tools. The LLM then reasons about the problem and returns a decision in the form of a "tool call".
* **Context Manager (`context_manager.py`):** This represents the agent's memory. It manages the history of messages, tool calls, and tool responses, ensuring that the conversation stays coherent and within the LLM's context window limits.

### 2.3. ✋ The "Hands" - The Action Layer

**Purpose:** To execute the "Brain's" decisions and interact with the target environment. This layer is built entirely on the Adapter pattern.

**Adapters:**
* **`PlaywrightAdapter`:** An implementation of the `BrowserAdapter` interface. It is responsible for all browser-based interactions, such as navigating to URLs, clicking elements, and typing text.
* **`NativeOSAdapter`:** An abstraction for all OS-level interactions. The concrete implementation, `AppleScriptOSAdapter`, handles tasks on macOS like launching/quitting applications, managing windows, and executing native key presses.

---

## 3. Key Design Patterns & Concepts

### 3.1. Hexagonal Architecture (Ports & Adapters)

This is the foundational pattern of the Aegis framework, mandated by our ethos.

* **The Core Application ("Hexagon"):** The `Orchestrator` and core models represent the central business logic.
* **Ports:** Abstract base classes like `LLMAdapter`, `BrowserAdapter`, and `NativeOSAdapter` define the interfaces for interacting with the outside world.
* **Adapters:** Concrete classes like `GoogleGenAIAdapter` and `AppleScriptOSAdapter` implement these interfaces, encapsulating all the specific details and external dependencies.

This pattern makes the system highly modular, testable, and portable. Swapping out our LLM provider or adding support for a new OS becomes a matter of writing a new adapter, with no changes to the core application logic.

### 3.2. The Playbook

Playbooks are declarative YAML files that define a high-level objective for the agent. They are designed to be human-readable and focus on **what** to achieve, not **how** to achieve it.

**Step Types:**
* `agent_step`: Used for tasks requiring reasoning. The `prompt` is given to the LLM, which then decides which tool(s) to use.
* `skill_step`: Used for direct, deterministic calls to adapter methods. This is primarily for native OS interactions where we want precise control (e.g., `launch_app`).
* `human_intervention`: Pauses execution and prompts for manual verification, ensuring a human is in the loop for critical steps.

### 3.3. Observability by Design

In line with our "Observability Foremost" principle, the framework is built to be transparent.

* **Structured Logging:** We use `loguru` with `log.bind()` to attach context (e.g., `adapter_name`, `function_name`) to every log message, making them easy to filter and analyze.
* **Visual Evidence:** All UI-affecting actions (e.g., `click`, `focus_window`, `launch_app`) are required to capture **before-and-after screenshots**. These are saved to the `debug_screenshots/` directory and are considered primary debugging artifacts.
* **LLM Transparency:** We log the exact token count and the final JSON payload sent to the LLM, as well as the raw response received. This is crucial for debugging prompting issues and unexpected LLM behavior.

---

## 4. The "North Star": Future Architecture & Development

This section outlines the planned evolution of the framework.

### 4.1. Immediate Priority: The Unified Tool Registry

**The Problem:** We have identified a critical architectural flaw: the LLM "Brain" is blind to our native OS tools. The tool list provided to the LLM is hardcoded to come only from the browser adapter, and the `Orchestrator` is hardcoded to only execute browser tool calls.

**The Solution (`feature/unified-tool-registry`):**
1.  **Create a central `ToolRegistry`** within the `Orchestrator`.
2.  All adapters (`PlaywrightAdapter`, `NativeOSAdapter`) will be enhanced with a `get_tools()` method to declare their capabilities.
3.  On startup, the `Orchestrator` will query all adapters and populate the registry.
4.  The complete, unified tool list from the registry will be passed to the `LLMAdapter`.
5.  The `Orchestrator` will be refactored to use the registry to dynamically dispatch LLM tool calls to the correct adapter.

This refactor is our top priority to reduce technical debt and enable the agent to be truly autonomous.

### 4.2. Mid-Term Goals

* **Deeper System & Mouse Control:** Implement the remaining brainstormed native skills: clipboard access (`get/set_clipboard_content`), direct mouse control (`move_mouse`, `click_mouse`, `drag_mouse`), and a secure, allow-list-based `execute_shell_command`.
* **Cross-Platform Support:** Create new `NativeOSAdapter` implementations for Windows (likely using `pywin32`) and Linux (likely using `xdotool`) to make the agent portable.

### 4.3. Long-Term Vision: The Fully Autonomous Agent

The ultimate goal is to move beyond step-by-step playbooks for most tasks. The agent will be given a high-level objective (e.g., "Summarize the latest posts from my LinkedIn feed") and will autonomously chain together tool calls—perception (`read_screen_content`), reasoning (LLM), and action (`click`, `scroll`)—in a closed loop until the objective is complete.

---

## 5. Getting Started

For a practical guide on installing dependencies and running a playbook, please refer to the `README.md` file.