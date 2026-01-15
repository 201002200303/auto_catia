"""
CATIA VLA Agent 主程序入口

展示如何使用 VisionService 的滑动窗口推理功能，并与驱动层集成。
"""

from perception import VisionService
from driver import WindowManager, CoordinateMapper, InputController
import cv2
import os
import pyautogui
import time


def example_vision_service_usage():
    """
    示例：VisionService 滑动窗口推理的使用方法
    """
    # 1. 初始化 VisionService（自动加载中文名称映射）
    model_path = 'perception/runs/detect/dataset3_yolo11s2/weights/best.pt'
    data_yaml_path = 'perception/dataset3/data.yaml'  # 用于加载中文名称
    vision_service = VisionService(
        model_path=model_path,
        data_yaml_path=data_yaml_path
    )
    
    # 2. 使用滑动窗口推理（推荐用于高分辨率屏幕）
    image_path = 'perception/figures/11.jpg'
    
    print("=" * 60)
    print("VisionService 滑动窗口推理示例")
    print("=" * 60)
    
    detections = vision_service.detect_full_screen_tiled(
        image_path=image_path,
        slice_size=640,          # YOLO 标准输入尺寸
        overlap_ratio=0.2,        # 20% 重叠，确保边界目标不遗漏
        conf_threshold=0.25,      # 置信度阈值
        iou_threshold=0.45        # NMS IoU 阈值
    )
    
    print(f"\n检测到 {len(detections)} 个目标:")
    for i, det in enumerate(detections, 1):
        x1, y1, x2, y2 = det['bbox']
        print(f"{i}. {det['label']}")
        print(f"   坐标: ({x1}, {y1}) -> ({x2}, {y2})")
        print(f"   置信度: {det['confidence']:.3f}")
        print()
    
    # 可视化检测结果（在原图上标注并保存）
    print("正在生成可视化结果...")
    vision_service.visualize_detections(
        image_path=image_path,
        detections=detections,
        output_dir='perception/result',
        conf_threshold=0.1
    )
    
    return detections


def example_integration_with_driver(detections):
    """
    示例：将 VisionService 的检测结果与驱动层集成
    
    展示如何将检测到的图标坐标用于自动化点击操作。
    """
    print("=" * 60)
    print("VisionService 与驱动层集成示例")
    print("=" * 60)
    
    # 1. 初始化窗口管理器
    window_manager = WindowManager(window_title_pattern="CATIA")
    
    try:
        # 2. 查找并激活 CATIA 窗口
        hwnd = window_manager.find_window()
        print(f"找到窗口: {window_manager.get_window_title()}")
        
        window_manager.activate_window()
        print("窗口已激活")
        
        # 3. 获取窗口矩形（用于坐标映射）
        window_rect = window_manager.get_window_rect()
        print(f"窗口坐标: {window_rect}")
        
        # 4. 初始化坐标映射器
        # 注意：这里假设截图尺寸与窗口尺寸一致
        # 实际使用时，需要传入截图的尺寸
        coordinate_mapper = CoordinateMapper(window_rect)
        
        # 5. 初始化输入控制器
        controller = InputController(action_delay=0.1, highlight_click=True)
        
        # 6. 遍历检测结果，执行点击操作
        print(f"\n准备点击 {len(detections)} 个检测到的目标...")
        
        for i, det in enumerate(detections, 1):
            # 获取检测框的中心坐标（图像坐标系）
            x1, y1, x2, y2 = det['bbox']
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # 假设截图尺寸（实际应该从截图获取）
            # 这里需要根据实际截图尺寸调整
            screenshot_width = 1920  # 示例值，实际应从截图获取
            screenshot_height = 1080  # 示例值，实际应从截图获取
            
            # 将图像坐标映射到屏幕坐标
            screen_x, screen_y = coordinate_mapper.map_to_screen(
                center_x, center_y,
                screenshot_width, screenshot_height
            )
            
            print(f"\n{i}. 点击目标: {det['label']}")
            print(f"   图像坐标: ({center_x:.0f}, {center_y:.0f})")
            print(f"   屏幕坐标: ({screen_x}, {screen_y})")
            
            # 执行点击（注释掉以避免实际点击）
            # controller.click(screen_x, screen_y)
            print("   [已跳过实际点击]")
        
    except RuntimeError as e:
        print(f"错误: {e}")
        print("提示: 请确保 CATIA 应用程序已启动")


def example_workflow():
    """
    完整工作流示例：截图 -> 检测 -> 点击
    """
    print("=" * 60)
    print("完整工作流示例")
    print("=" * 60)
    
    # 步骤1: 初始化服务
    model_path = 'perception/runs/detect/dataset6_yolo11s2/weights/best.pt'
    vision_service = VisionService(model_path=model_path)
    window_manager = WindowManager(window_title_pattern="CATIA")
    
    try:
        # 步骤2: 激活 CATIA 窗口
        window_manager.find_window()
        window_manager.activate_window()
        window_rect = window_manager.get_window_rect()
        # 给截图操作留出时间
        time.sleep(1)
        
        # 步骤3: 截图（
        screenshot = pyautogui.screenshot()
        screenshot.save('perception/figures/test.png')
        # 实际使用时，应该使用 pyautogui 或 win32api 截图
        image_path = 'perception/figures/test.png'
        
        # 步骤4: 运行检测
        detections = vision_service.detect_full_screen_tiled(
            image_path=image_path,
            slice_size=640,
            overlap_ratio=0.2,
            conf_threshold=0.25
        )
        
        print(f"检测到 {len(detections)} 个目标")
        
        # 步骤5: 坐标映射和点击（示例）
        if len(detections) > 0:
            # 获取图像尺寸
            img = cv2.imread(image_path)
            img_height, img_width = img.shape[:2]
            
            coordinate_mapper = CoordinateMapper(window_rect)
            controller = InputController(highlight_click=True)
            
            # 选择第一个检测结果作为示例
            det = detections[0]
            print(f"检测到的目标: {det}")
            print(f"检测到的目标的bbox: {det['bbox']}")
            print(f"检测到的目标的label: {det['label']}")
            print(f"检测到的目标的confidence: {det['confidence']}")
            x1, y1, x2, y2 = det['bbox']
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            screen_x, screen_y = coordinate_mapper.map_to_screen(
                center_x, center_y, img_width, img_height
            )
            
            # print(f"\n准备点击: {det['label']} at ({screen_x}, {screen_y})")
            print(f"不转换的坐标: ({center_x}, {center_y})")
            print(f"转换后的坐标: ({screen_x}, {screen_y})")

            #controller.click(screen_x, screen_y)  # 取消注释以执行实际点击
            # 点击原始坐标，转化为整数
            controller.click(int(center_x), int(center_y))
            # 点击转换后的坐标
            # controller.click(screen_x, screen_y)
            # 可视化检测结果
            vision_service.visualize_detections(
        image_path=image_path,
        detections=detections,
        output_dir='result',
        conf_threshold=0.1
    )
        
    except Exception as e:
        print(f"错误: {e}")


if __name__ == '__main__':
    print('CATIA VLA Agent Started...\n')
    
    # 示例1: 基本使用
    # detections = example_vision_service_usage()
    
    # 示例2: 与驱动层集成
    # example_integration_with_driver(detections)
    
    # 示例3: 完整工作流
    example_workflow()
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)
