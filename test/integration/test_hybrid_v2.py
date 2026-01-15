"""
CATIA VLA v2.0 混合架构测试套件

测试混合驱动策略：API + 视觉工具的协同工作

Author: CATIA VLA Team
"""

import json
import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Any, Dict

# 确保项目根目录在路径中
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ==================== Fixtures ====================

@pytest.fixture
def mock_api_tools():
    """Mock API 工具"""
    async def mock_create_pad(**kwargs):
        return json.dumps({"success": True, "data": {"pad_name": "Pad_100mm"}})
    
    async def mock_create_rectangle(**kwargs):
        return json.dumps({"success": True, "data": {"sketch_name": "Rect_100x100"}})
    
    async def mock_create_new_part(**kwargs):
        return json.dumps({"success": True, "data": {"part_name": "Part1"}})
    
    return {
        "create_pad": mock_create_pad,
        "create_rectangle_sketch": mock_create_rectangle,
        "create_new_part": mock_create_new_part,
    }


@pytest.fixture
def mock_vision_tools():
    """Mock 视觉工具"""
    async def mock_click_element(**kwargs):
        return json.dumps({"success": True, "message": "点击成功"})
    
    async def mock_capture_screen(**kwargs):
        return json.dumps({"success": True, "file_path": "/tmp/screenshot.png"})
    
    async def mock_detect_ui(**kwargs):
        return json.dumps([
            {"label": "005", "bbox": [100, 100, 150, 150], "confidence": 0.95}
        ])
    
    return {
        "click_element": mock_click_element,
        "capture_screen": mock_capture_screen,
        "detect_ui_elements": mock_detect_ui,
    }


# ==================== Dispatcher Tests ====================

class TestUnifiedDispatcher:
    """Unified Dispatcher 测试"""
    
    def test_import_dispatcher(self):
        """测试模块导入"""
        from applications.catia_vla.agent.dispatcher import (
            UnifiedDispatcher,
            ExecutionModality,
            ExecutionResult
        )
        assert UnifiedDispatcher is not None
        assert ExecutionModality is not None
    
    def test_modality_detection(self):
        """测试模态检测"""
        from applications.catia_vla.agent.dispatcher import (
            UnifiedDispatcher,
            ExecutionModality
        )
        
        dispatcher = UnifiedDispatcher(
            api_tools={},
            vision_tools={}
        )
        
        # API 操作
        assert dispatcher.get_modality("create_pad") == ExecutionModality.API
        assert dispatcher.get_modality("create_sketch") == ExecutionModality.API
        assert dispatcher.get_modality("create_rectangle") == ExecutionModality.API
        
        # 视觉操作
        assert dispatcher.get_modality("click_toolbar") == ExecutionModality.VISION
        assert dispatcher.get_modality("handle_dialog") == ExecutionModality.VISION
        assert dispatcher.get_modality("detect_ui_elements") == ExecutionModality.VISION
        
        # 混合操作
        assert dispatcher.get_modality("open_file") == ExecutionModality.HYBRID
    
    @pytest.mark.asyncio
    async def test_api_execution(self, mock_api_tools):
        """测试 API 执行"""
        from applications.catia_vla.agent.dispatcher import (
            UnifiedDispatcher,
            ExecutionModality
        )
        
        dispatcher = UnifiedDispatcher(
            api_tools=mock_api_tools,
            vision_tools={}
        )
        
        result = await dispatcher.execute(
            "create_pad",
            {"height": 100}
        )
        
        assert result.success is True
        assert result.modality == ExecutionModality.API
        assert result.fallback_used is False
    
    @pytest.mark.asyncio
    async def test_vision_execution(self, mock_vision_tools):
        """测试视觉执行"""
        from applications.catia_vla.agent.dispatcher import (
            UnifiedDispatcher,
            ExecutionModality
        )
        
        dispatcher = UnifiedDispatcher(
            api_tools={},
            vision_tools=mock_vision_tools
        )
        
        result = await dispatcher.execute(
            "click_element",
            {"x": 100, "y": 200},
            force_modality=ExecutionModality.VISION
        )
        
        assert result.success is True
        assert result.modality == ExecutionModality.VISION
    
    @pytest.mark.asyncio
    async def test_fallback_on_failure(self, mock_api_tools, mock_vision_tools):
        """测试失败降级"""
        from applications.catia_vla.agent.dispatcher import (
            UnifiedDispatcher,
            ExecutionModality
        )
        
        # 创建一个会失败的 API 工具
        async def failing_api(**kwargs):
            return json.dumps({"success": False, "message": "API 失败"})
        
        mock_api_tools["open_file"] = failing_api
        mock_vision_tools["open_file"] = mock_vision_tools["click_element"]
        
        dispatcher = UnifiedDispatcher(
            api_tools=mock_api_tools,
            vision_tools=mock_vision_tools,
            enable_fallback=True
        )
        
        result = await dispatcher.execute(
            "open_file",
            {"path": "/test.txt"},
            force_modality=ExecutionModality.HYBRID
        )
        
        # 应该降级到视觉并成功
        assert result.success is True
        assert result.fallback_used is True
    
    def test_stats_tracking(self, mock_api_tools):
        """测试统计跟踪"""
        from applications.catia_vla.agent.dispatcher import UnifiedDispatcher
        
        dispatcher = UnifiedDispatcher(
            api_tools=mock_api_tools,
            vision_tools={}
        )
        
        stats = dispatcher.get_stats()
        assert "api_calls" in stats
        assert "vision_calls" in stats
        assert "fallbacks" in stats


