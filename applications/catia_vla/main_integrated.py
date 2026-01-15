"""
CATIA VLA Agent - OxyGent 集成主程序

展示如何将 CATIA VLA 工具集成到 OxyGent 多智能体系统中。
"""

import asyncio
import os
from pathlib import Path

from oxygent import MAS, Config, oxy, preset_tools
from function_hubs import catia_tools

# 配置 Agent 使用的 LLM 模型
Config.set_agent_llm_model("default_llm")

# 定义 OxySpace（包含所有工具和智能体）
oxy_space = [
    # LLM 配置
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
    ),
    
    # CATIA 工具集
    catia_tools,
    
    # 预设工具（可选）
    preset_tools.file_tools,
    preset_tools.time_tools,
    
    # CATIA 执行智能体
    oxy.ReActAgent(
        name="catia_executor",
        desc=(
            "CATIA 自动化执行智能体。"
            "能够识别 CATIA 界面元素，执行点击、输入等操作，"
            "完成自动化建模任务。"
        ),
        tools=["catia_tools", "file_tools", "time_tools"],
    ),
    
    # 主智能体（协调者）
    oxy.ReActAgent(
        is_master=True,
        name="master_agent",
        desc="主协调智能体，负责任务规划和子智能体调度",
        sub_agents=["catia_executor"],
    ),
]


async def main():
    """主函数"""
    print("=" * 60)
    print("CATIA VLA Agent - OxyGent 集成")
    print("=" * 60)
    print()
    
    async with MAS(oxy_space=oxy_space) as mas:
        # 启动 Web 服务
        await mas.start_web_service(
            first_query=(
                "请帮我完成以下任务：\n"
                "1. 激活 CATIA 窗口\n"
                "2. 截取当前屏幕\n"
                "3. 识别屏幕上的 UI 元素\n"
                "4. 告诉我检测到了哪些元素"
            )
        )


if __name__ == "__main__":
    asyncio.run(main())


