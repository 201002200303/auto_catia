"""
CATIA VLA v1.0 集成测试套件

测试 API 核心闭环：LLM -> FunctionHub -> pycatia -> CATIA

Author: CATIA VLA Team
"""

import json
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from typing import Any

# 确保项目根目录在路径中
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ==================== Fixtures ====================

@pytest.fixture
def mock_catia():
    """Mock CATIA 连接"""
    fake_pycatia = MagicMock()

    # 创建 Mock CATIA 对象
    mock_caa = MagicMock()
    mock_caa.visible = True
        
    fake_pycatia.catia = MagicMock(return_value=mock_caa)

    with patch.dict(sys.modules, {"pycatia": fake_pycatia}):
        # Mock documents
        mock_documents = MagicMock()
        mock_doc = MagicMock()
        mock_part = MagicMock()
        mock_part.name = "TestPart"
        mock_doc.part = mock_part
        mock_documents.add.return_value = mock_doc
        mock_caa.documents = mock_documents
        mock_caa.active_document = mock_doc
        
        # Mock origin elements
        mock_origin = MagicMock()
        mock_origin.plane_xy = MagicMock()
        mock_origin.plane_yz = MagicMock()
        mock_origin.plane_zx = MagicMock()
        mock_part.origin_elements = mock_origin
        
        # Mock hybrid_bodies
        mock_hybrid_bodies = MagicMock()
        mock_hybrid_bodies.count = 1
        mock_hybrid_body = MagicMock()
        mock_hybrid_body.name = "Geometry"
        mock_hybrid_bodies.add.return_value = mock_hybrid_body
        mock_hybrid_bodies.__iter__ = Mock(return_value=iter([mock_hybrid_body]))
        mock_part.hybrid_bodies = mock_hybrid_bodies
        
        # Mock bodies
        mock_bodies = MagicMock()
        mock_bodies.count = 1
        mock_main_body = MagicMock()
        mock_main_body.name = "PartBody"
        mock_part.main_body = mock_main_body
        mock_part.bodies = mock_bodies
        
        # Mock factories
        mock_hsf = MagicMock()
        mock_part.hybrid_shape_factory = mock_hsf
        mock_sf = MagicMock()
        mock_part.shape_factory = mock_sf
        
        # Mock sketch
        mock_hybrid_sketches = MagicMock()
        mock_sketch = MagicMock()
        mock_sketch.name = "Rect_100x100"
        mock_factory2d = MagicMock()
        mock_sketch.open_edition.return_value = mock_factory2d
        mock_hybrid_sketches.item.return_value = mock_sketch
        mock_hybrid_sketches.add.return_value = mock_sketch
        mock_hybrid_body.hybrid_sketches = mock_hybrid_sketches
        
        # Mock shapes
        mock_hybrid_shapes = MagicMock()
        mock_hybrid_shapes.count = 0
        mock_hybrid_body.hybrid_shapes = mock_hybrid_shapes
        
        # Mock pad
        mock_pad = MagicMock()
        mock_pad.name = "Pad_100mm"
        mock_sf.add_new_pad.return_value = mock_pad

        # Mock pocket
        mock_pocket = MagicMock()
        mock_pocket.name = "Pocket_10mm"
        mock_sf.add_new_pocket.return_value = mock_pocket

        # Mock Factory2D COM methods for circle/spline/polyline
        mock_factory2d_com = MagicMock()
        mock_factory2d.com_object = mock_factory2d_com

        mock_circle = MagicMock()
        mock_factory2d_com.CreateCircle.return_value = mock_circle
        mock_factory2d_com.CreateClosedCircle.return_value = mock_circle

        def _make_cp(*args, **kwargs):
            return MagicMock()

        mock_factory2d_com.CreateControlPoint.side_effect = _make_cp
        mock_spline = MagicMock()
        mock_factory2d_com.CreateSpline.return_value = mock_spline

        def _make_point(*args, **kwargs):
            return MagicMock()

        mock_factory2d_com.CreatePoint.side_effect = _make_point
        mock_line = MagicMock()
        mock_factory2d_com.CreateLine.return_value = mock_line

        yield mock_caa


@pytest.fixture
def reset_catia_manager():
    """重置 CATIA 管理器状态"""
    # 在测试前重置单例状态
    from function_hubs.catia_api_tools import _manager
    _manager._catia = None
    _manager._part = None
    _manager._doc = None
    yield
    # 测试后再次重置
    _manager._catia = None
    _manager._part = None
    _manager._doc = None


# ==================== Unit Tests ====================

