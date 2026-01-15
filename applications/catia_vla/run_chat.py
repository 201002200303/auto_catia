#!/usr/bin/env python
"""
CATIA VLA 对话建模入口

这是真正可用的端到端入口，您可以：
1. 和大模型对话
2. 用自然语言描述建模需求
3. 实际在 CATIA 中创建 3D 模型

使用方法:
    # 1. 配置环境变量（复制 .env.example 为 .env 并填写）
    
    # 2. 启动 Web 界面（推荐）
    python run_chat.py
    
    # 3. 或启动命令行模式
    python run_chat.py --cli
    
    # 4. 快速测试（不启动 CATIA）
    python run_chat.py --test

Author: CATIA VLA Team
Date: 2026-01-08
"""

import asyncio
import os
import sys
import argparse
import logging
from pathlib import Path

# 确保项目根目录在路径中
_current_dir = Path(__file__).parent.resolve()
_project_root = _current_dir.parent.parent
sys.path.insert(0, str(_project_root))

# 加载 .env 文件
def load_env():
    """加载 .env 配置文件"""
    env_file = _current_dir / ".env"
    if env_file.exists():
        print(f"📄 加载配置: {env_file}")
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
    else:
        print(f"⚠️ 未找到 .env 文件，请复制 .env.example 为 .env 并配置")
        print(f"   cp {_current_dir}/.env.example {_current_dir}/.env")

load_env()

# 现在可以导入 oxygent
from oxygent import MAS, oxy, Config
from oxygent.schemas import LLMResponse, LLMState
import re

# 导入工具集
from function_hubs.catia_api_tools import catia_api_tools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 自定义 LLM 响应解析器 ====================
# 支持两种格式：JSON 格式 和 tool_code 格式

