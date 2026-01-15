"""
CATIA API Tools - OxyGent FunctionHub 集成

封装 pycatia 调用为 OxyGent FunctionHub 工具集。
采用方案 A：直接调用 pycatia（单进程模式）。

Author: CATIA VLA Team
"""

import json
import logging
from typing import Optional

from pydantic import Field

from oxygent.oxy import FunctionHub

# 配置日志
logger = logging.getLogger(__name__)

# 初始化 FunctionHub
catia_api_tools = FunctionHub(
    name="catia_api_tools",
    desc="CATIA 参数化建模 API 工具集 - 提供几何建模操作"
)


# ==================== CATIA 连接管理 ====================

class CATIAManager:
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
        """获取 CATIA 应用程序对象（延迟连接）"""
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
    
    def get_active_part(self):
        """获取当前活动的 Part"""
        if self._part is not None:
            return self._part
        
        try:
            doc = self.catia.active_document
            if doc is None:
                raise ValueError("没有打开的文档。请先调用 create_new_part 创建文档。")
            self._doc = doc
            self._part = doc.part
            return self._part
        except Exception as e:
            raise ValueError(f"无法获取当前 Part: {e}")
    
    def reset(self):
        """重置连接状态"""
        self._part = None
        self._doc = None


# 全局管理器实例
_manager = CATIAManager()


def _result_json(success: bool, message: str, data: Optional[dict] = None) -> str:
    """统一的 JSON 返回格式"""
    result = {
        "success": success,
        "message": message
    }
    if data:
        result["data"] = data
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== FunctionHub Tools ====================

@catia_api_tools.tool(
    description="创建新的 CATIA Part 文档。这是建模操作的第一步，必须先调用此函数。"
)
def create_new_part(
    visible: bool = Field(
        default=True,
        description="是否显示 CATIA 窗口（默认 True）"
    )
) -> str:
    """
    创建新的 Part 文档
    
    Returns:
        JSON 字符串，包含 success, message, data (part_name)
    """
    try:
        manager = _manager
        caa = manager.catia
        
        # 设置可见性
        caa.visible = visible
        
        # 创建新文档
        documents = caa.documents
        doc = documents.add("Part")
        
        # 保存引用
        manager.doc = doc
        manager.part = doc.part
        
        part_name = manager.part.name
        
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


