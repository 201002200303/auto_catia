"""
窗口句柄管理模块

使用 pywin32 库管理 CATIA 窗口的查找、激活和坐标获取。
支持 DPI 感知，确保在高分辨率屏幕上坐标计算的准确性。
"""

import ctypes
from typing import Optional, Tuple
import win32gui
import win32con
import win32api


# 设置进程 DPI 感知，避免高分辨率屏幕上的坐标偏移问题
# SetProcessDpiAwareness(1) = PROCESS_PER_MONITOR_DPI_AWARE
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    # 如果 SetProcessDpiAwareness 不可用（Windows 7 或更早版本），尝试旧版 API
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass  # 如果都不可用，继续执行（可能在某些系统上会有坐标偏移）


class WindowManager:
    """
    窗口管理器类
    
    负责查找、激活和管理目标应用程序窗口（如 CATIA）。
    提供窗口句柄（HWND）和窗口区域坐标的获取功能。
    """
    
    def __init__(self, window_title_pattern: str = "CATIA"):
        """
        初始化窗口管理器
        
        Args:
            window_title_pattern: 窗口标题匹配模式（部分匹配）
        """
        self.window_title_pattern = window_title_pattern
        self.hwnd: Optional[int] = None
        self._found_window_title: Optional[str] = None
    
    def find_window(self) -> int:
        """
        查找匹配的窗口句柄
        
        使用 win32gui.EnumWindows 遍历所有窗口，查找标题包含指定模式的窗口。
        
        Returns:
            int: 窗口句柄 (HWND)
            
        Raises:
            RuntimeError: 如果未找到匹配的窗口
        """
        def enum_windows_callback(hwnd: int, windows: list):
            """EnumWindows 的回调函数，收集匹配的窗口"""
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if self.window_title_pattern.lower() in window_title.lower():
                    windows.append((hwnd, window_title))
            return True
        
        matching_windows = []
        # 枚举所有顶层窗口
        win32gui.EnumWindows(enum_windows_callback, matching_windows)
        
        if not matching_windows:
            raise RuntimeError(
                f"未找到标题包含 '{self.window_title_pattern}' 的窗口。"
                f"请确保 CATIA 应用程序已启动。"
            )
        
        # 如果找到多个匹配窗口，选择第一个（通常是最新的）
        self.hwnd, self._found_window_title = matching_windows[0]
        return self.hwnd
    
    def activate_window(self) -> None:
        """
        激活窗口并置于前台
        
        将目标窗口置于前台，如果窗口最小化则恢复显示。
        使用多种方法尝试激活窗口，以应对 Windows 的安全限制。
        
        Raises:
            RuntimeError: 如果窗口句柄无效或所有激活方法都失败
        """
        if self.hwnd is None:
            self.find_window()
        
        if not win32gui.IsWindow(self.hwnd):
            raise RuntimeError("窗口句柄无效，窗口可能已关闭。")
        
        # 方法1: 标准方法（优先尝试）
        try:
            # 检查窗口是否最小化
            placement = win32gui.GetWindowPlacement(self.hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                # 恢复窗口（从最小化状态恢复）
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            
            # 尝试将窗口置于前台
            win32gui.SetForegroundWindow(self.hwnd)
            # 确保窗口可见且激活
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
            
            # 验证是否成功（检查窗口是否在前台）
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == self.hwnd:
                return  # 成功激活
            
        except Exception as e:
            # 如果标准方法失败，尝试替代方法
            pass
        
        # 方法2: 使用 AttachThreadInput（更可靠但需要更多权限）
        try:
            import win32process
            
            # 获取当前线程和窗口线程的 ID
            current_thread_id = win32api.GetCurrentThreadId()
            window_thread_id = win32process.GetWindowThreadProcessId(self.hwnd)[0]
            
            # 如果线程不同，附加线程输入
            if current_thread_id != window_thread_id:
                win32gui.AttachThreadInput(current_thread_id, window_thread_id, True)
            
            # 恢复窗口（如果最小化）
            placement = win32gui.GetWindowPlacement(self.hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            
            # 激活窗口
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
            
            # 分离线程
            if current_thread_id != window_thread_id:
                win32gui.AttachThreadInput(current_thread_id, window_thread_id, False)
            
            # 验证是否成功
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == self.hwnd:
                return  # 成功激活
                
        except Exception as e:
            # AttachThreadInput 也可能失败，继续尝试其他方法
            pass
        
        # 方法3: 使用 BringWindowToTop（备选方案）
        try:
            placement = win32gui.GetWindowPlacement(self.hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            
            win32gui.BringWindowToTop(self.hwnd)
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
            
            # 验证
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == self.hwnd:
                return  # 成功激活
                
        except Exception as e:
            pass
        
        # 如果所有方法都失败，检查窗口是否至少可见
        if win32gui.IsWindowVisible(self.hwnd):
            # 窗口可见但无法激活，这可能是 Windows 安全限制
            # 返回警告而不是错误，因为窗口至少是可见的
            raise RuntimeError(
                "无法将窗口置于前台（可能是 Windows 安全限制）。"
                "窗口已恢复显示，但可能不在前台。"
                "请手动点击 CATIA 窗口以确保其处于活动状态。"
            )
        else:
            raise RuntimeError("所有窗口激活方法都失败，窗口可能无法访问。")
    
    def get_window_rect(self) -> Tuple[int, int, int, int]:
        """
        获取窗口客户区域坐标
        
        返回窗口的矩形区域坐标，格式为 (left, top, right, bottom)。
        注意：这里返回的是窗口矩形，包含标题栏和边框。
        如果需要纯客户区域，可以使用 win32gui.GetClientRect 配合窗口位置计算。
        
        Returns:
            Tuple[int, int, int, int]: (left, top, right, bottom) 坐标
            
        Raises:
            RuntimeError: 如果窗口句柄无效
        """
        if self.hwnd is None:
            self.find_window()
        
        if not win32gui.IsWindow(self.hwnd):
            raise RuntimeError("窗口句柄无效，窗口可能已关闭。")
        
        # 获取窗口矩形（包含标题栏和边框）
        rect = win32gui.GetWindowRect(self.hwnd)
        return rect  # (left, top, right, bottom)
    
    def get_client_rect(self) -> Tuple[int, int, int, int]:
        """
        获取窗口客户区域坐标（不含标题栏和边框）
        
        返回客户区域的相对坐标和窗口位置，用于更精确的坐标映射。
        
        Returns:
            Tuple[int, int, int, int]: (left, top, right, bottom) 客户区域坐标（相对于窗口）
        """
        if self.hwnd is None:
            self.find_window()
        
        if not win32gui.IsWindow(self.hwnd):
            raise RuntimeError("窗口句柄无效，窗口可能已关闭。")
        
        # 获取客户区域矩形（相对于窗口，不含标题栏和边框）
        client_rect = win32gui.GetClientRect(self.hwnd)
        # 将客户区域坐标转换为屏幕坐标
        left_top = win32gui.ClientToScreen(self.hwnd, (client_rect[0], client_rect[1]))
        right_bottom = win32gui.ClientToScreen(self.hwnd, (client_rect[2], client_rect[3]))
        
        return (left_top[0], left_top[1], right_bottom[0], right_bottom[1])
    
    def is_window_valid(self) -> bool:
        """
        检查窗口句柄是否仍然有效
        
        Returns:
            bool: 如果窗口存在且有效返回 True，否则返回 False
        """
        if self.hwnd is None:
            return False
        return win32gui.IsWindow(self.hwnd)
    
    def get_window_title(self) -> Optional[str]:
        """
        获取当前窗口的标题
        
        Returns:
            Optional[str]: 窗口标题，如果窗口无效则返回 None
        """
        if self.hwnd is None:
            return None
        if not self.is_window_valid():
            return None
        return win32gui.GetWindowText(self.hwnd)
