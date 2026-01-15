# CATIA VLA Agent 项目总结

> **版本**: v1.0.0 (Alpha) | **状态**: 核心模块已实现 | **测试状态**: ✅ 完整工作流已验证

---

## 📋 项目概述

基于视觉-语言-动作（VLA）架构的 CATIA 自动化建模智能体，通过 YOLO 视觉识别 + LLM 推理规划 + 底层驱动控制，实现全自动化 3D 建模操作。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    CATIA VLA Agent                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   感知层      │  │   决策层      │  │   驱动层      │  │
│  │ Perception   │→ │   Agent      │→ │   Driver     │  │
│  │              │  │              │  │              │  │
│  │ ✅ VisionService│ │ ⏳ HostAgent │ │ ✅ WindowMgr  │  │
│  │ ✅ 滑动窗口    │ │ ⏳ LocalAgent │ │ ✅ CoordMapper│  │
│  │ ✅ 中文标注    │ │              │ │ ✅ Controller │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         ↓                  ↓                  ↓          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           知识层 (Knowledge Layer)               │  │
│  │  ⏳ RAG + SOP 文档检索                           │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ 已实现功能

### 1. 感知层 (Perception Layer) - **已完成**

**核心类**: `VisionService`

#### 功能特性
- ✅ **滑动窗口推理** (`detect_full_screen_tiled`)
  - 支持高分辨率屏幕（1920x1080, 4K）
  - 自动切片处理，避免小目标丢失
  - 全局 NMS 去重，消除重叠检测
  
- ✅ **标准推理** (`detect`)
  - 单次推理，适用于小图像
  
- ✅ **可视化功能** (`visualize_detections`)
  - 自动标注检测框和标签
  - 支持中文名称显示
  - 生成检测图和位置分布图
  - 导出坐标文本文件

#### 技术实现
- YOLO11 目标检测
- OpenCV 图像处理
- 自动中文字体配置
- 从 `data.yaml` 加载中文名称映射

#### 输出格式
```python
[
    {
        'label': '002',              # 类别ID
        'bbox': [x1, y1, x2, y2],    # 边界框坐标
        'confidence': 0.95          # 置信度
    }
]
```

---

### 2. 驱动层 (Driver Layer) - **已完成**

#### 2.1 窗口管理 (`WindowManager`)
- ✅ 自动查找 CATIA 窗口
- ✅ 窗口激活和最大化
- ✅ DPI 感知支持（解决高分辨率坐标偏移）
- ✅ 获取窗口/客户区坐标

#### 2.2 坐标映射 (`CoordinateMapper`)
- ✅ 图像坐标 → 屏幕坐标转换
- ✅ 支持边界检查和坐标限制
- ✅ 处理窗口尺寸变化

#### 2.3 输入控制 (`InputController`)
- ✅ 鼠标操作：点击、双击、拖拽
- ✅ 键盘输入：按键、文本输入
- ✅ 操作延迟模拟（模拟人类操作）
- ✅ 调试模式（坐标高亮）

---

### 3. 决策层 (Agent Layer) - **待实现**

- ⏳ `HostAgent`: 宏观任务规划
- ⏳ `LocalAgent`: 微观操作执行
- ⏳ LLM 客户端集成

---

### 4. 知识层 (Knowledge Layer) - **待实现**

- ⏳ RAG 检索器
- ⏳ SOP 文档向量化
- ⏳ 向量数据库集成

---

## 📁 项目结构

```
CATIA_VLA_Project/
├── perception/              # ✅ 感知层（已完成）
│   ├── inference.py        # VisionService 核心类
│   ├── dataset3/            # YOLO 训练数据集（75类图标）
│   └── result/              # 检测结果输出
│
├── driver/                  # ✅ 驱动层（已完成）
│   ├── window_manager.py   # 窗口管理
│   ├── coordinate_mapper.py # 坐标映射
│   └── controller.py       # 输入控制
│
├── agent/                   # ⏳ 决策层（待实现）
│   ├── host_planner.py
│   └── local_executor.py
│
├── knowledge/               # ⏳ 知识层（待实现）
│   └── rag_retriever.py
│
├── config/                  # 配置文件
│   ├── settings.yaml
│   └── labels_map.json
│
├── main.py                  # ✅ 主入口（示例代码）
└── requirements.txt         # ✅ 依赖清单
```

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 基本使用

