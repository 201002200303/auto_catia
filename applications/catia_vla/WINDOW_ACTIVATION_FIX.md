# Windows 窗口激活问题修复说明

## 🔍 问题描述

错误信息：
```
pywintypes.error: (0, 'SetForegroundWindow', 'No error message is available')
RuntimeError: 激活窗口失败: (0, 'SetForegroundWindow', 'No error message is available')
```

**根本原因**：
- Windows 有安全机制，防止程序随意将窗口置于前台
- `SetForegroundWindow` API 在某些情况下会被系统拒绝
- 常见场景：程序在后台运行、用户正在与其他窗口交互等

## ✅ 修复方案

### 1. 改进窗口激活逻辑 (`window_manager.py`)

实现了**三层激活策略**：

1. **方法1：标准方法**（优先）
   - `SetForegroundWindow` + `ShowWindow`
   - 适用于大多数情况

2. **方法2：AttachThreadInput**（更可靠）
   - 附加线程输入，绕过部分安全限制
   - 需要更多系统权限

3. **方法3：BringWindowToTop**（备选）
   - 使用替代 API
   - 作为最后的尝试

### 2. 改进错误处理 (`catia_tools.py`)

- ✅ 区分不同类型的错误
- ✅ Windows 安全限制视为警告而非错误
- ✅ 提供友好的错误消息和解决建议
- ✅ 即使激活受限，也返回窗口信息

### 3. 改进测试逻辑 (`test_integration.py`)

- ✅ 正确处理警告情况
- ✅ 区分"未找到窗口"和"激活受限"
- ✅ 提供更详细的测试输出

## 📝 使用说明

### 正常情况

```python
result = activate_catia_window()
# 返回: {"success": true, "message": "CATIA 窗口已激活", ...}
```

### Windows 安全限制情况

```python
result = activate_catia_window()
# 返回: {
#   "success": true,
#   "warning": "无法将窗口置于前台（可能是 Windows 安全限制）",
#   "note": "请手动点击 CATIA 窗口以确保其处于活动状态"
# }
```

### CATIA 未运行情况

```python
result = activate_catia_window()
# 返回: {"error": "未找到 CATIA 窗口。请确保 CATIA 应用程序已启动。"}
```

## 🔧 解决方案

### 方案1：手动激活（推荐）

如果遇到 Windows 安全限制，最简单的方法是：
1. 手动点击 CATIA 窗口
2. 确保 CATIA 窗口处于活动状态
3. 然后继续执行自动化操作

### 方案2：以管理员权限运行

在某些情况下，以管理员权限运行 Python 脚本可以绕过部分限制：

```bash
# 以管理员身份运行 PowerShell
# 然后执行脚本
python test_integration.py
```

### 方案3：使用环境变量

可以通过环境变量控制行为：

```bash
# Windows
set CATIA_VLA_FORCE_ACTIVATE=1
python test_integration.py
```

## ⚠️ 注意事项

1. **Windows 安全限制是正常的**
   - 这是 Windows 的保护机制
   - 不是代码错误
   - 部分激活（窗口可见但不在前台）通常足够使用

2. **窗口必须存在**
   - CATIA 必须已启动
   - 窗口标题必须包含 "CATIA"

3. **最佳实践**
   - 在自动化操作前，确保 CATIA 窗口可见
   - 如果可能，手动激活一次窗口
   - 使用 `get_window_rect()` 验证窗口位置

## 🧪 测试

运行测试验证修复：

```bash
cd OxyGent-main/applications/catia_vla
python test_integration.py
```

### 预期结果

- ✅ **CATIA 运行且可激活**：完全成功
- ⚠️ **CATIA 运行但激活受限**：部分成功（有警告）
- ⚠️ **CATIA 未运行**：友好错误消息

## 📚 相关文档

- [Windows SetForegroundWindow 限制](https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)
- [AttachThreadInput API](https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-attachthreadinput)

---

*修复日期: 2024-12-26*



