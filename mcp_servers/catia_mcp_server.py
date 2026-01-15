"""
CATIA MCP Server - Model Context Protocol Server for CATIA Operations

封装 pycatia 几何建模类为 MCP Server，供 LLM 智能体调用。
使用单例模式管理 CATIA 连接，支持延迟连接。

Author: CATIA VLA Team
"""

import json
import logging
from typing import Optional
from functools import lru_cache

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 MCP Server 实例
mcp = FastMCP()


# ==================== CATIA 连接管理 ====================

class CATIAConnection:
    """
    CATIA 连接管理器（单例模式）
    
    特性：
    - 延迟连接：首次调用时才建立连接
    - 单例模式：避免重复连接
    - 友好错误：连接失败时返回清晰的错误信息
    """
    
    _instance = None
    _catia = None
    _part = None
    _doc = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def catia(self):
        """获取 CATIA 应用程序对象"""
        if self._catia is None:
            self._connect()
        return self._catia
    
    @property
    def part(self):
        """获取当前活动的 Part 对象"""
        return self._part
    
    @part.setter
    def part(self, value):
        self._part = value
    
    @property
    def doc(self):
        """获取当前文档对象"""
        return self._doc
    
    @doc.setter
    def doc(self, value):
        self._doc = value
    
    def _connect(self):
        """建立 CATIA 连接"""
        try:
            from pycatia import catia
            self._catia = catia()
            logger.info("CATIA 连接成功")
        except Exception as e:
            logger.error(f"CATIA 连接失败: {e}")
            raise ConnectionError(
                f"无法连接到 CATIA。请确保：\n"
                f"1. CATIA 已启动并运行\n"
                f"2. 没有其他程序占用 CATIA COM 接口\n"
                f"原始错误: {e}"
            )
    
    def ensure_connection(self) -> bool:
        """确保连接可用，返回连接状态"""
        try:
            _ = self.catia
            return True
        except ConnectionError:
            return False
    
    def get_active_part(self):
        """获取当前活动的 Part"""
        if self._part is not None:
            return self._part
        
        try:
            doc = self.catia.active_document
            if doc is None:
                raise ValueError("没有打开的文档")
            self._doc = doc
            self._part = doc.part
            return self._part
        except Exception as e:
            raise ValueError(f"无法获取当前 Part: {e}")


# 全局连接实例
_connection = CATIAConnection()


def _result_json(success: bool, message: str, data: Optional[dict] = None) -> str:
    """统一的 JSON 返回格式"""
    result = {
        "success": success,
        "message": message
    }
    if data:
        result["data"] = data
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== MCP Tools ====================

@mcp.tool(description="Create a new CATIA Part document. This should be called first before any modeling operations.")
def create_new_part(
    visible: bool = Field(default=True, description="Whether to show CATIA window (default: True)")
) -> str:
    """
    创建新的 Part 文档
    
    Returns:
        JSON 字符串，包含 success, message, data (part_name)
    """
    try:
        conn = _connection
        caa = conn.catia
        
        # 设置可见性
        caa.visible = visible
        
        # 创建新文档
        documents = caa.documents
        doc = documents.add("Part")
        
        # 保存引用
        conn.doc = doc
        conn.part = doc.part
        
        part_name = conn.part.name
        
        logger.info(f"创建新 Part: {part_name}")
        return _result_json(
            success=True,
            message=f"成功创建新 Part 文档: {part_name}",
            data={"part_name": part_name}
        )
        
    except ConnectionError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建 Part 失败: {e}")
        return _result_json(success=False, message=f"创建 Part 失败: {e}")


