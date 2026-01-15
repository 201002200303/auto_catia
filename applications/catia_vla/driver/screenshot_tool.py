"""
截图工具模块

提供全屏截图功能，支持保存到指定路径或返回临时文件路径。
"""

import os
import tempfile
from typing import Optional
import pyautogui
from PIL import Image


def capture_full_screen(save_path: Optional[str] = None) -> str:
    """
    截取全屏并保存为 PNG 文件
    
    Args:
        save_path: 保存路径。如果为 None，则保存到临时文件
        
    Returns:
        str: 保存的文件路径
    """
    screenshot = pyautogui.screenshot()
    
    if save_path is None:
        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"catia_screenshot_{os.getpid()}.png")
        save_path = temp_path
    
    # 确保目录存在
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # 保存截图
    screenshot.save(save_path)
    
    return save_path