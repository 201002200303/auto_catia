import sys
import os
import json

# 这一步是为了让 Python 能找到你的 perception 文件夹
# 假设当前文件在 function_hubs/catia_tools/，我们需要回退两层找到 applications
sys.path.append(os.path.join(os.path.dirname(__file__), '../../applications/catia_vla'))

from applications.catia_vla.perception.inference import VisionService

# 初始化模型 (单例模式，避免重复加载)
# 注意：路径可能需要根据实际运行位置调整
_vision_service = VisionService(model_path=r"../../applications/catia_vla/perception/weights/best.pt")

def detect_ui_elements(image_path: str) -> str:
    """
    OxyGent Function: 识别 CATIA 界面元素
    Args:
        image_path: 截图的绝对路径
    Returns:
        JSON 字符串，包含所有识别到的图标及其坐标
    """
    try:
        # 调用写好的滑动窗口检测方法
        results = _vision_service.detect_full_screen_tiled(image_path)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_vision_tool_schema():
    """告诉 LLM 这个工具怎么用 (ICD 定义)"""
    return {
        "name": "detect_ui_elements",
        "description": "识别当前屏幕截图中的 CATIA 界面图标、按钮和菜单，返回它们的坐标。",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "屏幕截图文件的完整路径"
                }
            },
            "required": ["image_path"]
        }
    }