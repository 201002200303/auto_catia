"""
HostAgent - 宏观任务规划器

将用户的自然语言任务描述分解为可执行的步骤序列，
结合 RAG 知识检索增强规划能力，调度 LocalAgent 执行。

Author: CATIA VLA Team
"""

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    """步骤类型枚举"""
    API = "api"           # API 调用
    VISION = "vision"     # 视觉操作
    HYBRID = "hybrid"     # 混合（由执行器决定）
    CONDITION = "condition"  # 条件判断
    LOOP = "loop"         # 循环


@dataclass
class TaskStep:
    """任务步骤数据类"""
    id: str
    name: str
    description: str
    step_type: StepType
    tool_name: str
    parameters: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "step_type": self.step_type.value,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "status": self.status.value,
            "depends_on": self.depends_on,
        }


@dataclass
class TaskPlan:
    """任务计划数据类"""
    id: str
    name: str
    description: str
    steps: List[TaskStep]
    status: TaskStatus = TaskStatus.PENDING
    current_step_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_current_step(self) -> Optional[TaskStep]:
        """获取当前步骤"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def advance(self) -> bool:
        """前进到下一步"""
        if self.current_step_index < len(self.steps) - 1:
            self.current_step_index += 1
            return True
        return False
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        completed = sum(1 for s in self.steps if s.status == TaskStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == TaskStatus.FAILED)
        
        return {
            "total_steps": len(self.steps),
            "completed": completed,
            "failed": failed,
            "current_step": self.current_step_index,
            "progress_percent": (completed / len(self.steps) * 100) if self.steps else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "progress": self.get_progress()
        }


class HostPlanner:
    """
    宏观任务规划器
    
    职责：
    1. 解析用户意图
    2. 检索相关 SOP 文档（可选）
    3. 生成任务步骤列表
    4. 管理步骤执行状态
    
    Usage:
        planner = HostPlanner(llm_client=..., rag_retriever=...)
        plan = await planner.create_plan("创建一个带加强筋的底座")
        
        for step in plan.steps:
            result = await planner.execute_step(step, executor)
    """
    
    # 任务模板：常见操作的预定义步骤
    TASK_TEMPLATES = {
        "create_cube": [
            TaskStep(
                id="step_1",
                name="创建文档",
                description="创建新的 CATIA Part 文档",
                step_type=StepType.API,
                tool_name="create_new_part",
                parameters={"visible": True}
            ),
            TaskStep(
                id="step_2",
                name="创建草图",
                description="在 XY 平面创建正方形草图",
                step_type=StepType.API,
                tool_name="create_rectangle_sketch",
                parameters={
                    "support_plane": "PlaneXY",
                    "length": 100,
                    "width": 100,
                    "name": "CubeBase"
                },
                depends_on=["step_1"]
            ),
            TaskStep(
                id="step_3",
                name="创建凸台",
                description="拉伸草图创建立方体",
                step_type=StepType.API,
                tool_name="create_pad",
                parameters={
                    "profile_name": "CubeBase",
                    "height": 100,
                    "name": "Cube"
                },
                depends_on=["step_2"]
            ),
        ],
        "create_box": [
            TaskStep(
                id="step_1",
                name="创建文档",
                description="创建新的 CATIA Part 文档",
                step_type=StepType.API,
                tool_name="create_new_part",
                parameters={"visible": True}
            ),
            TaskStep(
                id="step_2",
                name="创建草图",
                description="在 XY 平面创建矩形草图",
                step_type=StepType.API,
                tool_name="create_rectangle_sketch",
                parameters={
                    "support_plane": "PlaneXY",
                    "length": "${length}",
                    "width": "${width}",
                    "name": "BoxBase"
                },
                depends_on=["step_1"]
            ),
            TaskStep(
                id="step_3",
                name="创建凸台",
                description="拉伸草图创建长方体",
                step_type=StepType.API,
                tool_name="create_pad",
                parameters={
                    "profile_name": "BoxBase",
                    "height": "${height}",
                    "name": "Box"
                },
                depends_on=["step_2"]
            ),
        ],
    }
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        rag_retriever: Optional[Any] = None,
        use_templates: bool = True
    ):
        """
        初始化规划器
        
        Args:
            llm_client: LLM 客户端（可选，用于动态规划）
            rag_retriever: RAG 检索器（可选，用于知识增强）
            use_templates: 是否使用预定义模板
        """
        self.llm_client = llm_client
        self.rag_retriever = rag_retriever
        self.use_templates = use_templates
        
        self._plan_counter = 0
        self._active_plans: Dict[str, TaskPlan] = {}
        
        logger.info("HostPlanner 初始化完成")
    
    async def create_plan(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """
        创建任务计划
        
        Args:
            user_query: 用户查询
            context: 额外上下文（如尺寸参数）
            
        Returns:
            TaskPlan: 任务计划
        """
        self._plan_counter += 1
        plan_id = f"plan_{self._plan_counter}"
        
        logger.info(f"创建计划: {user_query}")
        
        # 1. 尝试匹配模板
        if self.use_templates:
            template_plan = self._match_template(user_query, context)
            if template_plan:
                template_plan.id = plan_id
                self._active_plans[plan_id] = template_plan
                return template_plan
        
        # 2. 使用 RAG 检索相关知识
        sop_context = ""
        if self.rag_retriever:
            try:
                results = self.rag_retriever.search(user_query, top_k=2)
                sop_context = self.rag_retriever.format_context(results)
            except Exception as e:
                logger.warning(f"RAG 检索失败: {e}")
        
        # 3. 使用 LLM 生成计划（如果有 LLM 客户端）
        if self.llm_client:
            plan = await self._generate_plan_with_llm(
                user_query, sop_context, context, plan_id
            )
            if plan:
                self._active_plans[plan_id] = plan
                return plan
        
        # 4. 回退到基本计划
        plan = self._create_basic_plan(user_query, plan_id)
        self._active_plans[plan_id] = plan
        return plan
    
    def _match_template(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[TaskPlan]:
        """匹配预定义模板"""
        query_lower = query.lower()
        context = context or {}
        
        # 匹配立方体
        if "立方体" in query_lower or "cube" in query_lower:
            # 提取尺寸
            import re
            size_match = re.search(r'(\d+)\s*[xX×]\s*(\d+)\s*[xX×]\s*(\d+)', query)
            if size_match:
                size = int(size_match.group(1))
            else:
                size_match = re.search(r'(\d+)\s*(mm|毫米)?.*立方体', query)
                size = int(size_match.group(1)) if size_match else 100
            
            # 复制模板并替换参数
            steps = []
            for template_step in self.TASK_TEMPLATES["create_cube"]:
                step = TaskStep(
                    id=template_step.id,
                    name=template_step.name,
                    description=template_step.description,
                    step_type=template_step.step_type,
                    tool_name=template_step.tool_name,
                    parameters=template_step.parameters.copy(),
                    depends_on=template_step.depends_on.copy()
                )
                
                # 替换尺寸
                if "length" in step.parameters:
                    step.parameters["length"] = size
                if "width" in step.parameters:
                    step.parameters["width"] = size
                if "height" in step.parameters:
                    step.parameters["height"] = size
                
                steps.append(step)
            
            return TaskPlan(
                id="",
                name=f"创建 {size}mm 立方体",
                description=f"使用模板创建 {size}x{size}x{size}mm 立方体",
                steps=steps,
                metadata={"template": "create_cube", "size": size}
            )
        
        # 匹配长方体
        if "长方体" in query_lower or "box" in query_lower:
            import re
            size_match = re.search(r'(\d+)\s*[xX×]\s*(\d+)\s*[xX×]\s*(\d+)', query)
            
            if size_match:
                length = int(size_match.group(1))
                width = int(size_match.group(2))
                height = int(size_match.group(3))
            else:
                length = context.get("length", 200)
                width = context.get("width", 100)
                height = context.get("height", 50)
            
            steps = []
            for template_step in self.TASK_TEMPLATES["create_box"]:
                step = TaskStep(
                    id=template_step.id,
                    name=template_step.name,
                    description=template_step.description,
                    step_type=template_step.step_type,
                    tool_name=template_step.tool_name,
                    parameters=template_step.parameters.copy(),
                    depends_on=template_step.depends_on.copy()
                )
                
                # 替换参数
                for key, value in step.parameters.items():
                    if value == "${length}":
                        step.parameters[key] = length
                    elif value == "${width}":
                        step.parameters[key] = width
                    elif value == "${height}":
                        step.parameters[key] = height
                
                steps.append(step)
            
            return TaskPlan(
                id="",
                name=f"创建 {length}x{width}x{height}mm 长方体",
                description=f"使用模板创建长方体",
                steps=steps,
                metadata={"template": "create_box", "dimensions": [length, width, height]}
            )
        
        return None
    
    async def _generate_plan_with_llm(
        self,
        query: str,
        sop_context: str,
        context: Optional[Dict[str, Any]],
        plan_id: str
    ) -> Optional[TaskPlan]:
        """使用 LLM 生成计划"""
        # TODO: 实现 LLM 规划逻辑
        # 这需要定义 LLM 提示词和解析响应
        logger.info("LLM 规划功能待实现")
        return None
    
    def _create_basic_plan(self, query: str, plan_id: str) -> TaskPlan:
        """创建基本计划（回退方案）"""
        # 基本的三步计划
        steps = [
            TaskStep(
                id="step_1",
                name="创建文档",
                description="创建新的 CATIA Part 文档",
                step_type=StepType.API,
                tool_name="create_new_part",
                parameters={"visible": True}
            ),
            TaskStep(
                id="step_2",
                name="执行任务",
                description=query,
                step_type=StepType.HYBRID,
                tool_name="",  # 由执行器决定
                parameters={"query": query},
                depends_on=["step_1"]
            ),
        ]
        
        return TaskPlan(
            id=plan_id,
            name="基本任务计划",
            description=query,
            steps=steps,
            metadata={"type": "basic"}
        )
    
    async def execute_step(
        self,
        step: TaskStep,
        executor: Callable,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        执行单个步骤
        
        Args:
            step: 任务步骤
            executor: 执行器函数
            context: 执行上下文
            
        Returns:
            是否成功
        """
        step.status = TaskStatus.IN_PROGRESS
        logger.info(f"执行步骤: {step.name}")
        
        try:
            # 调用执行器
            if asyncio.iscoroutinefunction(executor):
                result = await executor(
                    tool_name=step.tool_name,
                    parameters=step.parameters,
                    context=context
                )
            else:
                result = executor(
                    tool_name=step.tool_name,
                    parameters=step.parameters,
                    context=context
                )
            
            # 检查结果
            success = True
            if isinstance(result, dict):
                success = result.get("success", True)
            elif isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    success = parsed.get("success", True)
                except:
                    pass
            
            if success:
                step.status = TaskStatus.COMPLETED
                step.result = result
                logger.info(f"步骤完成: {step.name}")
                return True
            else:
                raise Exception(f"执行失败: {result}")
                
        except Exception as e:
            step.retry_count += 1
            
            if step.retry_count <= step.max_retries:
                logger.warning(f"步骤失败，重试 ({step.retry_count}/{step.max_retries}): {e}")
                return await self.execute_step(step, executor, context)
            
            step.status = TaskStatus.FAILED
            step.error = str(e)
            logger.error(f"步骤失败: {step.name} - {e}")
            return False
    
    async def execute_plan(
        self,
        plan: TaskPlan,
        executor: Callable,
        stop_on_failure: bool = True
    ) -> bool:
        """
        执行整个计划
        
        Args:
            plan: 任务计划
            executor: 执行器函数
            stop_on_failure: 失败时是否停止
            
        Returns:
            是否全部成功
        """
        plan.status = TaskStatus.IN_PROGRESS
        logger.info(f"开始执行计划: {plan.name}")
        
        all_success = True
        
        for step in plan.steps:
            # 检查依赖
            dependencies_met = all(
                self._get_step_by_id(plan, dep_id).status == TaskStatus.COMPLETED
                for dep_id in step.depends_on
            )
            
            if not dependencies_met:
                step.status = TaskStatus.SKIPPED
                logger.warning(f"跳过步骤（依赖未满足）: {step.name}")
                all_success = False
                continue
            
            # 执行步骤
            success = await self.execute_step(step, executor)
            
            if not success:
                all_success = False
                if stop_on_failure:
                    plan.status = TaskStatus.FAILED
                    logger.error(f"计划执行失败: {plan.name}")
                    return False
        
        plan.status = TaskStatus.COMPLETED if all_success else TaskStatus.FAILED
        logger.info(f"计划执行完成: {plan.name}, 成功: {all_success}")
        return all_success
    
    def _get_step_by_id(self, plan: TaskPlan, step_id: str) -> Optional[TaskStep]:
        """根据 ID 获取步骤"""
        for step in plan.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_plan(self, plan_id: str) -> Optional[TaskPlan]:
        """获取计划"""
        return self._active_plans.get(plan_id)
    
    def list_plans(self) -> List[Dict[str, Any]]:
        """列出所有计划"""
        return [
            {
                "id": plan.id,
                "name": plan.name,
                "status": plan.status.value,
                "progress": plan.get_progress()
            }
            for plan in self._active_plans.values()
        ]


# ==================== 使用示例 ====================

async def _demo():
    """演示用法"""
    planner = HostPlanner()
    
    # 创建立方体计划
    plan1 = await planner.create_plan("创建一个 150x150x150 的立方体")
    print(f"\n计划 1: {plan1.name}")
    print(f"步骤数: {len(plan1.steps)}")
    for step in plan1.steps:
        print(f"  - {step.name}: {step.tool_name}({step.parameters})")
    
    # 创建长方体计划
    plan2 = await planner.create_plan("创建一个 200x100x50 的长方体")
    print(f"\n计划 2: {plan2.name}")
    print(f"步骤数: {len(plan2.steps)}")
    for step in plan2.steps:
        print(f"  - {step.name}: {step.tool_name}({step.parameters})")
    
    # 无法匹配模板的任务
    plan3 = await planner.create_plan("创建一个齿轮")
    print(f"\n计划 3: {plan3.name}")
    print(f"步骤数: {len(plan3.steps)}")
    for step in plan3.steps:
        print(f"  - {step.name}: {step.tool_name}")


if __name__ == "__main__":
    asyncio.run(_demo())
