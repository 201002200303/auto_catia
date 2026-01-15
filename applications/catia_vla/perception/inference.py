import matplotlib.pyplot as plt
import matplotlib.patches as patches
from ultralytics import YOLO
from PIL import Image
import torch
import os
import cv2
import numpy as np
import re
from typing import List, Dict, Tuple, Union, Optional

# 设置 matplotlib 中文字体
def setup_chinese_font():
    """
    配置 matplotlib 使用中文字体
    
    在 Windows 系统上尝试使用常见的中文字体，如果失败则使用默认字体。
    """
    try:
        # Windows 常见中文字体列表（按优先级排序）
        chinese_fonts = [
            'Microsoft YaHei',      # 微软雅黑
            'SimHei',                # 黑体
            'SimSun',                # 宋体
            'KaiTi',                 # 楷体
            'FangSong',              # 仿宋
        ]
        
        # 获取系统可用字体
        from matplotlib import font_manager
        available_fonts = [f.name for f in font_manager.fontManager.ttflist]
        
        # 查找第一个可用的中文字体
        for font_name in chinese_fonts:
            if font_name in available_fonts:
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
                return font_name
        
        # 如果没有找到，尝试直接设置（可能会失败）
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        return 'Microsoft YaHei'
        
    except Exception as e:
        print(f"警告: 设置中文字体失败: {e}，将使用默认字体")
        # 即使失败也设置 unicode_minus，避免负号显示问题
        plt.rcParams['axes.unicode_minus'] = False
        return None

# 初始化中文字体（在模块加载时执行）
_setup_font_result = setup_chinese_font()

def load_image(image_path):
    return Image.open(image_path).convert("RGB")


def load_chinese_names_from_yaml(yaml_path: str) -> Dict[str, str]:
    """
    从 data.yaml 文件加载类别ID到中文名称的映射
    
    Args:
        yaml_path: data.yaml 文件路径
    
    Returns:
        Dict[str, str]: 类别ID到中文名称的映射，例如 {'000': '飞行模式', '001': '全部适应'}
    """
    chinese_names = {}
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析 YAML 文件中的 names 部分
        # 格式: - '000' # 飞行模式
        pattern = r"-\s*['\"](\d+)['\"]\s*#\s*(.+)"
        matches = re.findall(pattern, content)
        
        for class_id, chinese_name in matches:
            chinese_name = chinese_name.strip()
            chinese_names[class_id] = chinese_name
        
    except FileNotFoundError:
        print(f"警告: 未找到文件 {yaml_path}，将不显示中文名称")
    except Exception as e:
        print(f"警告: 解析 {yaml_path} 时出错: {e}，将不显示中文名称")
    
    return chinese_names

