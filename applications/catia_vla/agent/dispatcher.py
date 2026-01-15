"""
Unified Dispatcher - 混合驱动决策调度器

根据操作类型自动选择执行模态（API/视觉/混合），
支持失败降级和重试策略。

Author: CATIA VLA Team
"""

import json
import logging
from enum import Enum
from typing import Dict, Callable, Any, Optional, List
from dataclasses import dataclass, field
import asyncio

logger = logging.getLogger(__name__)


class ExecutionModality(Enum):
    """执行模态枚举"""
    API = "api"
    VISION = "vision"
    HYBRID = "hybrid"


@dataclass
class ExecutionResult:
    """执行结果数据类"""
    success: bool
    modality: ExecutionModality
    output: Any
    error: Optional[str] = None
    fallback_used: bool = False
    retry_count: int = 0
    execution_time_ms: float = 0.0


@dataclass
class OperationMapping:
    """操作映射配置"""
    # API 支持的操作类型
    api_operations: set = field(default_factory=lambda: {
        # 几何建模操作
        "create_part", "create_new_part",
        "create_sketch", "create_rectangle", "create_rectangle_sketch",
        "create_pad", "create_extrude", "create_fillet",
        "create_chamfer", "create_plane", "create_point",
        "create_line", "create_circle", "create_spline",
        # 布尔运算
        "boolean_join", "boolean_split", "boolean_trim",
        "join_surfaces", "split_geometry",
        # 变换操作
        "mirror", "symmetry", "translate", "rotate", "scale",
        # 参数操作
        "set_parameter", "get_parameter", "get_part_info",
        # 文件操作
        "save_part", "export_part",
    })
    
    # 必须使用视觉的操作
    vision_only_operations: set = field(default_factory=lambda: {
        # GUI 交互
        "click_toolbar", "click_menu", "click_button",
        "handle_dialog", "dismiss_dialog", "confirm_dialog",
        "select_tree_node", "expand_tree_node",
        "drag_drop", "drag_element",
        # 自定义操作
        "custom_macro", "run_macro",
        "select_from_dropdown", "input_dialog_text",
        # 视觉检测
        "detect_ui_elements", "capture_screen",
        "find_element", "wait_for_element",
    })
    
    # 混合操作（优先 API，失败则视觉）
    hybrid_operations: set = field(default_factory=lambda: {
        "open_file", "close_file", "new_document",
        "undo", "redo",
        "zoom_fit", "zoom_in", "zoom_out",
        "select_body", "select_feature",
    })