class TestCatiaApiTools:
    """CATIA API 工具单元测试"""
    
    def test_import_catia_api_tools(self):
        """测试模块导入"""
        from function_hubs.catia_api_tools import catia_api_tools
        assert catia_api_tools is not None
        assert catia_api_tools.name == "catia_api_tools"
    
    def test_tools_registered(self):
        """测试工具注册"""
        from function_hubs.catia_api_tools import catia_api_tools
        
        expected_tools = [
            "create_new_part",
            "create_rectangle_sketch",
            "create_pad",
            "create_pocket",
            "create_extrude",
            "create_fillet",
            "create_empty_sketch",
            "add_circle_to_sketch",
            "add_polyline_to_sketch",
            "add_spline_to_sketch",
            "get_part_info",
            "save_part",
        ]
        
        registered_tools = list(catia_api_tools.func_dict.keys())
        
        for tool in expected_tools:
            assert tool in registered_tools, f"工具 {tool} 未注册"
    
    def test_result_json_format(self):
        """测试 JSON 返回格式"""
        from function_hubs.catia_api_tools import _result_json
        
        # 成功情况
        result = _result_json(True, "测试成功", {"key": "value"})
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["message"] == "测试成功"
        assert parsed["data"]["key"] == "value"
        
        # 失败情况
        result = _result_json(False, "测试失败")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "data" not in parsed


class TestCatiaApiToolsWithMock:
    """使用 Mock 的 CATIA API 工具测试"""
    
    @pytest.mark.catia_mock
    def test_create_new_part(self, mock_catia, reset_catia_manager):
        """测试创建新 Part"""
        from function_hubs.catia_api_tools import create_new_part
        
        # 由于是异步函数，需要同步调用底层逻辑
        # 这里直接测试同步逻辑
        from function_hubs.catia_api_tools import _manager, _result_json
        
        # 注入 mock
        _manager._catia = mock_catia
        
        # 执行
        result = create_new_part.__wrapped__(visible=True)  # 获取原始函数
        parsed = json.loads(result)
        
        assert parsed["success"] is True
        assert "TestPart" in parsed["data"]["part_name"]
    
    @pytest.mark.catia_mock
    def test_create_rectangle_sketch(self, mock_catia, reset_catia_manager):
        """测试创建矩形草图"""
        from function_hubs.catia_api_tools import create_rectangle_sketch, _manager
        
        # 注入 mock
        _manager._catia = mock_catia
        _manager._part = mock_catia.documents.add("Part").part
        
        # 执行
        result = create_rectangle_sketch.__wrapped__(
            support_plane="PlaneXY",
            length=100.0,
            width=100.0,
            body_name="Geometry",
            name="TestRect"
        )
        parsed = json.loads(result)
        
        # 验证
        assert parsed["success"] is True
        assert parsed["data"]["length"] == 100.0
        assert parsed["data"]["width"] == 100.0

    @pytest.mark.catia_mock
    def test_add_circle_to_sketch(self, mock_catia, reset_catia_manager):
        from function_hubs.catia_api_tools import add_circle_to_sketch, _manager

        _manager._catia = mock_catia
        _manager._part = mock_catia.documents.add("Part").part

        result = add_circle_to_sketch.__wrapped__(
            sketch_name="AnySketch",
            center_x=0.0,
            center_y=0.0,
            radius=10.0,
            start_angle=0.0,
            end_angle=6.283185307179586,
            name=None
        )
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["radius"] == 10.0

    @pytest.mark.catia_mock
    def test_add_polyline_to_sketch_closed(self, mock_catia, reset_catia_manager):
        from function_hubs.catia_api_tools import add_polyline_to_sketch, _manager

        _manager._catia = mock_catia
        _manager._part = mock_catia.documents.add("Part").part

        result = add_polyline_to_sketch.__wrapped__(
            sketch_name="AnySketch",
            points=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
            close=True,
            name_prefix=None
        )
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["closed"] is True
        assert parsed["data"]["segments_count"] == 3

    @pytest.mark.catia_mock
    def test_add_spline_to_sketch(self, mock_catia, reset_catia_manager):
        from function_hubs.catia_api_tools import add_spline_to_sketch, _manager

        _manager._catia = mock_catia
        _manager._part = mock_catia.documents.add("Part").part

        result = add_spline_to_sketch.__wrapped__(
            sketch_name="AnySketch",
            control_points=[[0.0, 0.0], [10.0, 5.0], [20.0, 0.0]],
            close=False,
            name=None
        )
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["control_points_count"] == 3


class TestMCPServer:
    """MCP Server 测试"""
    
    def test_import_mcp_server(self):
        """测试 MCP Server 模块导入"""
        from mcp_servers.catia_mcp_server import mcp
        assert mcp is not None
    
    def test_mcp_tools_registered(self):
        """测试 MCP 工具注册"""
        from mcp_servers.catia_mcp_server import mcp
        
        # 获取注册的工具列表
        # FastMCP 的工具存储方式可能不同，这里做基本验证
        assert hasattr(mcp, 'tool')


# ==================== Integration Tests ====================

