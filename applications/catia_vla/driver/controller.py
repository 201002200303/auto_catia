"""
鼠标/键盘控制封装模块

使用 win32api 和 win32con 实现底层鼠标和键盘输入控制。
提供原子级别的操作接口，支持点击、拖拽、键盘输入等功能。
"""

import time
from typing import Optional
import win32api
import win32con


class InputController:
    """
    输入控制器类
    
    封装 Windows 底层输入操作，包括鼠标移动、点击、键盘输入等。
    所有操作都包含适当的延迟，以模拟人类操作并确保 UI 能够响应。
    """
    
    def __init__(self, action_delay: float = 0.05, highlight_click: bool = False):
        """
        初始化输入控制器
        
        Args:
            action_delay: 每个操作后的延迟时间（秒），用于让 UI 消化事件
            highlight_click: 是否在点击前打印坐标（调试模式）
        """
        self.action_delay = action_delay
        self.highlight_click = highlight_click
    
    def move_to(self, x: int, y: int) -> None:
        """
        移动鼠标到指定坐标
        
        使用 win32api.SetCursorPos 直接设置鼠标位置。
        
        Args:
            x: 目标 x 坐标（屏幕绝对坐标）
            y: 目标 y 坐标（屏幕绝对坐标）
        """
        win32api.SetCursorPos((x, y))
        time.sleep(self.action_delay)
    
    def click(self, x: int, y: int, button: str = "left") -> None:
        """
        在指定坐标执行鼠标点击
        
        操作流程：
        1. 移动鼠标到目标位置
        2. 短暂延迟（模拟人类操作）
        3. 按下鼠标按钮
        4. 释放鼠标按钮
        
        Args:
            x: 目标 x 坐标（屏幕绝对坐标）
            y: 目标 y 坐标（屏幕绝对坐标）
            button: 鼠标按钮类型，"left" 或 "right"
        """
        if self.highlight_click:
            print(f"[DEBUG] 点击坐标: ({x}, {y})")
        
        # 移动鼠标到目标位置
        self.move_to(x, y)
        
        # 短暂延迟，模拟人类操作
        time.sleep(0.05)
        
        # 确定鼠标事件标志
        if button.lower() == "left":
            down_flag = win32con.MOUSEEVENTF_LEFTDOWN
            up_flag = win32con.MOUSEEVENTF_LEFTUP
        elif button.lower() == "right":
            down_flag = win32con.MOUSEEVENTF_RIGHTDOWN
            up_flag = win32con.MOUSEEVENTF_RIGHTUP
        else:
            raise ValueError(f"不支持的鼠标按钮类型: {button}")
        
        # 执行点击：按下 -> 释放
        win32api.mouse_event(down_flag, x, y, 0, 0)
        time.sleep(0.01)  # 按下和释放之间的短暂延迟
        win32api.mouse_event(up_flag, x, y, 0, 0)
        
        # 操作后延迟
        time.sleep(self.action_delay)
    
    def double_click(self, x: int, y: int, button: str = "left", interval: float = 0.1) -> None:
        """
        在指定坐标执行双击
        
        Args:
            x: 目标 x 坐标（屏幕绝对坐标）
            y: 目标 y 坐标（屏幕绝对坐标）
            button: 鼠标按钮类型，"left" 或 "right"
            interval: 两次点击之间的间隔时间（秒）
        """
        if self.highlight_click:
            print(f"[DEBUG] 双击坐标: ({x}, {y})")
        
        # 执行第一次点击
        self.click(x, y, button)
        
        # 等待间隔
        time.sleep(interval)
        
        # 执行第二次点击
        self.click(x, y, button)
    
    def drag(
        self, 
        start_x: int, 
        start_y: int, 
        end_x: int, 
        end_y: int, 
        button: str = "left",
        duration: float = 0.5
    ) -> None:
        """
        执行拖拽操作（按下 -> 移动 -> 释放）
        
        Args:
            start_x: 起始 x 坐标
            start_y: 起始 y 坐标
            end_x: 结束 x 坐标
            end_y: 结束 y 坐标
            button: 鼠标按钮类型，"left" 或 "right"
            duration: 拖拽持续时间（秒）
        """
        if self.highlight_click:
            print(f"[DEBUG] 拖拽: ({start_x}, {start_y}) -> ({end_x}, {end_y})")
        
        # 移动到起始位置
        self.move_to(start_x, start_y)
        time.sleep(0.05)
        
        # 确定鼠标事件标志
        if button.lower() == "left":
            down_flag = win32con.MOUSEEVENTF_LEFTDOWN
            up_flag = win32con.MOUSEEVENTF_LEFTUP
        elif button.lower() == "right":
            down_flag = win32con.MOUSEEVENTF_RIGHTDOWN
            up_flag = win32con.MOUSEEVENTF_RIGHTUP
        else:
            raise ValueError(f"不支持的鼠标按钮类型: {button}")
        
        # 按下鼠标按钮
        win32api.mouse_event(down_flag, start_x, start_y, 0, 0)
        time.sleep(0.05)
        
        # 平滑移动到结束位置
        steps = max(10, int(duration * 20))  # 至少 10 步
        for i in range(steps + 1):
            t = i / steps
            current_x = int(start_x + (end_x - start_x) * t)
            current_y = int(start_y + (end_y - start_y) * t)
            win32api.SetCursorPos((current_x, current_y))
            time.sleep(duration / steps)
        
        # 释放鼠标按钮
        win32api.mouse_event(up_flag, end_x, end_y, 0, 0)
        time.sleep(self.action_delay)
    
    def press_key(self, key_code: int) -> None:
        """
        按下并释放指定的虚拟键码
        
        使用 win32api.keybd_event 发送键盘事件。
        常用虚拟键码：
        - VK_RETURN (Enter): 13
        - VK_ESCAPE (Esc): 27
        - VK_TAB: 9
        - VK_SPACE: 32
        
        Args:
            key_code: Windows 虚拟键码 (VK_*)
        """
        # 按下键
        win32api.keybd_event(key_code, 0, 0, 0)
        time.sleep(0.01)
        # 释放键
        win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(self.action_delay)
    
    def type_string(self, text: str, delay_between_keys: float = 0.05) -> None:
        """
        输入字符串文本
        
        注意：此方法使用 win32api 的字符映射，对于特殊字符可能不准确。
        对于复杂输入，建议使用其他方法（如 SendInput 或 clipboard）。
        
        Args:
            text: 要输入的文本字符串
            delay_between_keys: 每个字符之间的延迟（秒）
        """
        for char in text:
            # 获取字符的虚拟键码和扫描码
            vk_code = win32api.VkKeyScan(char)
            
            if vk_code == -1:
                # 如果无法映射（如中文字符），跳过或使用其他方法
                print(f"[WARNING] 无法输入字符: {char}")
                continue
            
            # 提取低字节（虚拟键码）和高字节（修饰键）
            vk = vk_code & 0xFF
            shift_state = (vk_code >> 8) & 0xFF
            
            # 处理 Shift 键（如果需要）
            if shift_state & 1:  # Shift 键按下
                win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            
            # 按下并释放字符键
            win32api.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            # 释放 Shift 键（如果之前按下了）
            if shift_state & 1:
                win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            time.sleep(delay_between_keys)
        
        time.sleep(self.action_delay)
    
    def type_string_simple(self, text: str) -> None:
        """
        使用简单方法输入字符串（仅适用于 ASCII 字符）
        
        对于包含特殊字符或中文的文本，此方法可能不准确。
        建议使用剪贴板方法或其他更可靠的方式。
        
        Args:
            text: 要输入的文本字符串
        """
        # 对于简单 ASCII 文本，直接使用 type_string
        self.type_string(text)
    
    def set_action_delay(self, delay: float) -> None:
        """
        设置操作延迟时间
        
        Args:
            delay: 新的延迟时间（秒）
        """
        self.action_delay = delay
    
    def set_highlight_click(self, enable: bool) -> None:
        """
        启用或禁用点击坐标调试输出
        
        Args:
            enable: 是否启用调试输出
        """
        self.highlight_click = enable


# 常用虚拟键码常量（方便使用）
class VK:
    """Windows 虚拟键码常量"""
    RETURN = win32con.VK_RETURN  # Enter
    ESCAPE = win32con.VK_ESCAPE  # Esc
    TAB = win32con.VK_TAB
    SPACE = win32con.VK_SPACE
    BACK = win32con.VK_BACK  # Backspace
    DELETE = win32con.VK_DELETE
    SHIFT = win32con.VK_SHIFT
    CONTROL = win32con.VK_CONTROL
    ALT = win32con.VK_MENU  # Alt 键