@mcp.tool(description="Create a rectangle sketch on a specified plane. The rectangle is centered at the origin.")
def create_rectangle(
    support_plane: str = Field(
        description="Support plane name: 'PlaneXY', 'PlaneYZ', or 'PlaneZX'"
    ),
    length: float = Field(description="Rectangle length in mm (X direction)"),
    width: float = Field(description="Rectangle width in mm (Y direction)"),
    body_name: str = Field(
        default="Geometry",
        description="Target HybridBody name (default: 'Geometry')"
    ),
    name: str = Field(
        default=None,
        description="Custom sketch name (auto-generated if not provided)"
    )
) -> str:
    """
    创建矩形草图
    
    在指定平面上创建一个以原点为中心的矩形草图。
    矩形由四条线段组成，可用于后续的凸台或拉伸操作。
    
    Returns:
        JSON 字符串，包含 success, message, data (sketch_name)
    """
    try:
        conn = _connection
        part = conn.get_active_part()
        
        # 获取支撑平面
        origin = part.origin_elements
        plane_map = {
            "planexy": origin.plane_xy,
            "planeyz": origin.plane_yz,
            "planezx": origin.plane_zx,
        }
        
        support = plane_map.get(support_plane.lower())
        if support is None:
            # 尝试从几何集中查找
            for hb in part.hybrid_bodies:
                try:
                    support = hb.hybrid_shapes.item(support_plane)
                    break
                except Exception:
                    continue
            
            if support is None:
                return _result_json(
                    success=False,
                    message=f"未找到平面: {support_plane}。支持: PlaneXY, PlaneYZ, PlaneZX"
                )
        
        # 获取或创建几何集
        hsf = part.hybrid_shape_factory
        target_body = None
        
        for hb in part.hybrid_bodies:
            if hb.name.lower() == body_name.lower():
                target_body = hb
                break
        
        if target_body is None:
            target_body = part.hybrid_bodies.add()
            target_body.name = body_name
        
        # 创建草图
        ref_support = part.create_reference_from_object(support)
        sketch = target_body.hybrid_sketches.add(ref_support)
        
        # 生成名称
        if name is None:
            name = f"Rect_{int(length)}x{int(width)}"
        sketch.name = name
        
        # 绘制矩形
        factory2d = sketch.open_edition()
        
        half_l = length / 2.0
        half_w = width / 2.0
        
        # 四个顶点坐标
        x1, y1 = -half_l, -half_w
        x2, y2 = half_l, -half_w
        x3, y3 = half_l, half_w
        x4, y4 = -half_l, half_w
        
        # 创建四个点
        p1 = factory2d.create_point(x1, y1)
        p2 = factory2d.create_point(x2, y2)
        p3 = factory2d.create_point(x3, y3)
        p4 = factory2d.create_point(x4, y4)
        
        # 创建四条线
        l1 = factory2d.create_line(x1, y1, x2, y2)
        l2 = factory2d.create_line(x2, y2, x3, y3)
        l3 = factory2d.create_line(x3, y3, x4, y4)
        l4 = factory2d.create_line(x4, y4, x1, y1)
        
        # 设置连接
        l1.start_point = p1
        l1.end_point = p2
        l2.start_point = p2
        l2.end_point = p3
        l3.start_point = p3
        l3.end_point = p4
        l4.start_point = p4
        l4.end_point = p1
        
        sketch.close_edition()
        part.update_object(sketch)
        part.update()
        
        logger.info(f"创建矩形草图: {name} ({length}x{width}mm)")
        return _result_json(
            success=True,
            message=f"成功创建矩形草图: {name}",
            data={
                "sketch_name": name,
                "length": length,
                "width": width,
                "plane": support_plane
            }
        )
        
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建矩形草图失败: {e}")
        return _result_json(success=False, message=f"创建矩形草图失败: {e}")


@mcp.tool(description="Create a pad (solid extrusion) from a sketch profile. This creates a 3D solid feature.")
def create_pad(
    profile_name: str = Field(description="Name of the sketch profile to extrude"),
    height: float = Field(description="Pad height in mm"),
    name: str = Field(
        default=None,
        description="Custom pad name (auto-generated if not provided)"
    )
) -> str:
    """
    从草图创建凸台（实体拉伸）
    
    使用指定的草图轮廓创建实体凸台特征。
    草图必须是封闭轮廓。
    
    Returns:
        JSON 字符串，包含 success, message, data (pad_name)
    """
    try:
        conn = _connection
        part = conn.get_active_part()
        
        # 查找草图
        sketch = None
        for hb in part.hybrid_bodies:
            try:
                sketch = hb.hybrid_sketches.item(profile_name)
                break
            except Exception:
                continue
        
        # 也尝试在 Bodies 中查找
        if sketch is None:
            for body in part.bodies:
                try:
                    sketch = body.sketches.item(profile_name)
                    break
                except Exception:
                    continue
        
        if sketch is None:
            return _result_json(
                success=False,
                message=f"未找到草图: {profile_name}"
            )
        
        # 确保在主体中工作
        part.in_work_object = part.main_body
        
        # 创建凸台
        sf = part.shape_factory
        pad = sf.add_new_pad(sketch, height)
        
        # 命名
        if name is None:
            name = f"Pad_{int(height)}mm"
        pad.name = name
        
        part.update_object(pad)
        part.update()
        
        logger.info(f"创建凸台: {name} (高度: {height}mm)")
        return _result_json(
            success=True,
            message=f"成功创建凸台: {name}",
            data={
                "pad_name": name,
                "height": height,
                "profile": profile_name
            }
        )
        
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建凸台失败: {e}")
        return _result_json(success=False, message=f"创建凸台失败: {e}")