def parse_llm_response_with_tool_code(ori_response: str, oxy_request=None) -> LLMResponse:
    """
    自定义 LLM 响应解析器
    
    支持两种格式：
    1. JSON 格式: ```json {"tool_name": "xxx", "arguments": {...}} ```
    2. tool_code 格式: ```tool_code create_new_part() ```
    """
    import json
    import ast

    tool_name_set = set()
    try:
        tool_name_set = set(getattr(catia_api_tools, "func_dict", {}).keys())
    except Exception:
        tool_name_set = set()

    def _safe_eval_ast(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "True":
                return True
            if node.id == "False":
                return False
            if node.id == "None":
                return None
            raise ValueError(f"Unsupported name: {node.id}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = _safe_eval_ast(node.operand)
            if not isinstance(val, (int, float)):
                raise ValueError("Unary operator only supports numeric values")
            return +val if isinstance(node.op, ast.UAdd) else -val
        if isinstance(node, ast.List):
            return [_safe_eval_ast(elt) for elt in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(_safe_eval_ast(elt) for elt in node.elts)
        if isinstance(node, ast.Dict):
            return {
                _safe_eval_ast(k): _safe_eval_ast(v)
                for k, v in zip(node.keys, node.values)
            }
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")

    def _parse_call_text(call_text: str):
        call_text = call_text.strip().rstrip(";")
        try:
            expr = ast.parse(call_text, mode="eval").body
        except Exception:
            return None, None
        if not isinstance(expr, ast.Call):
            return None, None
        if not isinstance(expr.func, ast.Name):
            return None, None
        tool_name = expr.func.id
        if tool_name_set and tool_name not in tool_name_set:
            return None, None
        if expr.args:
            return tool_name, None
        arguments = {}
        for kw in expr.keywords:
            if kw.arg is None:
                return tool_name, None
            arguments[kw.arg] = _safe_eval_ast(kw.value)
        return tool_name, arguments

    def _find_first_call_line(block_text: str):
        for raw_line in block_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if re.match(r"^\w+\s*\(.*\)\s*$", line):
                name = re.match(r"^(\w+)\s*\(", line).group(1)
                if not tool_name_set or name in tool_name_set:
                    return line
        return None
    
    # 1. 首先尝试标准 JSON 格式
    json_matches = re.findall(r"```[\n]*json(.*?)```", ori_response, re.DOTALL)
    if json_matches:
        try:
            json_text = json_matches[0].strip()
            tool_call_dict = json.loads(json_text)
            if "tool_name" in tool_call_dict:
                return LLMResponse(
                    state=LLMState.TOOL_CALL,
                    output=tool_call_dict,
                    ori_response=ori_response,
                )
        except json.JSONDecodeError:
            pass
    
    # 2. 尝试 tool_code 格式
    tool_code_matches = re.findall(r"```tool_code\s*\n?(.*?)```", ori_response, re.DOTALL)
    if tool_code_matches:
        # 只取第一个 tool_code（每次只执行一个工具）
        tool_code = tool_code_matches[0].strip()

        call_line = _find_first_call_line(tool_code) or tool_code
        tool_name, arguments = _parse_call_text(call_line)
        if tool_name and isinstance(arguments, dict):
            logger.info(f"解析 tool_code: {tool_name}({arguments})")
            return LLMResponse(
                state=LLMState.TOOL_CALL,
                output={"tool_name": tool_name, "arguments": arguments},
                ori_response=ori_response,
            )
        if tool_name and arguments is None:
            logger.info(f"解析 tool_code: {tool_name}(args_not_supported)")
            return LLMResponse(
                state=LLMState.TOOL_CALL,
                output={"tool_name": tool_name, "arguments": {}},
                ori_response=ori_response,
            )

    # 3. 尝试 python 代码块（有些模型会用 ```python 输出工具调用）
    python_matches = re.findall(r"```[\n]*python(.*?)```", ori_response, re.DOTALL)
    if python_matches:
        block = python_matches[0].strip()
        call_line = _find_first_call_line(block)
        if call_line:
            tool_name, arguments = _parse_call_text(call_line)
            if tool_name and isinstance(arguments, dict):
                logger.info(f"解析 python: {tool_name}({arguments})")
                return LLMResponse(
                    state=LLMState.TOOL_CALL,
                    output={"tool_name": tool_name, "arguments": arguments},
                    ori_response=ori_response,
                )
            if tool_name and arguments is None:
                logger.info(f"解析 python: {tool_name}(args_not_supported)")
                return LLMResponse(
                    state=LLMState.TOOL_CALL,
                    output={"tool_name": tool_name, "arguments": {}},
                    ori_response=ori_response,
                )
    
    # 4. 没有找到工具调用，返回普通回答
    # 清理响应中的 think 标签
    clean_response = ori_response
    if "</think>" in clean_response:
        clean_response = clean_response.split("</think>")[-1].strip()
    
    return LLMResponse(
        state=LLMState.ANSWER,
        output=clean_response,
        ori_response=ori_response,
    )

# ==================== 补充提示词 ====================
# 注意：使用 additional_prompt 而不是 prompt，
# 这样框架的默认 SYSTEM_PROMPT（包含工具调用格式）会被保留

CATIA_ADDITIONAL_PROMPT = """
## CATIA 建模专用指南

你是 CATIA 3D 建模助手。你必须通过调用工具来实际执行操作。

### 重要：工具调用格式

当你需要调用工具时，必须严格使用以下 JSON 格式（每次只调用一个工具）：

```json
{
    "think": "我的思考过程",
    "tool_name": "工具名称",
    "arguments": {
        "参数名": "参数值"
    }
}
```

### 建模流程示例

用户说"创建一个100mm的立方体"，你应该：

第1步 - 调用 create_new_part：
```json
{
    "think": "首先需要创建一个新的Part文档",
    "tool_name": "create_new_part",
    "arguments": {
        "visible": true
    }
}
```

收到结果后，第2步 - 调用 create_rectangle_sketch：
```json
{
    "think": "创建100x100的正方形草图作为底面",
    "tool_name": "create_rectangle_sketch",
    "arguments": {
        "support_plane": "PlaneXY",
        "length": 100,
        "width": 100
    }
}
```

收到结果后，第3步 - 调用 create_pad：
```json
{
    "think": "将草图拉伸100mm形成立方体",
    "tool_name": "create_pad",
    "arguments": {
        "profile_name": "上一步返回的草图名",
        "height": 100
    }
}
```

### 参数说明

- **support_plane**: "PlaneXY"（水平）、"PlaneYZ"（正视）、"PlaneZX"（侧视）
- **length/width**: 尺寸（毫米）
- **height**: 拉伸高度（毫米）
- **profile_name**: 使用上一步 create_rectangle_sketch 返回的草图名称

### 注意事项

1. 每次只调用一个工具，等待结果后再调用下一个
2. 可以使用 JSON 格式或 tool_code 格式调用工具
3. 确保 CATIA 已启动
4. 等待每个工具的执行结果后再调用下一个工具

### 强制要求

每次需要执行操作时，只输出一个工具调用，必须放在 ```json 或 ```tool_code 代码块中。不要使用 ```python 代码块，不要一次输出多个步骤。
"""

# ==================== 创建 OxySpace ====================

def create_oxy_space():
    """创建智能体配置"""
    api_key = os.getenv("DEFAULT_LLM_API_KEY")
    base_url = os.getenv("DEFAULT_LLM_BASE_URL")
    model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")
    
    if not api_key or api_key == "sk-your-api-key-here":
        logger.error("❌ 请先配置 DEFAULT_LLM_API_KEY")
        logger.error("   编辑 .env 文件并填写您的 API Key")
        sys.exit(1)
    
    logger.info(f"🤖 LLM 配置: {model_name} @ {base_url}")
    
    return [
        # LLM 配置
        oxy.HttpLLM(
            name="default_llm",
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
        ),
        
        # CATIA 工具集
        catia_api_tools,
        
        # ReAct 智能体
        # 使用自定义解析器支持 tool_code 格式
        oxy.ReActAgent(
            name="catia_agent",
            llm_model="default_llm",
            tools=["catia_api_tools"],
            additional_prompt=CATIA_ADDITIONAL_PROMPT,
            max_react_rounds=10,
            func_parse_llm_response=parse_llm_response_with_tool_code,
        ),
    ]


# ==================== 主函数 ====================

async def run_web(first_query: str = None):
    """启动 Web 界面"""
    oxy_space = create_oxy_space()
    
    print("\n" + "=" * 60)
    print("🚀 CATIA VLA 智能建模助手")
    print("=" * 60)
    print("\n📝 示例指令：")
    print("   • '创建一个 100x100x100 的立方体'")
    print("   • '建一个 200x100x50 的长方体'")
    print("   • '在 XY 平面画一个 150x80 的矩形草图'")
    print("   • '把刚才的草图拉伸 60mm'")
    print("\n⚠️  确保 CATIA 已启动！")
    print("=" * 60 + "\n")
    
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query=first_query or "你好！我是 CATIA 建模助手，请告诉我你想创建什么模型？"
        )


async def run_cli(first_query: str = None):
    """启动命令行模式"""
    oxy_space = create_oxy_space()
    
    print("\n" + "=" * 60)
    print("🚀 CATIA VLA 智能建模助手 (CLI 模式)")
    print("=" * 60)
    print("\n输入 'exit' 或 'quit' 退出")
    print("=" * 60 + "\n")
    
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_cli_mode(
            first_query=first_query or "你好！告诉我你想创建什么 3D 模型"
        )


async def run_single_query(query: str):
    """单次查询模式（用于测试）"""
    oxy_space = create_oxy_space()
    
    print(f"\n📝 执行查询: {query}\n")
    
    async with MAS(oxy_space=oxy_space) as mas:
        response = await mas.chat_with_agent(payload={"query": query})
        # response 可能是字符串或对象
        output = response.output if hasattr(response, 'output') else str(response)
        print(f"\n🤖 响应:\n{output}")
        return response


async def run_test():
    """测试模式（不需要 CATIA）"""
    print("\n" + "=" * 60)
    print("🧪 测试模式 - 验证配置")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv("DEFAULT_LLM_API_KEY")
    base_url = os.getenv("DEFAULT_LLM_BASE_URL")
    model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")
    
    print(f"\n✅ API Key: {'已配置' if api_key and api_key != 'sk-your-api-key-here' else '❌ 未配置'}")
    print(f"✅ Base URL: {base_url or '❌ 未配置'}")
    print(f"✅ Model: {model_name or '❌ 未配置'}")
    
    # 检查工具
    print(f"\n✅ CATIA 工具: {list(catia_api_tools.func_dict.keys())}")
    
    # 测试 LLM 连接
    if api_key and api_key != "sk-your-api-key-here":
        print("\n🔄 测试 LLM 连接...")
        try:
            oxy_space = create_oxy_space()
            async with MAS(oxy_space=oxy_space) as mas:
                response = await mas.call(
                    callee="default_llm",
                    arguments={
                        "messages": [
                            {"role": "user", "content": "回复 'OK' 表示连接成功"}
                        ],
                    },
                )
                # response 可能是字符串或对象
                output = response.output if hasattr(response, 'output') else str(response)
                print(f"✅ LLM 连接成功: {output[:50]}...")
        except Exception as e:
            print(f"❌ LLM 连接失败: {e}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="CATIA VLA 对话建模入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_chat.py              # 启动 Web 界面
  python run_chat.py --cli        # 启动命令行模式
  python run_chat.py --test       # 测试配置
  python run_chat.py -q "创建立方体"  # 单次查询
        """
    )
    parser.add_argument(
        "--cli", "-c",
        action="store_true",
        help="使用命令行模式而非 Web 界面"
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="测试模式，验证配置是否正确"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="单次查询模式，执行指定指令后退出"
    )
    
    args = parser.parse_args()
    
    if args.test:
        asyncio.run(run_test())
    elif args.query:
        asyncio.run(run_single_query(args.query))
    elif args.cli:
        asyncio.run(run_cli())
    else:
        asyncio.run(run_web())


if __name__ == "__main__":
    main()

