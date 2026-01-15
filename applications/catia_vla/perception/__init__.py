"""
感知层模块

提供视觉推理服务，包括目标检测和滑动窗口推理功能。
"""

from .inference import VisionService, load_image, visualize_and_save_positions

__all__ = [
    'VisionService',
    'load_image',
    'visualize_and_save_positions',
]