```python
from perception import VisionService
from driver import WindowManager, CoordinateMapper, InputController

# 初始化服务
vision_service = VisionService(
    model_path='perception/runs/detect/dataset3_yolo11s2/weights/best.pt',
    data_yaml_path='perception/dataset3/data.yaml'
)

# 执行检测
detections = vision_service.detect_full_screen_tiled(
    image_path='perception/figures/11.jpg',
    slice_size=640,
    overlap_ratio=0.2,
    conf_threshold=0.8
)

# 可视化结果
vision_service.visualize_detections(
    image_path='perception/figures/11.jpg',
    detections=detections,
    output_dir='perception/result'
)

# 与驱动层集成
window_manager = WindowManager("CATIA")
window_manager.find_window()
window_rect = window_manager.get_window_rect()

coordinate_mapper = CoordinateMapper(window_rect)
controller = InputController()

# 点击检测到的目标
for det in detections:
    x1, y1, x2, y2 = det['bbox']
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    
    screen_x, screen_y = coordinate_mapper.map_to_screen(
        center_x, center_y, img_width, img_height
    )
    controller.click(screen_x, screen_y)
```

---

## 📊 技术栈

| 层级 | 技术 | 状态 |
|------|------|------|
| 感知 | YOLO11, OpenCV, NumPy | ✅ |
| 驱动 | pywin32, win32api | ✅ |
| 决策 | OpenAI API, LLM | ⏳ |
| 知识 | ChromaDB, RAG | ⏳ |

---

## 🎯 核心特性

### ✅ 已实现
- [x] 高分辨率屏幕滑动窗口检测
- [x] 中文名称自动映射和显示
- [x] DPI 感知坐标映射
- [x] 窗口自动查找和激活
- [x] 鼠标/键盘底层控制
- [x] 检测结果可视化
- [x] **完整工作流集成测试** ✅

### ⏳ 待实现
- [ ] LLM 任务规划
- [ ] SOP 知识库检索
- [ ] 视觉反思闭环
- [ ] 错误重试机制

---

## 📝 输出示例

### 检测结果 (`icons_location.txt`)
```
002 平移视图 466,1312
046 标尺 807,1312
006 法线视图 606,1311
```

### 可视化输出
- `detection.jpg`: 带检测框和标签的可视化图
- `location.jpg`: 位置分布图
- `icons_location.txt`: 坐标文本文件

---

## 🔧 配置说明

### 模型配置
- **模型路径**: `perception/runs/detect/dataset3_yolo11s2/weights/best.pt`
- **类别数量**: 75 类 CATIA 图标
- **输入尺寸**: 640×640

### 检测参数
- `slice_size`: 640 (YOLO 标准输入)
- `overlap_ratio`: 0.2 (20% 重叠)
- `conf_threshold`: 0.8 (置信度阈值)
- `iou_threshold`: 0.45 (NMS IoU 阈值)

---

## ✅ 测试验证

### 完整工作流测试（2024）

**测试命令**: `python main.py`

**测试结果**:
```
✅ 检测到 29 个目标
✅ 坐标转换成功: (2453.0, 16.5) → (2465, 4)
✅ 点击操作执行成功
✅ 可视化结果已保存:
   - detection.jpg (检测框图)
   - location.jpg (位置分布图)
   - icons_location.txt (坐标文本)
```

**测试流程验证**:
1. ✅ 图像检测：滑动窗口推理成功识别29个目标
2. ✅ 坐标映射：图像坐标正确转换为屏幕坐标
3. ✅ 驱动控制：鼠标点击操作正常执行
4. ✅ 结果输出：可视化文件成功生成

**示例检测结果**:
- 目标: `{'label': '018', 'bbox': [2441, 5, 2465, 28], 'confidence': 0.93}`
- 中心坐标: `(2453.0, 16.5)`
- 屏幕坐标: `(2465, 4)`

---

## 📈 下一步计划

1. **决策层开发**: 实现 HostAgent 和 LocalAgent
2. **知识库构建**: 完成 RAG 检索和 SOP 文档索引
3. **闭环测试**: 实现完整的"看-想-做-反思"循环
4. **错误处理**: 完善异常捕获和重试机制

---

*最后更新: 2024 | 测试验证: ✅ 通过*