# ==================== RAG Retriever Tests ====================

class TestSOPRetriever:
    """RAG 检索器测试"""
    
    def test_import_retriever(self):
        """测试模块导入"""
        from applications.catia_vla.knowledge.rag_retriever import (
            SOPRetriever,
            RetrievalResult,
            DocumentChunk
        )
        assert SOPRetriever is not None
    
    def test_retriever_initialization(self):
        """测试初始化"""
        from applications.catia_vla.knowledge.rag_retriever import SOPRetriever
        
        retriever = SOPRetriever()
        assert retriever is not None
        
        stats = retriever.get_stats()
        assert "mode" in stats
    
    def test_sample_sop_creation(self):
        """测试示例 SOP 文档创建"""
        from applications.catia_vla.knowledge.rag_retriever import (
            create_sample_sop_docs
        )
        
        # 使用临时目录
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = create_sample_sop_docs(tmpdir + "/sop_docs")
            
            # 验证文件创建
            from pathlib import Path
            assert Path(output_dir).exists()
            assert (Path(output_dir) / "sop_base_with_ribs.md").exists()
    
    def test_document_indexing(self):
        """测试文档索引 (使用内存模式避免 ChromaDB 兼容性问题)"""
        from applications.catia_vla.knowledge.rag_retriever import (
            SOPRetriever,
            create_sample_sop_docs
        )
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建示例文档
            docs_dir = create_sample_sop_docs(tmpdir + "/sop_docs")
            
            # 索引文档 - 使用内存模式
            retriever = SOPRetriever()
            retriever._use_memory_mode()  # 强制使用内存模式
            count = retriever.index_documents(docs_dir)
            
            assert count > 0
    
    def test_search(self):
        """测试检索 (使用内存模式避免 ChromaDB 兼容性问题)"""
        from applications.catia_vla.knowledge.rag_retriever import (
            SOPRetriever,
            create_sample_sop_docs
        )
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 准备
            docs_dir = create_sample_sop_docs(tmpdir + "/sop_docs")
            retriever = SOPRetriever()
            retriever._use_memory_mode()  # 强制使用内存模式
            retriever.index_documents(docs_dir)
            
            # 检索
            results = retriever.search("创建立方体", top_k=2)
            
            assert len(results) > 0
            assert results[0].content is not None
    
    def test_context_formatting(self):
        """测试上下文格式化"""
        from applications.catia_vla.knowledge.rag_retriever import (
            SOPRetriever,
            RetrievalResult
        )
        
        retriever = SOPRetriever()
        
        # 模拟结果
        results = [
            RetrievalResult(
                content="这是一个测试文档内容",
                score=0.85,
                metadata={"title": "测试文档"},
                source="test.md"
            ),
        ]
        
        context = retriever.format_context(results)
        
        assert "相关文档" in context
        assert "0.85" in context