class TestCatiaIntegration:
    """CATIA 集成测试（需要 CATIA 运行）"""
    
    @pytest.mark.catia_required
    def test_full_cube_creation_workflow(self):
        """完整的立方体创建流程测试"""
        from function_hubs.catia_api_tools import (
            create_new_part,
            create_rectangle_sketch,
            create_pad,
            get_part_info
        )
        
        # 注意：直接调用 __wrapped__ 时，需要显式传递所有参数（包括默认值）
        # 因为 Field(...) 默认值不会被自动解析
        
        # 1. 创建新 Part
        result1 = create_new_part.__wrapped__(visible=True)
        parsed1 = json.loads(result1)
        assert parsed1["success"] is True, f"创建 Part 失败: {parsed1['message']}"
        
        # 2. 创建矩形草图（显式传递所有参数）
        result2 = create_rectangle_sketch.__wrapped__(
            support_plane="PlaneXY",
            length=100.0,
            width=100.0,
            body_name="Geometry",  # 显式传递默认参数
            name="CubeBase"
        )
        parsed2 = json.loads(result2)
        assert parsed2["success"] is True, f"创建草图失败: {parsed2['message']}"
        
        # 3. 创建凸台（显式传递所有参数）
        result3 = create_pad.__wrapped__(
            profile_name="CubeBase",
            height=100.0,
            name="CubePad"
        )
        parsed3 = json.loads(result3)
        assert parsed3["success"] is True, f"创建凸台失败: {parsed3['message']}"
        
        # 4. 获取 Part 信息
        result4 = get_part_info.__wrapped__()
        parsed4 = json.loads(result4)
        assert parsed4["success"] is True


# ==================== Agent E2E Tests ====================

class TestAgentE2E:
    """智能体端到端测试"""
    
    def test_agent_configuration(self):
        """测试智能体配置"""
        from applications.catia_vla.main_api_agent import oxy_space
        
        assert len(oxy_space) == 3  # LLM, FunctionHub, Agent
        
        # 验证各组件
        names = [item.name for item in oxy_space]
        assert "default_llm" in names
        assert "catia_api_tools" in names
        assert "catia_agent" in names
    
    def test_agent_prompt(self):
        """测试智能体 Prompt"""
        from applications.catia_vla.main_api_agent import CATIA_AGENT_PROMPT
        
        # 验证 Prompt 包含关键信息
        assert "create_new_part" in CATIA_AGENT_PROMPT
        assert "create_rectangle_sketch" in CATIA_AGENT_PROMPT
        assert "create_pad" in CATIA_AGENT_PROMPT
        assert "create_pocket" in CATIA_AGENT_PROMPT
        assert "create_empty_sketch" in CATIA_AGENT_PROMPT
        assert "add_circle_to_sketch" in CATIA_AGENT_PROMPT
        assert "add_polyline_to_sketch" in CATIA_AGENT_PROMPT
        assert "add_spline_to_sketch" in CATIA_AGENT_PROMPT
        assert "PlaneXY" in CATIA_AGENT_PROMPT
        assert "毫米" in CATIA_AGENT_PROMPT or "mm" in CATIA_AGENT_PROMPT
    
    @pytest.mark.asyncio
    async def test_agent_dry_run(self):
        """测试智能体 dry-run 模式"""
        from applications.catia_vla.main_api_agent import main
        
        # Dry-run 不应该抛出异常
        await main(dry_run=True)

    def test_tool_code_parser_accepts_python_block(self):
        from applications.catia_vla.run_chat import parse_llm_response_with_tool_code
        from oxygent.schemas import LLMState

        resp = """```python
add_polyline_to_sketch(sketch_name="Sketch.3", points=[(-8, 0), (8, 0)], close=False)
```"""
        parsed = parse_llm_response_with_tool_code(resp)
        assert parsed.state == LLMState.TOOL_CALL
        assert parsed.output["tool_name"] == "add_polyline_to_sketch"
        assert parsed.output["arguments"]["sketch_name"] == "Sketch.3"
        assert parsed.output["arguments"]["points"] == [(-8, 0), (8, 0)]
        assert parsed.output["arguments"]["close"] is False


# ==================== Performance Tests ====================

class TestPerformance:
    """性能测试"""
    
    def test_json_serialization_performance(self):
        """测试 JSON 序列化性能"""
        import time
        from function_hubs.catia_api_tools import _result_json
        
        iterations = 1000
        start = time.time()
        
        for i in range(iterations):
            _result_json(True, f"Test message {i}", {"index": i, "data": "test"})
        
        elapsed = time.time() - start
        avg_time = elapsed / iterations * 1000  # ms
        
        # 平均序列化时间应小于 1ms
        assert avg_time < 1.0, f"JSON 序列化太慢: {avg_time:.3f}ms/次"


# ==================== Test Runner ====================

if __name__ == "__main__":
    # 运行测试
    pytest.main([
        __file__,
        "-v",
        "-m", "not catia_required",  # 默认跳过需要 CATIA 的测试
        "--tb=short"
    ])
