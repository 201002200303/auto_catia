import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SimulationCube")

# Add project root to sys.path
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

# Import tools
from function_hubs.catia_tools import (
    activate_catia_window,
    capture_screen,
    detect_ui_elements,
    click_element,
    input_text,
    press_key
)

class MockLLM:
    """
    模拟大模型，持有 SOP 知识库并根据感知结果做出决策。
    """
    def __init__(self):
        self.step_index = 0
        # SOP: 模拟点击流程
        # 1. 点击草图 (模拟使用标签 '007')
        # 2. 取消选择
        # 3. 点击拉伸 (模拟使用标签 '000')
        # 4. 取消选择
        self.sop = [
            {"step": "Select Sketch", "description": "点击左侧树中的草图一", "action_type": "click", "target_hint": "007"},
            {"step": "取消", "description": "取消选择", "action_type": "key", "key": "esc"}, 
            {"step": "Click Pad", "description": "点击右侧的拉伸图标", "action_type": "click", "target_hint": "000"},    
            {"step": "取消", "description": "取消选择", "action_type": "key", "key": "esc"},
        ]

    def decide(self, perception_json: str) -> Dict[str, Any]:
        """
        根据当前步骤和感知结果，生成工具调用指令。
        """
        if self.step_index >= len(self.sop):
            return {"action": "finish"}
        
        current_step = self.sop[self.step_index]
        self.step_index += 1
        
        print(f"\n========================================")
        print(f"🤖 [Mock LLM] 思考中...")
        print(f"当前任务: {current_step['step']} - {current_step['description']}")
        
        # 解析感知结果
        try:
            perception = json.loads(perception_json)
        except:
            perception = []
            
        if current_step["action_type"] == "click":
            # 决策逻辑：寻找目标图标
            target_label = current_step["target_hint"]
            print(f"寻找目标: {target_label}")
            
            # 在感知结果中查找
            target = next((item for item in perception if item.get("label") == target_label), None)
            
            if target:
                bbox = target["bbox"]
                center_x = int((bbox[0] + bbox[2]) / 2)
                center_y = int((bbox[1] + bbox[3]) / 2)
                print(f"✅ 找到目标，坐标: ({center_x}, {center_y})")
                
                return {
                    "tool": "click_element",
                    "args": {"x": center_x, "y": center_y},
                    "thought": f"我看到了 {target_label}，坐标是 ({center_x}, {center_y})，我将点击它。"
                }
            else:
                # 如果没找到，为了测试流程继续，使用第一个检测到的物体或默认坐标
                print(f"⚠️ 未找到目标 '{target_label}'")
                if len(perception) > 0:
                    fallback = perception[0]
                    bbox = fallback["bbox"]
                    center_x = int((bbox[0] + bbox[2]) / 2)
                    center_y = int((bbox[1] + bbox[3]) / 2)
                    print(f"⚠️ Fallback: 点击第一个可见元素 ({fallback.get('label')})")
                    return {
                        "tool": "click_element",
                        "args": {"x": center_x, "y": center_y},
                        "thought": f"未找到目标，尝试点击 {fallback.get('label')}。"
                    }
                else:
                    print(f"⚠️ 屏幕上没有识别到任何元素，使用默认坐标 (500, 500)")
                    return {
                        "tool": "click_element",
                        "args": {"x": 500, "y": 500},
                        "thought": "未识别到元素，盲点 (500, 500)。"
                    }

        elif current_step["action_type"] == "input":
            return {
                "tool": "input_text",
                "args": {"text": current_step["value"]},
                "thought": f"根据 SOP，我需要输入数值 {current_step['value']}。"
            }
            
        elif current_step["action_type"] == "key":
            return {
                "tool": "press_key",
                "args": {"key_name": current_step["key"]},
                "thought": f"输入完成，按下 {current_step['key']} 确认。"
            }
            
        return {"action": "wait"}

async def run_tool(func, **kwargs):
    """辅助函数：运行工具（自动处理同步/异步）"""
    if asyncio.iscoroutinefunction(func):
        return await func(**kwargs)
    return func(**kwargs)

async def main():
    print("🚀 开始模拟 'SOP 知识库驱动的立方体建模' 工作流")
    print("--------------------------------------------------")
    
    # 初始化 Mock Agent
    agent = MockLLM()
    
    # 1. 激活窗口
    print("\n[System] 正在激活 CATIA 窗口...")
    await run_tool(activate_catia_window)
    
    # 循环执行 SOP 步骤
    step_count = 0
    while True:
        step_count += 1
        print(f"\n>>> 进入第 {step_count} 轮循环 (感知-决策-执行) <<<")
        
        # --- 1. 感知 (Perception) ---
        print("👀 [感知] 正在截屏...")
        screenshot_res = await run_tool(capture_screen)
        screenshot_data = json.loads(screenshot_res)
        if not screenshot_data.get("success"):
            print("❌ 截图失败")
            break
        image_path = screenshot_data["file_path"]
        
        print(f"🧠 [感知] 正在识别界面元素... (Image: {image_path})")
        detection_res = await run_tool(detect_ui_elements, image_path=image_path)
        
        # --- 2. 决策 (Decision) ---
        decision = agent.decide(detection_res)
        
        if decision.get("action") == "finish":
            print("\n🎉 SOP 流程执行完毕！")
            break
            
        print(f"💡 [决策] Agent 决定执行: {decision['tool']}")
        print(f"   参数: {decision['args']}")
        print(f"   思考: {decision.get('thought')}")
        
        # --- 3. 执行 (Action) ---
        tool_name = decision["tool"]
        tool_args = decision["args"]
        
        print(f"🔨 [执行] 调用工具 {tool_name}...")
        
        result = None
        if tool_name == "click_element":
            result = await run_tool(click_element, **tool_args)
        elif tool_name == "input_text":
            result = await run_tool(input_text, **tool_args)
        elif tool_name == "press_key":
            result = await run_tool(press_key, **tool_args)
            
        print(f"✅ [结果] {result}")
        
        # 简单的等待，模拟思考间隔
        await asyncio.sleep(1.0)

if __name__ == "__main__":
    asyncio.run(main())