# ==================== Host Planner Tests ====================

class TestHostPlanner:
    """HostPlanner 测试"""
    
    def test_import_planner(self):
        """测试模块导入"""
        from applications.catia_vla.agent.host_planner import (
            HostPlanner,
            TaskPlan,
            TaskStep,
            TaskStatus
        )
        assert HostPlanner is not None
        assert TaskPlan is not None
    
    @pytest.mark.asyncio
    async def test_cube_template_matching(self):
        """测试立方体模板匹配"""
        from applications.catia_vla.agent.host_planner import HostPlanner
        
        planner = HostPlanner()
        
        plan = await planner.create_plan("创建一个 100x100x100 的立方体")
        
        assert plan is not None
        assert len(plan.steps) == 3
        assert plan.metadata.get("template") == "create_cube"
        
        # 验证尺寸参数
        assert plan.steps[1].parameters.get("length") == 100
        assert plan.steps[1].parameters.get("width") == 100
        assert plan.steps[2].parameters.get("height") == 100
    
    @pytest.mark.asyncio
    async def test_box_template_matching(self):
        """测试长方体模板匹配"""
        from applications.catia_vla.agent.host_planner import HostPlanner
        
        planner = HostPlanner()
        
        plan = await planner.create_plan("创建一个 200x100x50 的长方体")
        
        assert plan is not None
        assert len(plan.steps) == 3
        assert plan.metadata.get("template") == "create_box"
        
        # 验证尺寸参数
        assert plan.steps[1].parameters.get("length") == 200
        assert plan.steps[1].parameters.get("width") == 100
        assert plan.steps[2].parameters.get("height") == 50
    
    @pytest.mark.asyncio
    async def test_basic_plan_fallback(self):
        """测试基本计划回退"""
        from applications.catia_vla.agent.host_planner import HostPlanner
        
        planner = HostPlanner()
        
        # 无法匹配模板的任务
        plan = await planner.create_plan("创建一个复杂的齿轮")
        
        assert plan is not None
        assert plan.metadata.get("type") == "basic"
    
    @pytest.mark.asyncio
    async def test_step_execution(self):
        """测试步骤执行"""
        from applications.catia_vla.agent.host_planner import (
            HostPlanner,
            TaskStep,
            StepType,
            TaskStatus
        )
        
        planner = HostPlanner()
        
        step = TaskStep(
            id="test_step",
            name="测试步骤",
            description="测试",
            step_type=StepType.API,
            tool_name="create_new_part",
            parameters={"visible": True}
        )
        
        # Mock 执行器
        async def mock_executor(**kwargs):
            return {"success": True}
        
        success = await planner.execute_step(step, mock_executor)
        
        assert success is True
        assert step.status == TaskStatus.COMPLETED
    
    def test_plan_progress(self):
        """测试计划进度"""
        from applications.catia_vla.agent.host_planner import (
            TaskPlan,
            TaskStep,
            StepType,
            TaskStatus
        )
        
        steps = [
            TaskStep(
                id="s1", name="Step 1", description="",
                step_type=StepType.API, tool_name="t1", parameters={},
                status=TaskStatus.COMPLETED
            ),
            TaskStep(
                id="s2", name="Step 2", description="",
                step_type=StepType.API, tool_name="t2", parameters={},
                status=TaskStatus.COMPLETED
            ),
            TaskStep(
                id="s3", name="Step 3", description="",
                step_type=StepType.API, tool_name="t3", parameters={},
                status=TaskStatus.PENDING
            ),
        ]
        
        plan = TaskPlan(
            id="test", name="Test Plan", description="",
            steps=steps
        )
        
        progress = plan.get_progress()
        
        assert progress["total_steps"] == 3
        assert progress["completed"] == 2
        assert progress["progress_percent"] == pytest.approx(66.67, rel=0.1)


# ==================== Hybrid Agent Tests ====================

