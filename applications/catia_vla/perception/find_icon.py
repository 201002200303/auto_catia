import matplotlib.pyplot as plt
import matplotlib.patches as patches
from ultralytics import YOLO
from PIL import Image
import torch

def load_image(image_path):
    return Image.open(image_path).convert("RGB")

def crop_normalized_region(image, norm_coords):
    """根据归一化坐标裁剪图像"""
    w, h = image.size
    x1, y1, x2, y2 = [int(norm_coords[i] * (w if i % 2 == 0 else h)) for i in range(4)]
    cropped = image.crop((x1, y1, x2, y2))
    return cropped, (x1, y1)

def match_class_name(target_str):
    """从需求字符串中提取目标类名，如 '004放大' -> '004'"""
    for i in range(len(target_str)):
        if not target_str[i].isdigit():
            return target_str[:i]
    return target_str  # 全部数字

def detect_and_locate(image_path, region_norm, user_query, model_path):
    image = load_image(image_path)
    model = YOLO(model_path)

    # 截取归一化区域
    cropped, top_left = crop_normalized_region(image, region_norm)

    # 推理
    results = model(cropped)[0]

    # 直接匹配类名（例如 '004'）
    class_names = model.names
    name2id = {v: k for k, v in class_names.items()}
    target_id = name2id.get(user_query, None)

    if target_id is None:
        print(f"❌ 类名 '{user_query}' 不在模型类别中。")
        return

    # 查找匹配目标
    for box in results.boxes:
        if int(box.cls[0]) == target_id and float(box.conf[0]) > 0.1:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            x1_full = int(x1 + top_left[0])
            y1_full = int(y1 + top_left[1])
            x2_full = int(x2 + top_left[0])
            y2_full = int(y2 + top_left[1])
            print(f"✅ 找到目标 '{user_query}' 在全图中的像素位置：({x1_full}, {y1_full}) ~ ({x2_full}, {y2_full})")
            return (int((x1_full + x2_full) /2), int((y1_full + y2_full) /2))

    print(f"❌ 区域中未检测到目标 '{user_query}'。")
    return

# 示例调用
if __name__ == '__main__':
    image_path = 'figures/screenshot26.jpg'
    model_path = 'runs/detect/dataset3_yolo11s2/weights/best.pt'

    # 用户指定归一化区域坐标（左上和右下），例如 CATIA 框选区域
    region_norm = (0.75, 0.0926, 1.0, 0.6667)  # x1, y1, x2, y2，归一化值（0~1）

    # 用户需求字符串
    user_query = '028'

    cx, cy = detect_and_locate(image_path, region_norm, user_query, model_path)
    print(cx, cy)