@mcp.tool(description="Create a surface extrusion from a profile curve along a direction.")
def create_extrude(
    profile_name: str = Field(description="Name of the profile curve or sketch to extrude"),
    direction: str = Field(
        description="Extrusion direction: 'PlaneXY', 'PlaneYZ', 'PlaneZX', 'XAxis', 'YAxis', or 'ZAxis'"
    ),
    length1: float = Field(description="Extrusion length in first direction (mm)"),
    length2: float = Field(
        default=0.0,
        description="Extrusion length in second direction (mm, default: 0)"
    ),
    body_name: str = Field(
        default="Geometry",
        description="Target HybridBody name (default: 'Geometry')"
    ),
    name: str = Field(
        default=None,
        description="Custom feature name (auto-generated if not provided)"
    )
) -> str:
    """
    创建曲面拉伸
    
    将轮廓曲线沿指定方向拉伸成曲面。
    支持双向拉伸。
    
    Returns:
        JSON 字符串，包含 success, message, data (extrude_name)
    """
    try:
        conn = _connection
        part = conn.get_active_part()
        hsf = part.hybrid_shape_factory
        
        # 查找轮廓
        profile = None
        for hb in part.hybrid_bodies:
            try:
                profile = hb.hybrid_shapes.item(profile_name)
                break
            except Exception:
                pass
            try:
                profile = hb.hybrid_sketches.item(profile_name)
                break
            except Exception:
                continue
        
        if profile is None:
            return _result_json(
                success=False,
                message=f"未找到轮廓: {profile_name}"
            )
        
        # 解析方向
        direction_lower = direction.lower()
        origin = part.origin_elements
        
        direction_map = {
            "planexy": origin.plane_xy,
            "planeyz": origin.plane_yz,
            "planezx": origin.plane_zx,
        }
        
        dir_obj = direction_map.get(direction_lower)
        
        if dir_obj is None:
            # 尝试坐标轴方向
            axis_map = {
                "xaxis": (1, 0, 0),
                "yaxis": (0, 1, 0),
                "zaxis": (0, 0, 1),
            }
            coords = axis_map.get(direction_lower)
            if coords:
                dir_obj = hsf.add_new_direction_by_coord(*coords)
            else:
                return _result_json(
                    success=False,
                    message=f"无效的方向: {direction}。支持: PlaneXY, PlaneYZ, PlaneZX, XAxis, YAxis, ZAxis"
                )
        
        # 获取或创建几何集
        target_body = None
        for hb in part.hybrid_bodies:
            if hb.name.lower() == body_name.lower():
                target_body = hb
                break
        
        if target_body is None:
            target_body = part.hybrid_bodies.add()
            target_body.name = body_name
        
        # 创建拉伸
        ref_profile = part.create_reference_from_object(profile)
        ref_dir = part.create_reference_from_object(dir_obj)
        
        dir_feature = hsf.add_new_direction(ref_dir)
        extrude = hsf.add_new_extrude(ref_profile, length1, length2, dir_feature)
        
        # 命名
        if name is None:
            name = f"Extrude_{int(length1)}mm"
        extrude.name = name
        
        target_body.append_hybrid_shape(extrude)
        part.in_work_object = extrude
        part.update()
        
        logger.info(f"创建拉伸: {name} (长度: {length1}/{length2}mm)")
        return _result_json(
            success=True,
            message=f"成功创建拉伸曲面: {name}",
            data={
                "extrude_name": name,
                "length1": length1,
                "length2": length2,
                "direction": direction
            }
        )
        
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建拉伸失败: {e}")
        return _result_json(success=False, message=f"创建拉伸失败: {e}")