@catia_api_tools.tool(
    description="在指定平面上创建矩形草图。矩形以原点为中心。支持平面：PlaneXY（水平）、PlaneYZ（正视）、PlaneZX（侧视）"
)
def create_rectangle_sketch(
    support_plane: str = Field(
        description="支撑平面名称：'PlaneXY'、'PlaneYZ' 或 'PlaneZX'"
    ),
    length: float = Field(description="矩形长度（mm，X 方向）"),
    width: float = Field(description="矩形宽度（mm，Y 方向）"),
    body_name: str = Field(
        default="Geometry",
        description="目标几何集名称（默认：'Geometry'）"
    ),
    name: str = Field(
        default=None,
        description="自定义草图名称（留空则自动生成）"
    )
) -> str:
    """
    创建矩形草图
    
    Returns:
        JSON 字符串，包含 success, message, data (sketch_name)
    """
    try:
        manager = _manager
        part = manager.get_active_part()
        
        # 获取支撑平面
        origin = part.origin_elements
        plane_map = {
            "planexy": origin.plane_xy,
            "planeyz": origin.plane_yz,
            "planezx": origin.plane_zx,
        }
        
        support = plane_map.get(support_plane.lower())
        if support is None:
            return _result_json(
                success=False,
                message=f"未找到平面: {support_plane}。支持: PlaneXY, PlaneYZ, PlaneZX"
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


@catia_api_tools.tool(
    description="从草图创建凸台（实体拉伸）。草图必须是封闭轮廓。这将创建一个 3D 实体特征。"
)
def create_pad(
    profile_name: str = Field(description="要拉伸的草图轮廓名称"),
    height: float = Field(description="凸台高度（mm）"),
    name: str = Field(
        default=None,
        description="自定义凸台名称（留空则自动生成）"
    )
) -> str:
    """
    从草图创建凸台
    
    Returns:
        JSON 字符串，包含 success, message, data (pad_name)
    """
    try:
        manager = _manager
        part = manager.get_active_part()
        
        # 查找草图
        sketch = None
        for hb in part.hybrid_bodies:
            try:
                sketch = hb.hybrid_sketches.item(profile_name)
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


@catia_api_tools.tool(
    description="将轮廓曲线沿指定方向拉伸成曲面。支持双向拉伸。"
)
def create_extrude(
    profile_name: str = Field(description="要拉伸的轮廓曲线或草图名称"),
    direction: str = Field(
        description="拉伸方向：'PlaneXY'、'PlaneYZ'、'PlaneZX'、'XAxis'、'YAxis' 或 'ZAxis'"
    ),
    length1: float = Field(description="第一方向拉伸长度（mm）"),
    length2: float = Field(
        default=0.0,
        description="第二方向拉伸长度（mm，默认 0）"
    ),
    body_name: str = Field(
        default="Geometry",
        description="目标几何集名称（默认：'Geometry'）"
    ),
    name: str = Field(
        default=None,
        description="自定义特征名称（留空则自动生成）"
    )
) -> str:
    """
    创建曲面拉伸
    
    Returns:
        JSON 字符串，包含 success, message, data (extrude_name)
    """
    try:
        manager = _manager
        part = manager.get_active_part()
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


@catia_api_tools.tool(
    description="在两个曲面之间创建圆角过渡。"
)
def create_fillet(
    first_surface: str = Field(description="第一个曲面名称"),
    second_surface: str = Field(description="第二个曲面名称"),
    radius: float = Field(description="圆角半径（mm）"),
    body_name: str = Field(
        default="Geometry",
        description="目标几何集名称（默认：'Geometry'）"
    ),
    name: str = Field(
        default=None,
        description="自定义特征名称（留空则自动生成）"
    )
) -> str:
    """
    创建双切圆角
    
    Returns:
        JSON 字符串，包含 success, message, data (fillet_name)
    """
    try:
        manager = _manager
        part = manager.get_active_part()
        hsf = part.hybrid_shape_factory
        
        # 查找两个曲面
        def find_shape(shape_name):
            for hb in part.hybrid_bodies:
                try:
                    return hb.hybrid_shapes.item(shape_name)
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


@catia_api_tools.tool(
    description="获取当前 Part 文档的详细信息，包括几何集、特征等。"
)
def get_part_info() -> str:
    """
    获取当前 Part 信息
    
    Returns:
        JSON 字符串，包含 Part 的详细信息
    """
    try:
        manager = _manager
        part = manager.get_active_part()
        
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


@catia_api_tools.tool(
    description="保存当前 Part 文档。可以指定保存路径，或保存到当前位置。"
)
def save_part(
    file_path: str = Field(
        default=None,
        description="保存文件路径（可选，留空则保存到当前位置）"
    )
) -> str:
    """
    保存当前 Part 文档
    
    Returns:
        JSON 字符串，包含保存结果
    """
    try:
        manager = _manager
        doc = manager.doc
        
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


def _get_or_create_hybrid_body(part, body_name: str):
    target_body = None
    for hb in part.hybrid_bodies:
        if hb.name.lower() == body_name.lower():
            target_body = hb
            break
    if target_body is None:
        target_body = part.hybrid_bodies.add()
        target_body.name = body_name
    return target_body


def _find_sketch(part, sketch_name: str):
    for hb in part.hybrid_bodies:
        try:
            return hb.hybrid_sketches.item(sketch_name)
        except Exception:
            continue
    return None


def _resolve_support_plane(part, support_plane: str):
    origin = part.origin_elements
    plane_map = {
        "planexy": origin.plane_xy,
        "planeyz": origin.plane_yz,
        "planezx": origin.plane_zx,
    }
    return plane_map.get(support_plane.lower())


def _open_sketch_edition(sketch):
    factory2d = sketch.open_edition()
    factory2d_com = getattr(factory2d, "com_object", factory2d)
    return factory2d, factory2d_com


@catia_api_tools.tool(
    description="创建一个空草图（不绘制几何元素），用于后续逐步添加2D元素。"
)
def create_empty_sketch(
    support_plane: str = Field(
        description="支撑平面名称：'PlaneXY'、'PlaneYZ' 或 'PlaneZX'"
    ),
    body_name: str = Field(
        default="Geometry",
        description="目标几何集名称（默认：'Geometry'）"
    ),
    name: str = Field(
        default=None,
        description="自定义草图名称（留空则自动生成）"
    )
) -> str:
    try:
        manager = _manager
        part = manager.get_active_part()

        support = _resolve_support_plane(part, support_plane)
        if support is None:
            return _result_json(
                success=False,
                message=f"未找到平面: {support_plane}。支持: PlaneXY, PlaneYZ, PlaneZX"
            )

        target_body = _get_or_create_hybrid_body(part, body_name)
        ref_support = part.create_reference_from_object(support)
        sketch = target_body.hybrid_sketches.add(ref_support)

        if name is None:
            name = f"Sketch_{support_plane}"
        sketch.name = name

        part.update_object(sketch)
        part.update()

        logger.info(f"创建空草图: {name} ({support_plane})")
        return _result_json(
            success=True,
            message=f"成功创建空草图: {name}",
            data={
                "sketch_name": name,
                "plane": support_plane,
                "body_name": body_name,
            }
        )
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建空草图失败: {e}")
        return _result_json(success=False, message=f"创建空草图失败: {e}")


@catia_api_tools.tool(
    description="向指定草图添加圆或圆弧（CreateCircle）。角度单位为弧度，完整圆可使用 0 到 2π。"
)
def add_circle_to_sketch(
    sketch_name: str = Field(description="目标草图名称"),
    center_x: float = Field(default=0.0, description="圆心 X 坐标（mm）"),
    center_y: float = Field(default=0.0, description="圆心 Y 坐标（mm）"),
    radius: float = Field(description="半径（mm）"),
    start_angle: float = Field(default=0.0, description="起始角度（弧度，默认 0）"),
    end_angle: float = Field(
        default=6.283185307179586,
        description="结束角度（弧度，默认 2π）"
    ),
    name: str = Field(
        default=None,
        description="自定义曲线名称（留空则不命名或由CATIA自动命名）"
    )
) -> str:
    try:
        if radius <= 0:
            return _result_json(success=False, message="半径必须大于 0")

        manager = _manager
        part = manager.get_active_part()

        sketch = _find_sketch(part, sketch_name)
        if sketch is None:
            return _result_json(success=False, message=f"未找到草图: {sketch_name}")

        factory2d, factory2d_com = _open_sketch_edition(sketch)

        circle = None
        try:
            if (
                hasattr(factory2d_com, "CreateClosedCircle")
                and abs((end_angle - start_angle) - 6.283185307179586) < 1e-6
            ):
                circle = factory2d_com.CreateClosedCircle(center_x, center_y, radius)
            elif hasattr(factory2d_com, "CreateCircle"):
                circle = factory2d_com.CreateCircle(
                    center_x, center_y, radius, start_angle, end_angle
                )
        except Exception:
            circle = None

        if circle is None:
            try:
                if hasattr(factory2d, "create_circle"):
                    circle = factory2d.create_circle(
                        center_x, center_y, radius, start_angle, end_angle
                    )
            except Exception:
                circle = None

        sketch.close_edition()
        part.update_object(sketch)
        part.update()

        if circle is None:
            return _result_json(success=False, message="创建圆/圆弧失败：未找到可用的 Factory2D 接口")

        if name is not None:
            try:
                circle.name = name
            except Exception:
                pass

        logger.info(f"草图添加圆/圆弧: {sketch_name} (R={radius}mm)")
        return _result_json(
            success=True,
            message=f"成功添加圆/圆弧到草图: {sketch_name}",
            data={
                "sketch_name": sketch_name,
                "radius": radius,
                "center": {"x": center_x, "y": center_y},
                "start_angle": start_angle,
                "end_angle": end_angle,
            }
        )
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"添加圆/圆弧失败: {e}")
        return _result_json(success=False, message=f"添加圆/圆弧失败: {e}")


