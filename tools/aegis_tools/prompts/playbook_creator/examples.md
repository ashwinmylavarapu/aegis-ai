**Story:**
"Test the browser extension by pressing Alt+A, wait a bit, then ask a human to check if the sidebar is open."

**Playbook:**
```yaml
name: "Test Native Key Press for Browser Extension"
description: "Tests triggering a browser extension via a native OS-level key press."
persona: "You are a testing agent verifying browser extension integration."
steps:
  - name: "Invoke Assistant via Native Shortcut"
    type: "skill_step"
    function_name: "press_key_native"
    params:
      key: "a"
      modifier: "alt"
  - name: "Wait for sidebar to appear"
    type: "agent_step"
    prompt: "wait for 3 seconds"
  - name: "Verify sidebar"
    type: "human_intervention"
    prompt: "Please visually confirm that the assistant sidebar is now open in the browser."