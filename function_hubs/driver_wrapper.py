import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '../../applications/catia_vla'))

from applications.catia_vla.driver.controller import InputController
# 假设你已经把 screenshot_tool 放到了 driver 里
from applications.catia_vla.driver.screenshot_tool import capture_full_screen 

_controller = InputController()
_screenshot = capture_full_screen(save_path=os.path.abspath("current_state.png"))

def click_element(x: int, y: int) -> str:
    """OxyGent Function: 点击指定坐标"""
    try:
        _controller.click(x, y)
        return "Click success"
    except Exception as e:
        return f"Click failed: {str(e)}"

def capture_screen() -> str:
    """OxyGent Function: 截图"""
    return _screenshot

# ... 类似上面的 schema 定义，告诉 LLM click_element 需要 x, y ...