@catia_api_tools.tool(
    description="向指定草图添加折线（多段直线），可选自动闭合（末点回到起点）。"
)
def add_polyline_to_sketch(
    sketch_name: str = Field(description="目标草图名称"),
    points: list = Field(description="点序列，例如 [[0,0],[10,0],[10,10]]"),
    close: bool = Field(default=False, description="是否自动闭合（默认 False）"),
    name_prefix: str = Field(
        default=None,
        description="线段名前缀（留空则不命名或由CATIA自动命名）"
    )
) -> str:
    try:
        if not isinstance(points, list) or len(points) < 2:
            return _result_json(success=False, message="points 至少需要 2 个点")
        if close and len(points) < 3:
            return _result_json(success=False, message="close=True 时 points 至少需要 3 个点")

        manager = _manager
        part = manager.get_active_part()

        sketch = _find_sketch(part, sketch_name)
        if sketch is None:
            return _result_json(success=False, message=f"未找到草图: {sketch_name}")

        factory2d, factory2d_com = _open_sketch_edition(sketch)

        def _create_point(x, y):
            if hasattr(factory2d_com, "CreatePoint"):
                return factory2d_com.CreatePoint(x, y)
            if hasattr(factory2d, "create_point"):
                return factory2d.create_point(x, y)
            raise AttributeError("Factory2D 缺少 CreatePoint/create_point")

        def _create_line(x1, y1, x2, y2):
            if hasattr(factory2d_com, "CreateLine"):
                return factory2d_com.CreateLine(x1, y1, x2, y2)
            if hasattr(factory2d, "create_line"):
                return factory2d.create_line(x1, y1, x2, y2)
            raise AttributeError("Factory2D 缺少 CreateLine/create_line")

        created_lines = []
        segment_points = points[:]
        if close:
            segment_points = points[:] + [points[0]]

        for idx in range(len(segment_points) - 1):
            x1, y1 = segment_points[idx]
            x2, y2 = segment_points[idx + 1]

            p_start = _create_point(x1, y1)
            p_end = _create_point(x2, y2)
            line = _create_line(x1, y1, x2, y2)

            if hasattr(line, "StartPoint"):
                try:
                    line.StartPoint = p_start
                    line.EndPoint = p_end
                except Exception:
                    pass
            if hasattr(line, "start_point"):
                try:
                    line.start_point = p_start
                    line.end_point = p_end
                except Exception:
                    pass

            if name_prefix is not None:
                try:
                    line.name = f"{name_prefix}_{idx+1}"
                except Exception:
                    pass

            created_lines.append(line)

        sketch.close_edition()
        part.update_object(sketch)
        part.update()

        logger.info(f"草图添加折线: {sketch_name} (segments={len(created_lines)}, close={close})")
        return _result_json(
            success=True,
            message=f"成功添加折线到草图: {sketch_name}",
            data={
                "sketch_name": sketch_name,
                "segments_count": len(created_lines),
                "closed": close,
            }
        )
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"添加折线失败: {e}")
        return _result_json(success=False, message=f"添加折线失败: {e}")


