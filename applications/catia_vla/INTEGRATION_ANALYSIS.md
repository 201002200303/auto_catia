# CATIA VLA 项目集成 OxyGent 框架分析报告

## 📋 项目现状分析

### ✅ 已完成模块

1. **感知层 (Perception Layer)**
   - ✅ `VisionService` 类完整实现
   - ✅ 滑动窗口检测 (`detect_full_screen_tiled`)
   - ✅ 可视化功能
   - ✅ 中文名称映射

2. **驱动层 (Driver Layer)**
   - ✅ `InputController` - 鼠标/键盘控制
   - ✅ `WindowManager` - 窗口管理
   - ✅ `CoordinateMapper` - 坐标映射
   - ⚠️ `screenshot_tool.py` - 实现不完整

3. **决策层 (Agent Layer)**
   - ⏳ `host_planner.py` - 仅占位符
   - ⏳ `local_executor.py` - 待实现
   - ⏳ `llm_client.py` - 待实现

4. **知识层 (Knowledge Layer)**
   - ⏳ RAG 检索器 - 待实现

---

## 🔍 现有 Wrapper 问题分析

### 问题 1: 未使用 OxyGent FunctionHub 模式

**当前实现** (`vision_wrapper.py`, `driver_wrapper.py`):
```python
# ❌ 错误：直接定义函数，未使用 FunctionHub
def detect_ui_elements(image_path: str) -> str:
    ...
```

**应该使用**:
```python
# ✅ 正确：使用 FunctionHub 注册工具
from oxygent.oxy import FunctionHub
from pydantic import Field

catia_tools = FunctionHub(name="catia_tools")

@catia_tools.tool(description="...")
def detect_ui_elements(image_path: str = Field(...)) -> str:
    ...
```

### 问题 2: 路径处理硬编码且不稳定

**当前问题**:
- `vision_wrapper.py` 第13行：硬编码相对路径 `r"../../applications/catia_vla/perception/weights/best.pt"`
- `driver_wrapper.py` 第12行：`capture_full_screen` 调用方式错误
- 路径依赖运行位置，容易失败

**应该**:
- 使用 `os.path` 和 `__file__` 动态计算路径
- 从配置文件读取模型路径
- 支持环境变量配置

### 问题 3: 工具 Schema 定义不完整

**当前问题**:
- `get_vision_tool_schema()` 函数存在但未被 OxyGent 使用
- `driver_wrapper.py` 缺少 schema 定义
- 参数描述不够详细

**应该**:
- 使用 `@tool()` 装饰器的 `description` 参数
- 使用 `Field(description=...)` 定义参数
- 提供完整的工具描述

### 问题 4: 截图工具实现错误

**当前问题** (`screenshot_tool.py`):
```python
def capture_full_screen(save_path: str) -> None:
    screenshot = pyautogui.screenshot()
    screenshot.save('perception/figures/test.png')  # ❌ 硬编码路径
    screenshot.save(save_path)  # ❌ 保存两次
```

**应该**:
- 只保存到指定路径
- 返回保存的文件路径
- 支持临时文件生成

### 问题 5: 缺少错误处理和日志

**当前问题**:
- 异常处理过于简单（只返回 JSON 错误）
- 缺少日志记录
- 没有重试机制

### 问题 6: 未集成到 MAS 系统

**当前问题**:
- Wrapper 文件存在但未在主程序中注册
- 没有创建 Agent 使用这些工具
- 缺少完整的集成示例

---

## 🛠️ 修复方案

### 步骤 1: 重构 vision_wrapper.py

**需要修复**:
1. 使用 `FunctionHub` 注册工具
2. 修复路径处理（动态计算）
3. 完善参数定义和描述
4. 添加错误处理和日志

### 步骤 2: 重构 driver_wrapper.py

**需要修复**:
1. 使用 `FunctionHub` 注册工具
2. 修复 `screenshot_tool.py` 实现
3. 添加更多驱动工具（双击、拖拽、键盘输入等）
4. 完善错误处理

### 步骤 3: 修复 screenshot_tool.py

**需要修复**:
1. 正确实现截图功能
2. 返回文件路径
3. 支持临时文件

### 步骤 4: 创建主集成程序

**需要创建**:
1. `catia_vla_agent.py` - 主 Agent 定义
2. `main_integrated.py` - 集成示例
3. 配置文件支持

### 步骤 5: 编写测试

**需要创建**:
1. 单元测试（各工具函数）
2. 集成测试（完整工作流）
3. 端到端测试（实际 CATIA 操作）

---

## 📝 后续工作清单

### 优先级 P0 (必须完成)

- [ ] 重构 `vision_wrapper.py` 使用 FunctionHub
- [ ] 重构 `driver_wrapper.py` 使用 FunctionHub
- [ ] 修复 `screenshot_tool.py` 实现
- [ ] 创建主集成程序
- [ ] 编写基础测试

### 优先级 P1 (重要)

- [ ] 实现 HostAgent (宏观规划)
- [ ] 实现 LocalAgent (微观执行)
- [ ] 集成 LLM 客户端
- [ ] 添加配置管理

### 优先级 P2 (增强)

- [ ] 实现 RAG 知识检索
- [ ] 添加视觉反思闭环
- [ ] 完善错误重试机制
- [ ] 性能优化

---

## 🧪 测试策略

### 1. 单元测试

```python
# test_vision_wrapper.py
def test_detect_ui_elements():
    # 测试视觉检测功能
    pass

# test_driver_wrapper.py
def test_click_element():
    # 测试点击功能（mock）
    pass
```

### 2. 集成测试

```python
# test_integration.py
async def test_full_workflow():
    # 测试：截图 -> 检测 -> 点击
    pass
```

### 3. 端到端测试

```python
# test_e2e.py
async def test_catia_automation():
    # 实际 CATIA 环境测试
    # 需要 CATIA 运行
    pass
```

---

## 📚 参考文档

- [OxyGent 工具注册文档](../../docs/docs_zh/2_register_single_tool.md)
- [FunctionHub API](../../docs/development/api/function_tools/function_hub.md)
- [预设工具示例](../../oxygent/preset_tools/file_tools.py)


