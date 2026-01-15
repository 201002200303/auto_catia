I will implement the **Cube Building Simulation** strictly following your SOP-based workflow:

**1. Enhance Tool Capability (Framework Check)**

* **Add** **`press_key`** **tool**: The current framework lacks a keyboard press tool (e.g., for "Enter" key). I will add `press_key` to `catia_tools.py` to support the "Confirm" step in your SOP.

* **Verify** **`input_text`**: Ensure it supports your parameter requirements.

**2. Develop** **`simulation_cube_workflow.py`**
I will create a script that simulates the **"Perception-Decision-Action"** loop for each step of the Cube SOP:

* **Define SOP Knowledge Base (Mock)**:

  * Hardcode the "Cube Modeling SOP": `[Step 1: Select Sketch, Step 2: Click Pad, Step 3: Input Value, Step 4: Confirm]`.

* **Implement the Simulation Loop**:

  * **Perception**: Call `capture_screen` and `detect_ui_elements` to get the current UI state.

  * **Decision (Simulated LLM)**:

    * Read the current SOP step (e.g., "Select Sketch").

    * Parse the `detect_ui_elements` output (JSON) to find the target icon (e.g., matching label "030" for Sketch).

    * Generate a **Standard Tool Call JSON** (e.g., `{"tool": "click_element", "args": {"x": 200, "y": 300}}`).

  * **Execution**:

    * Receive the Tool Call JSON.

    * Dispatch it to the actual `catia_tools` function (MCP) to perform the click or input.

**3. Verification**

* Run the script to demonstrate the full chain: **Screenshot -> Identify -> Plan (Mock) -> Click/Type**.

* This verifies that your framework is ready for real LLM integration.