@catia_api_tools.tool(
    description="向指定草图添加样条曲线（CreateSpline）。控制点为二维坐标列表。"
)
def add_spline_to_sketch(
    sketch_name: str = Field(description="目标草图名称"),
    control_points: list = Field(description="控制点序列，例如 [[0,0],[10,5],[20,0]]"),
    close: bool = Field(default=False, description="是否闭合（默认 False）"),
    name: str = Field(
        default=None,
        description="自定义样条名称（留空则不命名或由CATIA自动命名）"
    )
) -> str:
    try:
        if not isinstance(control_points, list) or len(control_points) < 2:
            return _result_json(success=False, message="control_points 至少需要 2 个点")

        cps = control_points[:]
        if close and cps[0] != cps[-1]:
            cps = cps + [cps[0]]

        manager = _manager
        part = manager.get_active_part()

        sketch = _find_sketch(part, sketch_name)
        if sketch is None:
            return _result_json(success=False, message=f"未找到草图: {sketch_name}")

        factory2d, factory2d_com = _open_sketch_edition(sketch)

        spline = None
        try:
            if hasattr(factory2d_com, "CreateControlPoint") and hasattr(factory2d_com, "CreateSpline"):
                cp_objs = []
                for x, y in cps:
                    cp_objs.append(factory2d_com.CreateControlPoint(x, y))
                spline = factory2d_com.CreateSpline(tuple(cp_objs))
        except Exception:
            spline = None

        if spline is None:
            sketch.close_edition()
            part.update_object(sketch)
            part.update()
            return _result_json(success=False, message="创建样条失败：未找到可用的 Factory2D CreateSpline 接口")

        sketch.close_edition()
        part.update_object(sketch)
        part.update()

        if name is not None:
            try:
                spline.name = name
            except Exception:
                pass

        logger.info(f"草图添加样条: {sketch_name} (points={len(cps)}, close={close})")
        return _result_json(
            success=True,
            message=f"成功添加样条到草图: {sketch_name}",
            data={
                "sketch_name": sketch_name,
                "control_points_count": len(cps),
                "closed": close,
            }
        )
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"添加样条失败: {e}")
        return _result_json(success=False, message=f"添加样条失败: {e}")


