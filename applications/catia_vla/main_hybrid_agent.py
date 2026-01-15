"""
CATIA Hybrid Agent - 混合驱动 CATIA 自动化智能体

同时注册 API 工具和视觉工具，根据任务自动选择最优执行模态。
支持 API 优先、失败降级到视觉的混合策略。

Author: CATIA VLA Team
"""

import asyncio
import os
import sys
import argparse
import logging

# 确保项目根目录在路径中
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from oxygent import MAS, oxy

# 导入工具集
from function_hubs.catia_api_tools import catia_api_tools
from function_hubs.catia_tools import catia_tools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Hybrid Agent System Prompt ====================

HYBRID_AGENT_PROMPT = """
你是一个专业的 CATIA 3D 建模助手，具有两种操作能力：

## 模态 A: API 操作 (高速精准)

适用于标准几何建模操作，执行速度快、精度高：

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `create_new_part` | 创建新 Part 文档 | 建模的第一步 |
| `create_rectangle_sketch` | 创建矩形草图 | 需要矩形轮廓时 |
| `create_empty_sketch` | 创建空草图 | 逐步添加 2D 元素 |
| `add_circle_to_sketch` | 添加圆/圆弧 | 创建圆形或圆弧轮廓 |
| `add_polyline_to_sketch` | 添加折线（可闭合） | 自定义多边形轮廓 |
| `add_spline_to_sketch` | 添加样条（可闭合） | 不规则曲线轮廓 |
| `create_pad` | 创建凸台 | 将草图拉伸成实体 |
| `create_pocket` | 创建凹槽 | 从草图切除材料 |
| `create_extrude` | 创建曲面拉伸 | 创建曲面 |
| `create_fillet` | 创建圆角 | 边缘倒圆 |
| `get_part_info` | 获取 Part 信息 | 查看当前状态 |
| `save_part` | 保存文档 | 保存工作 |

## 模态 B: 视觉操作 (高兼容性)

适用于 GUI 交互操作，可以处理任何界面元素：

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `capture_screen` | 截取屏幕 | 获取当前界面状态 |
| `detect_ui_elements` | 识别 UI 元素 | 找到图标、按钮位置 |
| `click_element` | 点击坐标 | 执行点击操作 |
| `double_click_element` | 双击坐标 | 双击激活 |
| `input_text` | 输入文本 | 在输入框中输入 |
| `press_key` | 按键 | 按下功能键 |
| `activate_catia_window` | 激活窗口 | 确保 CATIA 在前台 |

## 工具选择策略

遵循以下优先级选择工具：

1. **几何建模操作** → 优先使用 API 工具
   - 创建草图、凸台、拉伸、圆角等
   - API 更快、更精准

2. **工具栏点击** → 使用视觉工具
   - 点击工具栏图标
   - 选择菜单项

3. **对话框处理** → 使用视觉工具
   - 处理弹出对话框
   - 确认/取消操作

4. **文件操作** → 先尝试 API，失败则视觉
   - 保存文件优先用 save_part
   - 如果需要"另存为"则用视觉点击

## 工作流程示例

### 示例 1: 创建立方体（纯 API）

用户: "创建一个 100mm 的立方体"

思考: 这是标准几何建模，使用 API 工具。

执行步骤:
1. `create_new_part()` - 创建文档
2. `create_rectangle_sketch(support_plane="PlaneXY", length=100, width=100)` - 创建底面
3. `create_pad(profile_name="Rect_100x100", height=100)` - 拉伸成立方体

### 示例 2: 点击工具栏（视觉）

用户: "点击'拉伸'工具图标"

思考: 这是 GUI 交互，使用视觉工具。

执行步骤:
1. `activate_catia_window()` - 确保窗口激活
2. `capture_screen()` - 截取屏幕
3. `detect_ui_elements(image_path=截图路径)` - 识别 UI 元素
4. 分析检测结果，找到"拉伸"图标的坐标
5. `click_element(x=图标中心x, y=图标中心y)` - 点击图标

### 示例 3: 混合操作

用户: "创建一个立方体并保存到桌面"

思考: 建模用 API，保存对话框可能需要视觉。

执行步骤:
1. [API] `create_new_part()` - 创建文档
2. [API] `create_rectangle_sketch(...)` - 创建草图
3. [API] `create_pad(...)` - 创建凸台
4. [API] `save_part()` - 先尝试 API 保存
5. 如果需要选择路径：
   - [视觉] `capture_screen()` - 截取保存对话框
   - [视觉] `detect_ui_elements(...)` - 识别输入框
   - [视觉] `click_element(...)` - 点击路径输入框
   - [视觉] `input_text(text="C:\\Users\\Desktop\\cube.CATPart")` - 输入路径
   - [视觉] `click_element(...)` - 点击保存按钮

## 坐标系和单位

- **CATIA 坐标系**: 毫米 (mm) 为默认单位
- **平面命名**:
  - `PlaneXY` - 水平面（俯视图）
  - `PlaneYZ` - 正视面（前视图）
  - `PlaneZX` - 侧视面（右视图）
- **屏幕坐标**: 像素，原点在左上角

## 错误处理

1. **API 失败** → 检查错误信息，尝试修正参数或改用视觉方式
2. **视觉识别失败** → 尝试重新截图，或调整检测参数
3. **CATIA 未启动** → 提示用户启动 CATIA

## 响应格式

完成操作后，请简洁说明：
1. 执行了什么操作
2. 使用了哪种模态（API/视觉）
3. 操作结果
4. 如果有问题，给出建议
"""


# ==================== OxySpace 配置 ====================

def create_hybrid_oxy_space():
    """创建混合智能体 OxySpace 配置"""
    return [
        # LLM 配置
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        ),
        
        # API 工具集（几何建模）
        catia_api_tools,
        
        # 视觉工具集（GUI 交互）
        catia_tools,
        
        # 混合智能体
        oxy.ReActAgent(
            name="catia_hybrid_agent",
            llm_model="default_llm",
            tools=["catia_api_tools", "catia_tools"],
            prompt=HYBRID_AGENT_PROMPT,
            max_react_rounds=15,
            additional_prompt="根据任务类型智能选择工具：几何建模优先 API，GUI 交互使用视觉。",
        ),
    ]


# 导出 oxy_space 供外部使用
oxy_space = create_hybrid_oxy_space()


# ==================== 主函数 ====================

async def main(first_query: str = None, dry_run: bool = False):
    """
    主函数
    
    Args:
        first_query: 初始查询（可选）
        dry_run: 是否只验证配置而不启动服务
    """
    if dry_run:
        logger.info("Dry-run 模式：验证混合智能体配置...")
        logger.info(f"OxySpace 配置项: {len(oxy_space)}")
        for item in oxy_space:
            logger.info(f"  - {item.name}: {type(item).__name__}")
        
        # 检查工具注册
        api_tools = list(catia_api_tools.func_dict.keys())
        vision_tools = list(catia_tools.func_dict.keys())
        
        logger.info(f"API 工具 ({len(api_tools)} 个): {api_tools}")
        logger.info(f"视觉工具 ({len(vision_tools)} 个): {vision_tools}")
        logger.info("混合智能体配置验证通过！")
        return
    
    # 默认查询
    if first_query is None:
        first_query = "创建一个 100x100x100 的立方体"
    
    logger.info(f"启动 CATIA 混合智能体，初始查询: {first_query}")
    
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query=first_query
        )


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="CATIA Hybrid Agent - 混合驱动 CATIA 自动化建模智能体"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="初始查询语句"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证配置，不启动服务"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(first_query=args.query, dry_run=args.dry_run))