@mcp.tool(description="Create a fillet (rounded edge) between two surfaces.")
def create_fillet(
    first_surface: str = Field(description="Name of the first surface"),
    second_surface: str = Field(description="Name of the second surface"),
    radius: float = Field(description="Fillet radius in mm"),
    body_name: str = Field(
        default="Geometry",
        description="Target HybridBody name (default: 'Geometry')"
    ),
    name: str = Field(
        default=None,
        description="Custom feature name (auto-generated if not provided)"
    )
) -> str:
    """
    创建双切圆角
    
    在两个曲面之间创建圆角过渡。
    
    Returns:
        JSON 字符串，包含 success, message, data (fillet_name)
    """
    try:
        conn = _connection
        part = conn.get_active_part()
        hsf = part.hybrid_shape_factory
        
        # 查找两个曲面
        def find_shape(name):
            for hb in part.hybrid_bodies:
                try:
                    return hb.hybrid_shapes.item(name)
                except Exception:
                    continue
            return None
        
        first = find_shape(first_surface)
        second = find_shape(second_surface)
        
        if first is None:
            return _result_json(
                success=False,
                message=f"未找到第一个曲面: {first_surface}"
            )
        
        if second is None:
            return _result_json(
                success=False,
                message=f"未找到第二个曲面: {second_surface}"
            )
        
        # 获取或创建几何集
        target_body = None
        for hb in part.hybrid_bodies:
            if hb.name.lower() == body_name.lower():
                target_body = hb
                break
        
        if target_body is None:
            target_body = part.hybrid_bodies.add()
            target_body.name = body_name
        
        # 创建圆角
        ref1 = part.create_reference_from_object(first)
        ref2 = part.create_reference_from_object(second)
        
        fillet = hsf.add_new_fillet_bi_tangent(
            ref1, ref2, radius,
            1, 1,  # orientation
            1,     # support mode
            1      # trim mode
        )
        
        # 命名
        if name is None:
            name = f"Fillet_R{int(radius)}"
        fillet.name = name
        
        target_body.append_hybrid_shape(fillet)
        part.in_work_object = fillet
        part.update()
        
        logger.info(f"创建圆角: {name} (半径: {radius}mm)")
        return _result_json(
            success=True,
            message=f"成功创建圆角: {name}",
            data={
                "fillet_name": name,
                "radius": radius,
                "surface1": first_surface,
                "surface2": second_surface
            }
        )
        
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建圆角失败: {e}")
        return _result_json(success=False, message=f"创建圆角失败: {e}")


@mcp.tool(description="Get information about the current active Part document.")
def get_part_info() -> str:
    """
    获取当前 Part 信息
    
    Returns:
        JSON 字符串，包含 Part 的详细信息
    """
    try:
        conn = _connection
        part = conn.get_active_part()
        
        # 收集信息
        info = {
            "part_name": part.name,
            "hybrid_bodies_count": part.hybrid_bodies.count,
            "bodies_count": part.bodies.count,
            "hybrid_bodies": [],
            "main_body_name": part.main_body.name if part.main_body else None
        }
        
        # 遍历几何集
        for i in range(1, part.hybrid_bodies.count + 1):
            hb = part.hybrid_bodies.item(i)
            hb_info = {
                "name": hb.name,
                "shapes_count": hb.hybrid_shapes.count if hasattr(hb, 'hybrid_shapes') else 0,
                "sketches_count": hb.hybrid_sketches.count if hasattr(hb, 'hybrid_sketches') else 0
            }
            info["hybrid_bodies"].append(hb_info)
        
        return _result_json(
            success=True,
            message="成功获取 Part 信息",
            data=info
        )
        
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"获取 Part 信息失败: {e}")
        return _result_json(success=False, message=f"获取 Part 信息失败: {e}")


@mcp.tool(description="Save the current Part document to a file.")
def save_part(
    file_path: str = Field(
        default=None,
        description="File path to save (optional, uses current path if not specified)"
    )
) -> str:
    """
    保存当前 Part 文档
    
    Returns:
        JSON 字符串，包含保存结果
    """
    try:
        conn = _connection
        doc = conn.doc
        
        if doc is None:
            return _result_json(
                success=False,
                message="没有打开的文档可保存"
            )
        
        if file_path:
            doc.save_as(file_path)
            saved_path = file_path
        else:
            doc.save()
            saved_path = doc.full_name if hasattr(doc, 'full_name') else "当前位置"
        
        logger.info(f"文档已保存: {saved_path}")
        return _result_json(
            success=True,
            message=f"文档已保存",
            data={"file_path": saved_path}
        )
        
    except Exception as e:
        logger.error(f"保存文档失败: {e}")
        return _result_json(success=False, message=f"保存文档失败: {e}")


# ==================== Entry Point ====================

if __name__ == "__main__":
    logger.info("启动 CATIA MCP Server...")
    mcp.run()

