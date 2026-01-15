"""
坐标映射与 DPI 缩放处理模块

将 YOLO 检测结果中的图像坐标（相对于截图）转换为屏幕物理坐标。
处理 Windows DPI 缩放导致的坐标偏移问题。
"""

from typing import Tuple


class CoordinateMapper:
    """
    坐标映射器类
    
    负责将截图中的相对坐标转换为屏幕上的绝对坐标。
    通过计算相对位置比例，然后投影到目标窗口的实际尺寸上。
    """
    
    def __init__(self, window_rect: Tuple[int, int, int, int]):
        """
        初始化坐标映射器
        
        Args:
            window_rect: 目标窗口的矩形坐标，格式为 (left, top, right, bottom)
                        或 (left, top, width, height)
        """
        if len(window_rect) == 4:
            # 如果传入的是 (left, top, right, bottom)
            self.window_left = window_rect[0]
            self.window_top = window_rect[1]
            self.window_width = window_rect[2] - window_rect[0]
            self.window_height = window_rect[3] - window_rect[1]
        else:
            raise ValueError("window_rect 必须是包含 4 个元素的元组")
        
        # 屏幕边界（用于安全检查）
        # 注意：这里假设使用主显示器，如果需要多显示器支持，需要更复杂的逻辑
        self.screen_width = self.window_left + self.window_width
        self.screen_height = self.window_top + self.window_height
    
    def map_to_screen(
        self, 
        img_x: float, 
        img_y: float, 
        img_width: int, 
        img_height: int
    ) -> Tuple[int, int]:
        """
        将图像坐标映射到屏幕物理坐标
        
        计算逻辑：
        1. 计算图像中的相对位置比例（x_ratio, y_ratio）
        2. 将比例投影到窗口的实际尺寸上
        3. 加上窗口的起始位置，得到屏幕绝对坐标
        
        Args:
            img_x: YOLO 检测结果中的 x 坐标（图像中心点或左上角，取决于 YOLO 输出格式）
            img_y: YOLO 检测结果中的 y 坐标
            img_width: 截图图像的宽度（像素）
            img_height: 截图图像的高度（像素）
        
        Returns:
            Tuple[int, int]: 屏幕物理坐标 (screen_x, screen_y)
            
        Raises:
            ValueError: 如果输入参数无效
        """
        if img_width <= 0 or img_height <= 0:
            raise ValueError(f"图像尺寸无效: width={img_width}, height={img_height}")
        
        # 计算相对位置比例（假设 img_x, img_y 是相对于图像左上角的坐标）
        # 如果 YOLO 输出的是中心坐标，需要根据实际情况调整
        x_ratio = img_x / img_width
        y_ratio = img_y / img_height
        
        # 将比例投影到窗口实际尺寸
        screen_x = self.window_left + (x_ratio * self.window_width)
        screen_y = self.window_top + (y_ratio * self.window_height)
        
        # 转换为整数坐标
        screen_x = int(round(screen_x))
        screen_y = int(round(screen_y))
        
        # 安全检查：确保坐标在屏幕边界内
        screen_x, screen_y = self._clamp_to_bounds(screen_x, screen_y)
        
        return (screen_x, screen_y)
    
    def map_bbox_to_screen(
        self,
        bbox: Tuple[float, float, float, float],
        img_width: int,
        img_height: int
    ) -> Tuple[int, int, int, int]:
        """
        将边界框（bbox）从图像坐标映射到屏幕坐标
        
        Args:
            bbox: 边界框坐标，格式为 (x_center, y_center, width, height) 或 (x1, y1, x2, y2)
            img_width: 截图图像的宽度
            img_height: 截图图像的高度
        
        Returns:
            Tuple[int, int, int, int]: 屏幕坐标边界框 (left, top, right, bottom)
        """
        # 假设 bbox 格式为 (x_center, y_center, width, height) - YOLO 标准格式
        if len(bbox) == 4:
            x_center, y_center, bbox_width, bbox_height = bbox
            
            # 转换为左上角和右下角坐标（图像坐标系）
            x1_img = x_center - bbox_width / 2
            y1_img = y_center - bbox_height / 2
            x2_img = x_center + bbox_width / 2
            y2_img = y_center + bbox_height / 2
            
            # 映射到屏幕坐标
            screen_x1, screen_y1 = self.map_to_screen(x1_img, y1_img, img_width, img_height)
            screen_x2, screen_y2 = self.map_to_screen(x2_img, y2_img, img_width, img_height)
            
            return (screen_x1, screen_y1, screen_x2, screen_y2)
        else:
            raise ValueError("bbox 必须是包含 4 个元素的元组")
    
    def _clamp_to_bounds(self, x: int, y: int) -> Tuple[int, int]:
        """
        将坐标限制在屏幕边界内
        
        Args:
            x: 原始 x 坐标
            y: 原始 y 坐标
        
        Returns:
            Tuple[int, int]: 限制后的坐标 (x, y)
        """
        # 限制在窗口区域内（加上一些安全边距）
        x = max(self.window_left, min(x, self.window_left + self.window_width - 1))
        y = max(self.window_top, min(y, self.window_top + self.window_height - 1))
        
        return (x, y)
    
    def update_window_rect(self, window_rect: Tuple[int, int, int, int]) -> None:
        """
        更新窗口矩形（当窗口位置或大小改变时调用）
        
        Args:
            window_rect: 新的窗口矩形坐标，格式为 (left, top, right, bottom)
        """
        self.window_left = window_rect[0]
        self.window_top = window_rect[1]
        self.window_width = window_rect[2] - window_rect[0]
        self.window_height = window_rect[3] - window_rect[1]
        
        self.screen_width = self.window_left + self.window_width
        self.screen_height = self.window_top + self.window_height
