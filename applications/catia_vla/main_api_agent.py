"""
CATIA API Agent - 基于 OxyGent ReActAgent 的 CATIA 自动化智能体

使用 catia_api_tools FunctionHub 执行几何建模操作。
支持自然语言指令理解和执行。

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

# 导入 CATIA API 工具集
from function_hubs.catia_api_tools import catia_api_tools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== System Prompt ====================

CATIA_AGENT_PROMPT = """
你是一个专业的 CATIA 3D 建模助手。你可以通过调用工具来帮助用户完成各种建模任务。

## 可用工具

1. `create_new_part` - 创建新的 Part 文档（这是第一步，必须先调用）
2. `create_rectangle_sketch` - 在指定平面上创建矩形草图
3. `create_pad` - 从草图创建凸台（实体拉伸）
4. `create_pocket` - 从草图创建凹槽（实体切除）
5. `create_empty_sketch` - 创建空草图（用于后续逐步添加 2D 元素）
6. `add_circle_to_sketch` - 向草图添加圆或圆弧
7. `add_polyline_to_sketch` - 向草图添加折线（可选闭合）
8. `add_spline_to_sketch` - 向草图添加样条曲线（可选闭合）
9. `create_extrude` - 创建曲面拉伸
10. `create_fillet` - 创建圆角
11. `get_part_info` - 获取当前 Part 信息
12. `save_part` - 保存 Part 文档

## 工作流程

1. 首先调用 `create_new_part` 创建文档
2. 使用 `create_rectangle_sketch` 或 `create_empty_sketch` 创建草图
3. 用 `add_circle_to_sketch` / `add_polyline_to_sketch` / `add_spline_to_sketch` 补充草图 2D 元素
4. 使用 `create_pad` 或 `create_pocket` 创建实体特征，或用 `create_extrude` 创建曲面
4. 操作完成后告知用户结果

## 注意事项

- **坐标系**：CATIA 使用毫米 (mm) 作为默认单位
- **平面命名**：
  - `PlaneXY` - 水平面（俯视图）
  - `PlaneYZ` - 正视面（前视图）
  - `PlaneZX` - 侧视面（右视图）
- **草图必须先创建才能用于凸台或拉伸**
- **凸台 (Pad)** 创建实体，**拉伸 (Extrude)** 创建曲面

## 典型建模流程示例

### 示例1：创建立方体
用户: "创建一个 100x100x100 的立方体"

思考: 
1. 需要先创建 Part
2. 然后在 XY 平面创建 100x100 的矩形草图
3. 最后拉伸 100mm 创建立方体

执行步骤:
1. create_new_part()
2. create_rectangle_sketch(support_plane="PlaneXY", length=100, width=100, name="Base_Square")
3. create_pad(profile_name="Base_Square", height=100, name="Cube")

### 示例2：创建长方体
用户: "创建一个 200x100x50 的长方体"

执行步骤:
1. create_new_part()
2. create_rectangle_sketch(support_plane="PlaneXY", length=200, width=100, name="Base_Rect")
3. create_pad(profile_name="Base_Rect", height=50, name="Block")

### 示例3：创建多个几何体
如果用户需要创建多个几何体，在同一个 Part 中依次创建即可。

## 错误处理

- 如果工具返回 `success: false`，请根据错误信息进行处理
- 常见错误：
  - "无法连接到 CATIA" → 提示用户启动 CATIA
  - "未找到草图" → 检查草图名称是否正确
  - "没有打开的文档" → 先调用 create_new_part

## 回复格式

完成操作后，请用简洁的语言告知用户：
1. 执行了什么操作
2. 创建了什么几何体
3. 如果有问题，说明原因和建议
"""


# ==================== OxySpace 配置 ====================

def create_oxy_space():
    """创建 OxyGent 配置空间"""
    return [
        # LLM 配置
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        ),
        
        # CATIA API 工具集
        catia_api_tools,
        
        # CATIA 建模智能体
        oxy.ReActAgent(
            name="catia_agent",
            llm_model="default_llm",
            tools=["catia_api_tools"],
            prompt=CATIA_AGENT_PROMPT,
            max_react_rounds=10,
            additional_prompt="请根据用户的建模需求，一步步调用工具完成任务。",
        ),
    ]


# 导出 oxy_space 供外部使用
oxy_space = create_oxy_space()


# ==================== 主函数 ====================

async def main(first_query: str = None, dry_run: bool = False):
    """
    主函数
    
    Args:
        first_query: 初始查询（可选）
        dry_run: 是否只验证配置而不启动服务
    """
    if dry_run:
        logger.info("Dry-run 模式：验证配置...")
        logger.info(f"OxySpace 配置项: {len(oxy_space)}")
        for item in oxy_space:
            logger.info(f"  - {item.name}: {type(item).__name__}")
        logger.info("配置验证通过！")
        return
    
    # 默认查询
    if first_query is None:
        first_query = "创建一个 100x100x100 的立方体"
    
    logger.info(f"启动 CATIA API Agent，初始查询: {first_query}")
    
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query=first_query
        )


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="CATIA API Agent - 基于 OxyGent 的 CATIA 自动化建模智能体"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="初始查询语句（默认：创建一个 100x100x100 的立方体）"
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