class UnifiedDispatcher:
    """
    混合驱动决策调度器
    
    职责：
    1. 根据操作类型选择执行模态
    2. 管理 API 和视觉工具的调用
    3. 处理失败降级逻辑
    4. 支持重试策略
    
    Usage:
        dispatcher = UnifiedDispatcher(
            api_tools={"create_pad": create_pad_func, ...},
            vision_tools={"click_element": click_func, ...}
        )
        result = await dispatcher.execute("create_pad", {"height": 100})
    """
    
    def __init__(
        self,
        api_tools: Dict[str, Callable],
        vision_tools: Dict[str, Callable],
        enable_fallback: bool = True,
        max_retries: int = 2,
        retry_delay: float = 0.5,
        operation_mapping: Optional[OperationMapping] = None
    ):
        """
        初始化调度器
        
        Args:
            api_tools: API 工具字典 {tool_name: callable}
            vision_tools: 视觉工具字典 {tool_name: callable}
            enable_fallback: 是否启用失败降级
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            operation_mapping: 操作映射配置
        """
        self.api_tools = api_tools or {}
        self.vision_tools = vision_tools or {}
        self.enable_fallback = enable_fallback
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.mapping = operation_mapping or OperationMapping()
        
        # 执行统计
        self._stats = {
            "api_calls": 0,
            "vision_calls": 0,
            "fallbacks": 0,
            "retries": 0,
            "failures": 0,
        }
        
        logger.info(
            f"UnifiedDispatcher 初始化完成: "
            f"API 工具 {len(self.api_tools)} 个, "
            f"视觉工具 {len(self.vision_tools)} 个"
        )
    
    def get_modality(self, operation: str) -> ExecutionModality:
        """
        根据操作类型返回执行模态
        
        Args:
            operation: 操作名称
            
        Returns:
            ExecutionModality: API, VISION, 或 HYBRID
        """
        # 标准化操作名称
        op_lower = operation.lower().replace("-", "_")
        
        # 检查 API 支持
        if op_lower in self.mapping.api_operations:
            return ExecutionModality.API
        
        # 检查视觉专属
        if op_lower in self.mapping.vision_only_operations:
            return ExecutionModality.VISION
        
        # 检查混合操作
        if op_lower in self.mapping.hybrid_operations:
            return ExecutionModality.HYBRID
        
        # 检查工具可用性
        if operation in self.api_tools:
            return ExecutionModality.API
        if operation in self.vision_tools:
            return ExecutionModality.VISION
        
        # 默认混合模式
        return ExecutionModality.HYBRID
    
    def is_operation_supported(self, operation: str) -> bool:
        """检查操作是否被支持"""
        return (
            operation in self.api_tools or 
            operation in self.vision_tools
        )
    
    async def execute(
        self,
        operation: str,
        params: Dict[str, Any],
        force_modality: Optional[ExecutionModality] = None
    ) -> ExecutionResult:
        """
        执行操作，自动选择模态
        
        Args:
            operation: 操作名称
            params: 操作参数
            force_modality: 强制使用的模态（可选）
            
        Returns:
            ExecutionResult: 执行结果
        """
        import time
        start_time = time.time()
        
        # 确定执行模态
        modality = force_modality or self.get_modality(operation)
        
        logger.info(f"执行操作: {operation}, 模态: {modality.value}")
        
        result = None
        
        if modality == ExecutionModality.API:
            result = await self._execute_with_fallback(
                operation, params, 
                primary_executor=self._execute_api,
                fallback_executor=self._execute_vision if self.enable_fallback else None
            )
            
        elif modality == ExecutionModality.VISION:
            result = await self._execute_with_retry(
                operation, params, self._execute_vision
            )
            
        else:  # HYBRID
            result = await self._execute_with_fallback(
                operation, params,
                primary_executor=self._execute_api,
                fallback_executor=self._execute_vision
            )
        
        # 计算执行时间
        result.execution_time_ms = (time.time() - start_time) * 1000
        
        # 更新统计
        if not result.success:
            self._stats["failures"] += 1
        
        return result
    
    async def _execute_with_fallback(
        self,
        operation: str,
        params: Dict[str, Any],
        primary_executor: Callable,
        fallback_executor: Optional[Callable] = None
    ) -> ExecutionResult:
        """带降级的执行"""
        # 尝试主执行器
        result = await self._execute_with_retry(operation, params, primary_executor)
        
        # 如果失败且有降级执行器
        if not result.success and fallback_executor and self.enable_fallback:
            logger.warning(f"主执行器失败，降级到备用执行器: {result.error}")
            self._stats["fallbacks"] += 1
            
            fallback_result = await self._execute_with_retry(
                operation, params, fallback_executor
            )
            fallback_result.fallback_used = True
            return fallback_result
        
        return result
    
    async def _execute_with_retry(
        self,
        operation: str,
        params: Dict[str, Any],
        executor: Callable
    ) -> ExecutionResult:
        """带重试的执行"""
        last_error = None
        retry_count = 0
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await executor(operation, params)
                result.retry_count = retry_count
                
                if result.success:
                    return result
                    
                last_error = result.error
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"执行异常 (尝试 {attempt + 1}): {e}")
            
            # 重试延迟
            if attempt < self.max_retries:
                retry_count += 1
                self._stats["retries"] += 1
                await asyncio.sleep(self.retry_delay)
        
        # 所有重试都失败
        return ExecutionResult(
            success=False,
            modality=ExecutionModality.HYBRID,
            output=None,
            error=f"操作失败（已重试 {retry_count} 次）: {last_error}",
            retry_count=retry_count
        )
    
    async def _execute_api(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> ExecutionResult:
        """执行 API 模态操作"""
        self._stats["api_calls"] += 1
        
        if operation not in self.api_tools:
            return ExecutionResult(
                success=False,
                modality=ExecutionModality.API,
                output=None,
                error=f"API 工具不存在: {operation}"
            )
        
        try:
            tool_func = self.api_tools[operation]
            
            # 支持同步和异步函数
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**params)
            else:
                result = tool_func(**params)
            
            # 解析结果
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    success = parsed.get("success", True)
                    error = parsed.get("message") if not success else None
                    output = parsed.get("data", parsed)
                except json.JSONDecodeError:
                    success = True
                    output = result
                    error = None
            else:
                success = True
                output = result
                error = None
            
            return ExecutionResult(
                success=success,
                modality=ExecutionModality.API,
                output=output,
                error=error
            )
            
        except Exception as e:
            logger.error(f"API 执行异常: {operation} - {e}")
            return ExecutionResult(
                success=False,
                modality=ExecutionModality.API,
                output=None,
                error=str(e)
            )
    
    async def _execute_vision(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> ExecutionResult:
        """执行视觉模态操作"""
        self._stats["vision_calls"] += 1
        
        if operation not in self.vision_tools:
            return ExecutionResult(
                success=False,
                modality=ExecutionModality.VISION,
                output=None,
                error=f"视觉工具不存在: {operation}"
            )
        
        try:
            tool_func = self.vision_tools[operation]
            
            # 支持同步和异步函数
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**params)
            else:
                result = tool_func(**params)
            
            # 解析结果
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    success = parsed.get("success", True) if "error" not in parsed else False
                    error = parsed.get("error") if not success else None
                    output = parsed
                except json.JSONDecodeError:
                    success = True
                    output = result
                    error = None
            else:
                success = True
                output = result
                error = None
            
            return ExecutionResult(
                success=success,
                modality=ExecutionModality.VISION,
                output=output,
                error=error
            )
            
        except Exception as e:
            logger.error(f"视觉执行异常: {operation} - {e}")
            return ExecutionResult(
                success=False,
                modality=ExecutionModality.VISION,
                output=None,
                error=str(e)
            )
    
    def get_stats(self) -> Dict[str, int]:
        """获取执行统计"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        for key in self._stats:
            self._stats[key] = 0
    
    def get_available_operations(self) -> Dict[str, List[str]]:
        """获取所有可用操作"""
        return {
            "api_operations": list(self.api_tools.keys()),
            "vision_operations": list(self.vision_tools.keys()),
            "supported_api_types": list(self.mapping.api_operations),
            "supported_vision_types": list(self.mapping.vision_only_operations),
        }


# ==================== 辅助函数 ====================

def create_dispatcher_from_function_hubs(
    api_hub,
    vision_hub,
    **kwargs
) -> UnifiedDispatcher:
    """
    从 FunctionHub 创建调度器
    
    Args:
        api_hub: API FunctionHub 实例
        vision_hub: 视觉 FunctionHub 实例
        **kwargs: 传递给 UnifiedDispatcher 的其他参数
        
    Returns:
        UnifiedDispatcher 实例
    """
    # 从 FunctionHub 提取工具函数
    api_tools = {}
    vision_tools = {}
    
    if hasattr(api_hub, 'func_dict'):
        for name, (desc, func) in api_hub.func_dict.items():
            api_tools[name] = func
    
    if hasattr(vision_hub, 'func_dict'):
        for name, (desc, func) in vision_hub.func_dict.items():
            vision_tools[name] = func
    
    return UnifiedDispatcher(
        api_tools=api_tools,
        vision_tools=vision_tools,
        **kwargs
    )


# ==================== 使用示例 ====================

async def _demo():
    """演示用法"""
    # 模拟工具
    async def mock_create_pad(**kwargs):
        return json.dumps({"success": True, "data": {"pad_name": "Pad_100mm"}})
    
    async def mock_click_element(**kwargs):
        return json.dumps({"success": True, "message": "点击成功"})
    
    dispatcher = UnifiedDispatcher(
        api_tools={"create_pad": mock_create_pad},
        vision_tools={"click_element": mock_click_element}
    )
    
    # 测试 API 操作
    result1 = await dispatcher.execute("create_pad", {"height": 100})
    print(f"API 操作结果: {result1}")
    
    # 测试视觉操作
    result2 = await dispatcher.execute("click_element", {"x": 100, "y": 200})
    print(f"视觉操作结果: {result2}")
    
    # 打印统计
    print(f"执行统计: {dispatcher.get_stats()}")


if __name__ == "__main__":
    asyncio.run(_demo())

