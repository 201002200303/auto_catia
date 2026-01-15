"""
CATIA VLA 工具集 - OxyGent FunctionHub 集成

将 CATIA VLA 项目的感知层和驱动层功能封装为 OxyGent 工具。
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Optional
from pydantic import Field

from oxygent.oxy import FunctionHub

# 配置日志
logger = logging.getLogger(__name__)

# 动态添加 catia_vla 项目路径
_current_dir = Path(__file__).parent
_catia_vla_path = _current_dir.parent / "applications" / "catia_vla"
if _catia_vla_path.exists():
    sys.path.insert(0, str(_catia_vla_path.parent))
else:
    logger.warning(f"CATIA VLA 路径不存在: {_catia_vla_path}")

# 初始化 FunctionHub
catia_tools = FunctionHub(name="catia_tools", desc="CATIA 自动化建模工具集")

# ==================== 感知层工具 ====================

# 延迟加载 VisionService（避免启动时加载模型）
_vision_service = None
_vision_service_model_path = None


def _get_vision_service(model_path: Optional[str] = None):
    """获取或初始化 VisionService（单例模式）"""
    global _vision_service, _vision_service_model_path
    
    # 参数验证：确保 model_path 是字符串或 None
    try:
        from pydantic import FieldInfo
        if isinstance(model_path, FieldInfo):
            model_path = None
    except ImportError:
        pass  # pydantic 不可用时跳过
    
    if model_path is not None and not isinstance(model_path, str):
        logger.warning(f"model_path 类型错误: {type(model_path)}, 使用默认值")
        model_path = None
    
    # 确定模型路径
    if model_path is None:
        # 默认模型路径
        default_model = _catia_vla_path / "perception" / "weights" / "best.pt"
        if default_model.exists():
            model_path = str(default_model)
        else:
            # 尝试其他可能的路径
            alt_paths = [
                _catia_vla_path / "perception" / "runs" / "detect" / "dataset6_yolo11s2" / "weights" / "best.pt",
                _catia_vla_path / "perception" / "runs" / "detect" / "dataset3_yolo11s2" / "weights" / "best.pt",
            ]
            for alt_path in alt_paths:
                if alt_path.exists():
                    model_path = str(alt_path)
                    break
    
    if model_path is None or not isinstance(model_path, str):
        raise FileNotFoundError(
            "未找到 YOLO 模型文件。请确保模型文件存在于以下位置之一：\n"
            "- applications/catia_vla/perception/weights/best.pt\n"
            "- applications/catia_vla/perception/runs/detect/*/weights/best.pt"
        )
    
    # 验证文件是否存在
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    
    # 如果模型路径改变或服务未初始化，重新加载
    if _vision_service is None or _vision_service_model_path != model_path:
        try:
            from applications.catia_vla.perception.inference import VisionService
            import torch
            
            # 设备选择逻辑：优先使用环境变量，然后尝试 CUDA，失败则使用 CPU
            device = os.getenv("CATIA_VLA_DEVICE", None)
            
            if device is None:
                # 尝试检测 CUDA 是否可用且兼容
                if torch.cuda.is_available():
                    try:
                        # 测试 CUDA 是否真的可用（避免兼容性问题）
                        test_tensor = torch.zeros(1).cuda()
                        del test_tensor
                        torch.cuda.empty_cache()
                        device = 'cuda'
                        logger.info("检测到可用的 CUDA 设备")
                    except Exception as cuda_error:
                        logger.warning(f"CUDA 检测失败，将使用 CPU: {cuda_error}")
                        device = 'cpu'
                else:
                    device = 'cpu'
                    logger.info("未检测到 CUDA，使用 CPU")
            else:
                logger.info(f"使用环境变量指定的设备: {device}")
            
            # 尝试加载模型，如果 CUDA 失败则回退到 CPU
            try:
                _vision_service = VisionService(model_path=model_path, device=device)
                _vision_service_model_path = model_path
                logger.info(f"VisionService 已加载，模型路径: {model_path}, 设备: {device}")
            except RuntimeError as e:
                if 'cuda' in str(e).lower() or 'cuda' in device.lower():
                    logger.warning(f"CUDA 加载失败，尝试使用 CPU: {e}")
                    try:
                        _vision_service = VisionService(model_path=model_path, device='cpu')
                        _vision_service_model_path = model_path
                        logger.info(f"VisionService 已加载（CPU fallback），模型路径: {model_path}")
                    except Exception as cpu_error:
                        logger.error(f"CPU 加载也失败: {cpu_error}")
                        raise
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"加载 VisionService 失败: {e}")
            raise
    
    return _vision_service


@catia_tools.tool(
    description=(
        "识别 CATIA 界面截图中的 UI 元素（图标、按钮、菜单等），"
        "返回所有检测到的元素及其坐标信息。使用 YOLO 模型进行目标检测，"
        "支持高分辨率屏幕的滑动窗口检测。"
    )
)
def detect_ui_elements(
    image_path: str = Field(
        description="屏幕截图文件的完整路径（绝对路径或相对于项目根目录的路径）"
    ),
    model_path: Optional[str] = Field(
        default=None,
        description="YOLO 模型文件路径（可选，默认使用预配置路径）"
    ),
    slice_size: int = Field(
        default=640,
        description="滑动窗口切片大小（默认 640，YOLO 标准输入尺寸）"
    ),
    overlap_ratio: float = Field(
        default=0.2,
        description="滑动窗口重叠比例（默认 0.2，即 20% 重叠）"
    ),
    conf_threshold: float = Field(
        default=0.25,
        description="检测置信度阈值（默认 0.25）"
    ),
) -> str:
    """
    识别 CATIA 界面元素
    
    Returns:
        JSON 字符串，格式：
        [
            {
                "label": "002",
                "bbox": [x1, y1, x2, y2],
                "confidence": 0.95
            },
            ...
        ]
    """
    try:
        # 参数验证：确保参数是实际值而不是 Field 对象
        try:
            from pydantic.fields import FieldInfo
            _has_field_info = True
        except ImportError:
            try:
                from pydantic import FieldInfo
                _has_field_info = True
            except ImportError:
                _has_field_info = False
        
        if _has_field_info:
            if isinstance(image_path, FieldInfo):
                raise ValueError("image_path 参数解析错误：收到了 Field 对象而不是实际值")
            if isinstance(model_path, FieldInfo):
                model_path = None  # 使用默认值
            if isinstance(slice_size, FieldInfo):
                slice_size = 640
            if isinstance(overlap_ratio, FieldInfo):
                overlap_ratio = 0.2
            if isinstance(conf_threshold, FieldInfo):
                conf_threshold = 0.25
        
        # 确保 model_path 是字符串或 None
        if model_path is not None and not isinstance(model_path, str):
            logger.warning(f"model_path 类型错误: {type(model_path)}, 使用默认值")
            model_path = None
        
        # 类型转换和验证
        if not isinstance(image_path, str):
            raise TypeError(f"image_path 必须是字符串，收到: {type(image_path)}")
        if slice_size is not None and not isinstance(slice_size, (int, float)):
            slice_size = 640
        if overlap_ratio is not None and not isinstance(overlap_ratio, (int, float)):
            overlap_ratio = 0.2
        if conf_threshold is not None and not isinstance(conf_threshold, (int, float)):
            conf_threshold = 0.25
        
        # 检查文件是否存在
        if not os.path.isabs(image_path):
            # 相对路径，尝试多个可能的位置
            possible_paths = [
                image_path,
                str(_catia_vla_path / image_path),
                str(_current_dir.parent / image_path),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    image_path = path
                    break
            else:
                raise FileNotFoundError(f"截图文件不存在: {image_path}")
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"截图文件不存在: {image_path}")
        
        # 获取 VisionService
        vision_service = _get_vision_service(model_path)
        
        # 执行检测（同步函数，FunctionHub 会自动包装为异步）
        logger.info(f"开始检测 UI 元素: {image_path}")
        results = vision_service.detect_full_screen_tiled(
            image_path=image_path,
            slice_size=slice_size,
            overlap_ratio=overlap_ratio,
            conf_threshold=conf_threshold,
        )
        
        logger.info(f"检测完成，发现 {len(results)} 个 UI 元素")
        return json.dumps(results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        error_msg = f"检测 UI 元素失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@catia_tools.tool(
    description=(
        "模拟键盘按键操作。"
        "支持常用的功能键，如 Enter, Esc, Tab, Space 等。"
    )
)
def press_key(
    key_name: str = Field(description="按键名称（如 'enter', 'esc', 'tab', 'space'）")
) -> str:
    """
    模拟按键
    
    Returns:
        操作结果 JSON 字符串
    """
    try:
        # 参数验证
        if not isinstance(key_name, str):
            # 尝试处理 FieldInfo 情况
            try:
                from pydantic.fields import FieldInfo
                if isinstance(key_name, FieldInfo):
                    raise ValueError("key_name 参数解析错误：收到了 Field 对象")
            except ImportError:
                try:
                    from pydantic import FieldInfo
                    if isinstance(key_name, FieldInfo):
                        raise ValueError("key_name 参数解析错误：收到了 Field 对象")
                except ImportError:
                    pass
            raise ValueError(f"key_name 必须是字符串，收到: {type(key_name)}")
            
        from applications.catia_vla.driver.controller import VK
        
        key_map = {
            "enter": VK.RETURN,
            "return": VK.RETURN,
            "esc": VK.ESCAPE,
            "escape": VK.ESCAPE,
            "tab": VK.TAB,
            "space": VK.SPACE,
            "back": VK.BACK,
            "backspace": VK.BACK,
            "delete": VK.DELETE,
            "del": VK.DELETE,
            "shift": VK.SHIFT,
            "ctrl": VK.CONTROL,
            "alt": VK.ALT
        }
        
        key_code = key_map.get(key_name.lower())
        if key_code is None:
             return json.dumps({"error": f"不支持的按键: {key_name}"}, ensure_ascii=False)

        controller = _get_controller()
        controller.press_key(key_code)
        
        result = {
            "success": True, 
            "message": f"成功按下按键: {key_name}"
        }
        logger.info(f"按键操作成功: {key_name}")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"按键操作失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


# ==================== 驱动层工具 ====================

# 延迟加载驱动组件
_controller = None
_window_manager = None


def _get_controller():
    """获取或初始化 InputController（单例模式）"""
    global _controller
    if _controller is None:
        try:
            from applications.catia_vla.driver.controller import InputController
            _controller = InputController(action_delay=0.1, highlight_click=True)
            logger.info("InputController 已初始化")
        except Exception as e:
            logger.error(f"初始化 InputController 失败: {e}")
            raise
    return _controller


def _get_window_manager():
    """获取或初始化 WindowManager（单例模式）"""
    global _window_manager
    if _window_manager is None:
        try:
            from applications.catia_vla.driver.window_manager import WindowManager
            _window_manager = WindowManager(window_title_pattern="CATIA")
            logger.info("WindowManager 已初始化")
        except Exception as e:
            logger.error(f"初始化 WindowManager 失败: {e}")
            raise
    return _window_manager


@catia_tools.tool(
    description=(
        "截取当前屏幕的全屏截图并保存。"
        "如果未指定保存路径，将保存到临时目录。"
    )
)
def capture_screen(
    save_path: Optional[str] = Field(
        default=None,
        description="截图保存路径（可选，默认保存到临时文件）"
    )
) -> str:
    """
    截取全屏截图
    
    Returns:
        保存的文件路径
    """
    try:
        from applications.catia_vla.driver.screenshot_tool import capture_full_screen

        if not isinstance(save_path, str) or not save_path.strip():
            normalized_save_path: Optional[str] = None
        else:
            normalized_save_path = save_path

        file_path = capture_full_screen(normalized_save_path)
        logger.info(f"截图已保存: {file_path}")
        return json.dumps({
            "success": True,
            "file_path": file_path,
            "message": f"截图已保存到: {file_path}"
        }, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"截图失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@catia_tools.tool(
    description=(
        "在指定坐标执行鼠标点击操作。"
        "坐标应为屏幕绝对坐标。建议先使用 detect_ui_elements 获取元素坐标。"
    )
)
def click_element(
    x: int = Field(description="目标 x 坐标（屏幕绝对坐标）"),
    y: int = Field(description="目标 y 坐标（屏幕绝对坐标）"),
    button: str = Field(
        default="left",
        description="鼠标按钮类型：'left' 或 'right'（默认 'left'）"
    )
) -> str:
    """
    点击指定坐标
    
    Returns:
        操作结果 JSON 字符串
    """
    try:
        # 参数验证：确保参数是实际值而不是 Field 对象
        if not isinstance(button, str):
            button = "left"

        controller = _get_controller()
        controller.click(x, y, button=button)
        
        result = {
            "success": True,
            "message": f"成功点击坐标 ({x}, {y})",
            "coordinates": {"x": x, "y": y},
            "button": button
        }
        logger.info(f"点击操作成功: ({x}, {y})")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"点击操作失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@catia_tools.tool(
    description=(
        "在指定坐标执行鼠标双击操作。"
        "用于需要双击激活的功能（如打开文件、启动命令等）。"
    )
)
def double_click_element(
    x: int = Field(description="目标 x 坐标（屏幕绝对坐标）"),
    y: int = Field(description="目标 y 坐标（屏幕绝对坐标）"),
    button: str = Field(
        default="left",
        description="鼠标按钮类型：'left' 或 'right'（默认 'left'）"
    )
) -> str:
    """
    双击指定坐标
    
    Returns:
        操作结果 JSON 字符串
    """
    try:
        # 参数验证：确保参数是实际值而不是 Field 对象
        if not isinstance(button, str):
            button = "left"

        controller = _get_controller()
        controller.double_click(x, y, button=button)
        
        result = {
            "success": True,
            "message": f"成功双击坐标 ({x}, {y})",
            "coordinates": {"x": x, "y": y},
            "button": button
        }
        logger.info(f"双击操作成功: ({x}, {y})")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"双击操作失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@catia_tools.tool(
    description=(
        "查找并激活 CATIA 窗口。"
        "确保 CATIA 应用程序窗口处于活动状态，以便后续操作能够正确执行。"
        "注意：由于 Windows 安全限制，在某些情况下可能无法自动激活窗口，"
        "此时需要手动点击 CATIA 窗口。"
    )
)
def activate_catia_window() -> str:
    """
    激活 CATIA 窗口
    
    Returns:
        操作结果 JSON 字符串
    """
    try:
        window_manager = _get_window_manager()
        hwnd = window_manager.find_window()
        
        if hwnd is None:
            return json.dumps({
                "error": "未找到 CATIA 窗口。请确保 CATIA 应用程序已启动。"
            }, ensure_ascii=False)
        
        # 尝试激活窗口
        activation_success = False
        activation_warning = None
        
        try:
            window_manager.activate_window()
            activation_success = True
        except RuntimeError as e:
            error_msg = str(e)
            # 检查是否是 Windows 安全限制导致的警告
            if "Windows 安全限制" in error_msg or "无法将窗口置于前台" in error_msg:
                activation_warning = error_msg
                # 这种情况下窗口可能已经可见，不算完全失败
                activation_success = True  # 部分成功
            else:
                raise  # 重新抛出其他错误
        
        window_rect = window_manager.get_window_rect()
        window_title = window_manager.get_window_title()
        
        result = {
            "success": activation_success,
            "message": "CATIA 窗口已激活" if activation_success and not activation_warning else "CATIA 窗口已找到但激活受限",
            "window_title": window_title,
            "window_rect": window_rect
        }
        
        if activation_warning:
            result["warning"] = activation_warning
            result["note"] = "由于 Windows 安全限制，窗口可能不在前台。请手动点击 CATIA 窗口以确保其处于活动状态。"
            logger.warning(f"CATIA 窗口激活受限: {activation_warning}")
        else:
            logger.info(f"CATIA 窗口已激活: {window_title}")
        
        return json.dumps(result, ensure_ascii=False)
        
    except RuntimeError as e:
        error_msg = str(e)
        # 检查是否是"未找到窗口"的错误
        if "未找到" in error_msg or "CATIA 应用程序已启动" in error_msg:
            return json.dumps({
                "error": error_msg,
                "note": "请确保 CATIA 应用程序已启动，并且窗口标题包含 'CATIA'"
            }, ensure_ascii=False)
        else:
            error_msg = f"激活 CATIA 窗口失败: {error_msg}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"激活 CATIA 窗口失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@catia_tools.tool(
    description=(
        "输入文本到当前活动窗口。"
        "用于在 CATIA 中输入参数、文件名等文本内容。"
    )
)
def input_text(
    text: str = Field(description="要输入的文本内容"),
    delay: float = Field(
        default=0.05,
        description="每个字符输入之间的延迟（秒，默认 0.05）"
    )
) -> str:
    """
    输入文本
    
    Returns:
        操作结果 JSON 字符串
    """
    try:
        # 参数验证
        if not isinstance(text, str):
            try:
                from pydantic import FieldInfo
                if isinstance(text, FieldInfo):
                     raise ValueError("text 参数解析错误：收到了 Field 对象")
            except ImportError:
                pass
            raise ValueError(f"text 必须是字符串，收到: {type(text)}")

        if not isinstance(delay, (int, float)):
             delay = 0.05

        controller = _get_controller()
        controller.type_string(text, delay_between_keys=delay)
        
        result = {
            "success": True,
            "message": f"成功输入文本: {text}",
            "text_length": len(text)
        }
        logger.info(f"文本输入成功: {text[:50]}...")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"文本输入失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg}, ensure_ascii=False)