def visualize_and_save_positions(image, results, class_names, conf_threshold=0.1):
    fig, ax = plt.subplots(1, figsize=(12, 8))
    ax.imshow(image)

    save_txt = 'result/icons_location.txt'
    save_img = 'result/location.jpg'
    save_detection_img = 'result/detection.jpg'
    os.makedirs(os.path.dirname(save_txt), exist_ok=True)

    icon_positions = []  # 保存 (类名, center_x, center_y) 方便后面画位置分布图

    with open(save_txt, 'w', encoding='utf-8') as f:
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                if box.conf < conf_threshold:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                # 写入 txt 文件（取整）
                f.write(f"{class_names[cls_id]} {int(center_x)},{int(center_y)}\n")

                # 保存到列表
                icon_positions.append((class_names[cls_id], int(center_x), int(center_y)))

                # 画检测框（缩小标注，避免遮挡）
                label = f"{class_names[cls_id]} {conf:.2f}"
                rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1,
                                         linewidth=1.5, edgecolor='red', facecolor='none')
                ax.add_patch(rect)
                ax.text(x1, y1 - 3, label, color='green', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none'))

    # 保存检测结果
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(save_detection_img)
    plt.close()

    # 绘制位置分布图（缩小标注）
    fig2, ax2 = plt.subplots(1, figsize=(12, 8))
    ax2.imshow(image)
    for cls_name, cx, cy in icon_positions:
        ax2.text(cx, cy, f"{cls_name}\n({cx},{cy})", color='green', fontsize=6,
                 ha='center', va='center', 
                 bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', boxstyle='round,pad=0.2'))
        ax2.plot(cx, cy, 'ro', markersize=2)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(save_img)
    plt.close()

class VisionService:
    """
    视觉推理服务类
    
    提供基于 YOLO 的目标检测功能，支持全屏滑动窗口推理，
    用于处理高分辨率屏幕上的小目标检测。
    """
    
    def __init__(self, model_path:str, device: str = None, data_yaml_path: Optional[str] = None):
        """
        初始化视觉服务
        
        Args:
            model_path: YOLO 模型权重文件路径 (.pt)
            device: 推理设备 ('cuda' 或 'cpu')，如果为 None 则自动选择
            data_yaml_path: data.yaml 文件路径，用于加载中文名称映射（可选）
        """
        self.model = YOLO(model_path)
        self.class_names = self.model.names
        
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        
        # 加载中文名称映射
        self.chinese_names = {}
        if data_yaml_path:
            self.chinese_names = load_chinese_names_from_yaml(data_yaml_path)
        else:
            # 尝试自动查找 data.yaml（在模型路径附近）
            model_dir = os.path.dirname(os.path.dirname(model_path))
            possible_paths = [
                os.path.join(model_dir, 'dataset6', 'data.yaml'),
                os.path.join(os.path.dirname(model_path), '..', 'dataset6', 'data.yaml'),
                'perception/dataset6/data.yaml',
                'dataset6/data.yaml'
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    self.chinese_names = load_chinese_names_from_yaml(path)
                    break
    
    def get_chinese_name(self, class_id: str) -> str:
        """
        获取类别ID对应的中文名称
        
        Args:
            class_id: 类别ID（如 '000', '001'）
        
        Returns:
            str: 中文名称，如果不存在则返回类别ID
        """
        return self.chinese_names.get(class_id, class_id)
    
    def detect_full_screen_tiled(
        self,
        image_path: str,
        slice_size: int = 640,
        overlap_ratio: float = 0.2,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> List[Dict[str, Union[str, List[int], float]]]:
        """
        使用滑动窗口方法对全屏图像进行目标检测
        
        算法流程：
        1. 将大图像分割成多个重叠的切片
        2. 对每个切片运行 YOLO 推理
        3. 将局部坐标转换为全局坐标
        4. 使用全局 NMS 去除重复检测框
        
        Args:
            image_path: 输入图像路径
            slice_size: 切片大小（默认 640，YOLO 标准输入尺寸）
            overlap_ratio: 切片重叠比例（0.0-1.0），用于确保边界目标不被遗漏
            conf_threshold: 置信度阈值
            iou_threshold: NMS 的 IoU 阈值
        
        Returns:
            List[Dict]: 检测结果列表，每个元素包含：
                - 'label': 类别名称 (str)
                - 'bbox': 边界框坐标 [x1, y1, x2, y2] (List[int])
                - 'confidence': 置信度 (float)
        """
        # 加载图像
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法加载图像: {image_path}")
        
        img_height, img_width = image.shape[:2]
        
        # 计算步长（stride）
        stride = int(slice_size * (1 - overlap_ratio))
        
        # 存储所有检测结果
        all_detections = []
        
        # 滑动窗口遍历
        y = 0
        while y < img_height:
            # 处理垂直边界：如果窗口超出图像底部，向后调整起始位置
            y_adjusted = y
            if y + slice_size > img_height:
                y_adjusted = max(0, img_height - slice_size)
            
            x = 0
            while x < img_width:
                # 处理水平边界：如果窗口超出图像右边界，向后调整起始位置
                x_adjusted = x
                if x + slice_size > img_width:
                    x_adjusted = max(0, img_width - slice_size)
                
                # 提取切片
                slice_img = image[y_adjusted:y_adjusted+slice_size, x_adjusted:x_adjusted+slice_size]
                
                # 运行 YOLO 推理
                results = self.model(slice_img, conf=conf_threshold, verbose=False)
                
                # 处理检测结果
                for result in results:
                    boxes = result.boxes
                    if boxes is None or len(boxes) == 0:
                        continue
                    
                    for box in boxes:
                        # 获取局部坐标（相对于切片）
                        local_x1, local_y1, local_x2, local_y2 = box.xyxy[0].cpu().numpy()
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        
                        # 转换为全局坐标（相对于原始图像）
                        global_x1 = int(local_x1 + x_adjusted)
                        global_y1 = int(local_y1 + y_adjusted)
                        global_x2 = int(local_x2 + x_adjusted)
                        global_y2 = int(local_y2 + y_adjusted)
                        
                        # 获取类别名称
                        label = self.class_names[cls_id]
                        
                        # 添加到检测列表
                        all_detections.append({
                            'label': label,
                            'bbox': [global_x1, global_y1, global_x2, global_y2],
                            'confidence': conf,
                            'class_id': cls_id  # 临时存储，用于 NMS
                        })
                
                # 移动到下一个水平位置
                x += stride
                
                # 如果已经到达右边界，退出水平循环
                if x >= img_width:
                    break
            
            # 移动到下一个垂直位置
            y += stride
            
            # 如果已经到达底部边界，退出垂直循环
            if y >= img_height:
                break
        
        # 如果没有检测结果，直接返回空列表
        if len(all_detections) == 0:
            return []
        
        # 全局 NMS 去重
        # 准备 NMS 输入：将 [x1, y1, x2, y2] 转换为 [x, y, w, h]
        boxes_nms = []
        confidences = []
        class_ids = []
        
        for det in all_detections:
            x1, y1, x2, y2 = det['bbox']
            w = x2 - x1
            h = y2 - y1
            boxes_nms.append([x1, y1, w, h])
            confidences.append(det['confidence'])
            class_ids.append(det['class_id'])
        
        # 转换为 numpy 数组
        boxes_nms = np.array(boxes_nms, dtype=np.float32)
        confidences = np.array(confidences, dtype=np.float32)
        class_ids = np.array(class_ids, dtype=np.int32)
        
        # 使用 OpenCV 的 NMSBoxes 进行非极大值抑制
        indices = cv2.dnn.NMSBoxes(
            boxes_nms,
            confidences,
            conf_threshold,
            iou_threshold
        )
        
        # 构建最终结果列表
        final_detections = []
        if len(indices) > 0:
            # indices 可能是 numpy 数组或列表
            if isinstance(indices, np.ndarray):
                indices = indices.flatten()
            
            for idx in indices:
                det = all_detections[idx]
                # 移除临时字段，只保留最终输出格式
                final_detections.append({
                    'label': det['label'],
                    'bbox': det['bbox'],  # 已经是整数列表 [x1, y1, x2, y2]
                    'confidence': det['confidence']
                })
        
        return final_detections
    
    def detect(self, image_path: str, conf_threshold: float = 0.25) -> List[Dict[str, Union[str, List[int], float]]]:
        """
        标准单次推理方法（不切片）
        
        适用于小图像或不需要高精度检测的场景。
        
        Args:
            image_path: 输入图像路径
            conf_threshold: 置信度阈值
        
        Returns:
            List[Dict]: 检测结果列表，格式同 detect_full_screen_tiled
        """
        results = self.model(image_path, conf=conf_threshold, verbose=False)
        
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue
            
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                detections.append({
                    'label': self.class_names[cls_id],
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf
                })
        
        return detections
    
    def visualize_detections(
        self,
        image_path: str,
        detections: List[Dict[str, Union[str, List[int], float]]],
        output_dir: str = 'result',
        conf_threshold: float = 0.1
    ) -> None:
        """
        可视化检测结果并在原图上标注检测框和标签
        
        功能类似 visualize_and_save_positions，但接受 detect_full_screen_tiled 的返回格式。
        
        Args:
            image_path: 输入图像路径
            detections: detect_full_screen_tiled 返回的检测结果列表
            output_dir: 输出目录（默认 'result'）
            conf_threshold: 置信度阈值（用于过滤低置信度检测）
        """
        # 加载图像
        image = load_image(image_path)
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        save_txt = os.path.join(output_dir, 'icons_location.txt')
        save_img = os.path.join(output_dir, 'location.jpg')
        save_detection_img = os.path.join(output_dir, 'detection.jpg')
        
        # 创建检测结果可视化图
        fig, ax = plt.subplots(1, figsize=(12, 8))
        ax.imshow(image)
        
        icon_positions = []  # 保存 (类名, center_x, center_y)
        
        # 写入文本文件并绘制检测框
        with open(save_txt, 'w', encoding='utf-8') as f:
            for det in detections:
                # 过滤低置信度检测
                if det['confidence'] < conf_threshold:
                    continue
                
                x1, y1, x2, y2 = det['bbox']
                label = det['label']
                conf = det['confidence']
                
                # 计算中心点
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                # 获取中文名称
                chinese_name = self.get_chinese_name(label)
                
                # 写入 txt 文件（格式：类别ID 中文名称 坐标）
                if chinese_name != label:
                    f.write(f"{label} {chinese_name} {int(center_x)},{int(center_y)}\n")
                else:
                    f.write(f"{label} {int(center_x)},{int(center_y)}\n")
                
                # 保存到列表
                icon_positions.append((label, int(center_x), int(center_y)))
                
                # 绘制检测框（减小线宽，避免遮挡）
                rect = patches.Rectangle(
                    (x1, y1), x2 - x1, y2 - y1,
                    linewidth=1.5, edgecolor='red', facecolor='none'
                )
                ax.add_patch(rect)
                
                # 绘制标签（缩小字体和标签框，避免遮挡）
                label_text = f"{label} {conf:.2f}"
                ax.text(x1, y1 - 3, label_text, color='green', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none'))
        
        # 保存检测结果图
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(save_detection_img, dpi=150, bbox_inches='tight')
        plt.close()
        
        # 绘制位置分布图
        fig2, ax2 = plt.subplots(1, figsize=(12, 8))
        ax2.imshow(image)
        
        for cls_name, cx, cy in icon_positions:
            # 获取中文名称用于显示
            chinese_name = self.get_chinese_name(cls_name)
            if chinese_name != cls_name:
                display_text = f"{cls_name}\n{chinese_name}\n({cx},{cy})"
            else:
                display_text = f"{cls_name}\n({cx},{cy})"
            
            ax2.text(cx, cy, display_text, color='green', fontsize=6,
                    ha='center', va='center',
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', boxstyle='round,pad=0.2'))
            ax2.plot(cx, cy, 'ro', markersize=2)
        
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(save_img, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"可视化结果已保存到:")
        print(f"  - 检测框图: {save_detection_img}")
        print(f"  - 位置分布图: {save_img}")
        print(f"  - 坐标文本: {save_txt}")


if __name__ == '__main__':
    # ========== 使用示例：滑动窗口推理（推荐用于高分辨率屏幕） ==========
    model_path = 'runs/detect/dataset6_yolo11s2/weights/best.pt'
    image_path = 'figures/image.png'
    data_yaml_path = 'dataset6/data.yaml'  # data.yaml 路径，用于加载中文名称
    
    # 初始化 VisionService（会自动加载中文名称映射）
    vision_service = VisionService(
        model_path=model_path,
        data_yaml_path=data_yaml_path
    )
    
    # 方法1: 使用滑动窗口推理（适用于高分辨率图像，如 1920x1080 或 4K）
    print("使用滑动窗口推理...")
    detections = vision_service.detect_full_screen_tiled(
        image_path=image_path,
        slice_size=640,          # 切片大小（YOLO 标准输入）
        overlap_ratio=0.2,        # 重叠比例（20% 重叠，确保边界目标不遗漏）
        conf_threshold=0.8,      # 置信度阈值
        iou_threshold=0.45        # NMS IoU 阈值
    )
    
    print(f"检测到 {len(detections)} 个目标:")
    for det in detections:
        print(f"  - {det['label']}: bbox={det['bbox']}, confidence={det['confidence']:.3f}")
    
    # ========== 可视化检测结果 ==========
    print("\n正在生成可视化结果...")
    vision_service.visualize_detections(
        image_path=image_path,
        detections=detections,
        output_dir='result',
        conf_threshold=0.1
    )
    
    # 方法2: 标准单次推理（适用于小图像）
    print("\n使用标准推理...")
    detections_standard = vision_service.detect(
        image_path=image_path,
        conf_threshold=0.25
    )
    print(f"检测到 {len(detections_standard)} 个目标")
    
    # ========== 可视化标准推理结果（使用原有函数） ==========
    # 注意：visualize_and_save_positions 需要 ultralytics 的 results 对象
    # 如果需要可视化标准推理结果，可以使用以下方式：
    # image = load_image(image_path)
    # results = vision_service.model(image)
    # visualize_and_save_positions(image, results, vision_service.class_names, conf_threshold=0.1)