@catia_api_tools.tool(
    description="从草图创建凹槽（Pocket），用于切除材料。草图必须是封闭轮廓。"
)
def create_pocket(
    profile_name: str = Field(description="要切除的草图轮廓名称"),
    depth: float = Field(description="凹槽深度（mm）"),
    name: str = Field(
        default=None,
        description="自定义凹槽名称（留空则自动生成）"
    )
) -> str:
    try:
        manager = _manager
        part = manager.get_active_part()

        sketch = _find_sketch(part, profile_name)
        if sketch is None:
            return _result_json(success=False, message=f"未找到草图: {profile_name}")

        part.in_work_object = part.main_body
        sf = part.shape_factory

        pocket = None
        if hasattr(sf, "add_new_pocket"):
            pocket = sf.add_new_pocket(sketch, depth)
        elif hasattr(sf, "AddNewPocket"):
            pocket = sf.AddNewPocket(sketch, depth)
        else:
            return _result_json(success=False, message="ShapeFactory 不支持 Pocket 创建接口")

        if name is None:
            name = f"Pocket_{int(depth)}mm"
        try:
            pocket.name = name
        except Exception:
            pass

        part.update_object(pocket)
        part.update()

        logger.info(f"创建凹槽: {name} (深度: {depth}mm)")
        return _result_json(
            success=True,
            message=f"成功创建凹槽: {name}",
            data={
                "pocket_name": name,
                "depth": depth,
                "profile": profile_name
            }
        )
    except ValueError as e:
        return _result_json(success=False, message=str(e))
    except Exception as e:
        logger.error(f"创建凹槽失败: {e}")
        return _result_json(success=False, message=f"创建凹槽失败: {e}")