class TestHybridAgent:
    """混合智能体测试"""
    
    def test_import_hybrid_agent(self):
        """测试模块导入"""
        from applications.catia_vla.main_hybrid_agent import (
            oxy_space,
            HYBRID_AGENT_PROMPT
        )
        assert oxy_space is not None
        assert HYBRID_AGENT_PROMPT is not None
    
    def test_agent_configuration(self):
        """测试智能体配置"""
        from applications.catia_vla.main_hybrid_agent import oxy_space
        
        assert len(oxy_space) == 4  # LLM, API tools, Vision tools, Agent
        
        names = [item.name for item in oxy_space]
        assert "default_llm" in names
        assert "catia_api_tools" in names
        assert "catia_tools" in names
        assert "catia_hybrid_agent" in names
    
    def test_hybrid_prompt_content(self):
        """测试混合 Prompt 内容"""
        from applications.catia_vla.main_hybrid_agent import HYBRID_AGENT_PROMPT
        
        # 验证 API 工具说明
        assert "create_new_part" in HYBRID_AGENT_PROMPT
        assert "create_rectangle_sketch" in HYBRID_AGENT_PROMPT
        assert "create_pad" in HYBRID_AGENT_PROMPT
        
        # 验证视觉工具说明
        assert "capture_screen" in HYBRID_AGENT_PROMPT
        assert "detect_ui_elements" in HYBRID_AGENT_PROMPT
        assert "click_element" in HYBRID_AGENT_PROMPT
        
        # 验证策略说明
        assert "模态 A" in HYBRID_AGENT_PROMPT or "API" in HYBRID_AGENT_PROMPT
        assert "模态 B" in HYBRID_AGENT_PROMPT or "视觉" in HYBRID_AGENT_PROMPT
    
    @pytest.mark.asyncio
    async def test_hybrid_agent_dry_run(self):
        """测试混合智能体 dry-run"""
        from applications.catia_vla.main_hybrid_agent import main
        
        # Dry-run 不应该抛出异常
        await main(dry_run=True)


# ==================== Integration Tests ====================

class TestHybridFlow:
    """混合流程集成测试"""
    
    @pytest.mark.asyncio
    async def test_api_then_vision_flow(self, mock_api_tools, mock_vision_tools):
        """测试 API 然后视觉的流程"""
        from applications.catia_vla.agent.dispatcher import UnifiedDispatcher
        
        dispatcher = UnifiedDispatcher(
            api_tools=mock_api_tools,
            vision_tools=mock_vision_tools
        )
        
        # 1. API: 创建 Part
        result1 = await dispatcher.execute(
            "create_new_part",
            {"visible": True}
        )
        assert result1.success is True
        
        # 2. API: 创建草图
        result2 = await dispatcher.execute(
            "create_rectangle_sketch",
            {"support_plane": "PlaneXY", "length": 100, "width": 100}
        )
        assert result2.success is True
        
        # 3. 视觉: 截图
        result3 = await dispatcher.execute(
            "capture_screen",
            {}
        )
        assert result3.success is True
        
        # 4. 视觉: 点击
        result4 = await dispatcher.execute(
            "click_element",
            {"x": 100, "y": 200}
        )
        assert result4.success is True
        
        # 验证统计
        stats = dispatcher.get_stats()
        assert stats["api_calls"] >= 2
        assert stats["vision_calls"] >= 2
    
    @pytest.mark.asyncio
    async def test_plan_and_execute_flow(self, mock_api_tools):
        """测试计划和执行流程"""
        from applications.catia_vla.agent.host_planner import HostPlanner, TaskStatus
        from applications.catia_vla.agent.dispatcher import UnifiedDispatcher
        
        # 创建规划器
        planner = HostPlanner()
        
        # 创建调度器
        dispatcher = UnifiedDispatcher(
            api_tools=mock_api_tools,
            vision_tools={}
        )
        
        # 创建计划
        plan = await planner.create_plan("创建一个 100x100x100 的立方体")
        
        # 执行计划
        async def executor(tool_name, parameters, context=None):
            if tool_name in mock_api_tools:
                return await mock_api_tools[tool_name](**parameters)
            return {"success": True}
        
        success = await planner.execute_plan(plan, executor)
        
        assert success is True
        assert plan.status == TaskStatus.COMPLETED


# ==================== Test Runner ====================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])

