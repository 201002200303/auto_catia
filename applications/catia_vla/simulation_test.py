
import os
import sys
import json
import time
import random
import asyncio
from pathlib import Path

# 添加项目路径
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))

try:
    from function_hubs.catia_tools import (
        detect_ui_elements,
        capture_screen,
        click_element,
        activate_catia_window
    )
except ImportError:
    # 尝试直接从模块导入（如果上面的导入失败）
    import function_hubs.catia_tools as catia_tools_module
    detect_ui_elements = getattr(catia_tools_module, 'detect_ui_elements', None)
    capture_screen = getattr(catia_tools_module, 'capture_screen', None)
    click_element = getattr(catia_tools_module, 'click_element', None)
    activate_catia_window = getattr(catia_tools_module, 'activate_catia_window', None)

async def run_tool(func, **kwargs):
    """辅助函数：运行工具（自动处理同步/异步）"""
    if asyncio.iscoroutinefunction(func):
        return await func(**kwargs)
    return func(**kwargs)

def simulate_llm_decision(detection_json):
    """
    模拟大模型决策过程：
    1. 接收检测到的 UI 元素列表
    2. 规划点击顺序
    3. 返回决策结果（JSON）
    """
    print("\n" + "="*40)
    print("🤖 [模拟 LLM] 正在思考...")
    print("="*40)
    
    try:
        detections = json.loads(detection_json)
    except json.JSONDecodeError:
        return json.dumps({
            "thought": "解析检测结果失败。",
            "action": "wait",
            "target": None
        }, ensure_ascii=False)
    
    if not detections or isinstance(detections, dict) and "error" in detections:
        return json.dumps({
            "thought": "屏幕上没有检测到任何可用的 UI 元素。",
            "action": "wait",
            "target": None
        }, ensure_ascii=False)
    
    # 模拟：LLM 决定点击置信度最高的那个元素
    # 或者随机选择一个
    # 这里我们选择第一个检测到的元素作为演示
    target = detections[0]
    
    # 构造模拟的 LLM 输出
    llm_response = {
        "thought": f"我看到了 {len(detections)} 个图标。根据任务规划，我需要先点击 '{target['label']}'。",
        "plan": [
            f"点击 {target['label']}",
            "等待菜单弹出",
            "选择下一步操作"
        ],
        "current_action": {
            "type": "click",
            "target_label": target['label'],
            "bbox": target['bbox'],
            "confidence": target['confidence']
        }
    }
    
    return json.dumps(llm_response, ensure_ascii=False, indent=2)

async def main():
    print("🚀 开始模拟 '感知-决策-执行' 闭环测试")
    print("-" * 50)

    # 1. 尝试激活窗口（可选）
    print("\nStep 1: 尝试激活 CATIA 窗口...")
    activate_res = await run_tool(activate_catia_window)
    print(f"激活结果: {activate_res}")
    
    # 2. 截图
    print("\nStep 2: 截取屏幕...")
    # 无论是否激活成功，都尝试截图
    screenshot_res_json = await run_tool(capture_screen)
    try:
        screenshot_res = json.loads(screenshot_res_json)
    except:
        print(f"❌ 截图结果解析失败: {screenshot_res_json}")
        return
    
    image_path = None
    if isinstance(screenshot_res, dict) and screenshot_res.get("success"):
        image_path = screenshot_res.get("file_path")
        print(f"✅ 截图成功: {image_path}")
    else:
        print(f"❌ 截图失败: {screenshot_res}")
        # 如果截图失败，也无法继续
        return

    # 3. 视觉识别
    print("\nStep 3: 识别界面元素...")
    detection_json = await run_tool(detect_ui_elements, image_path=image_path)
    detections = json.loads(detection_json)
    
    # 如果检测结果为空或有错误，切换到测试图片
    if not detections or (isinstance(detections, dict) and "error" in detections):
        print("⚠️  当前屏幕未检测到 CATIA 元素 (可能是因为未打开 CATIA)")
        print("🔄 切换到测试图片进行模拟演示...")
        test_image = str(Path(__file__).parent / "perception" / "figures" / "11.jpg")
        if os.path.exists(test_image):
            print(f"读取测试图片: {test_image}")
            detection_json = await run_tool(detect_ui_elements, image_path=test_image)
            image_path = test_image # 更新图片路径
        else:
            print("❌ 测试图片也不存在，无法继续演示。")
            return

    print(f"检测结果: {detection_json[:500]}..." + ("" if len(detection_json)<500 else "\n(截断展示)"))

    # 4. 模拟大模型决策
    print("\nStep 4: 发送给大模型进行规划...")
    llm_output_json = simulate_llm_decision(detection_json)
    print(f"\n📜 [LLM 输出]:\n{llm_output_json}")
    
    llm_output = json.loads(llm_output_json)
    
    if llm_output.get("action") == "wait":
        print("LLM 决定等待，流程结束。")
        return

    # 5. 解析决策并执行
    action = llm_output["current_action"]
    print(f"\nStep 5: 执行动作 -> 点击 {action['target_label']}")
    
    bbox = action["bbox"] # [x1, y1, x2, y2]
    
    x1, y1, x2, y2 = bbox
    center_x = int((x1 + x2) / 2)
    center_y = int((y1 + y2) / 2)
    
    print(f"目标坐标 (BBox): {bbox}")
    print(f"计算中心点: ({center_x}, {center_y})")
    
    if "figures" in image_path:
        print("\n⚠️  警告: 正在使用静态测试图片进行演示。")
        print("    点击操作将发送到屏幕的 ({}, {}) 位置。".format(center_x, center_y))
        print("    这可能不会点击到真实的图标，仅用于测试点击功能是否正常运行。")
    
    # 执行点击
    click_res_json = await run_tool(click_element, x=center_x, y=center_y)
    print(f"点击结果: {click_res_json}")

if __name__ == "__main__":
    asyncio.run(main())
