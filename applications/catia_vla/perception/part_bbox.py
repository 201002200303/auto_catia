import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def find_part_bounding_box(image_path, expansion_percent=0.05):
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("无法加载图像，请检查路径是否正确")
    
    # 转换为LAB颜色空间
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # 对亮度通道使用自适应阈值
    thresh = cv2.adaptiveThreshold(l, 255, 
                                  cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 51, 10)
    
    # 形态学操作增强边缘
    kernel = np.ones((3,3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # 定义搜索区域（横向20%-90%，纵向10%-90%）
    height, width = thresh.shape
    x_start = int(width * 0.2)
    x_end = int(width * 0.9)
    y_start = int(height * 0.1)
    y_end = int(height * 0.9)
    
    # 创建ROI区域
    roi = thresh[y_start:y_end, x_start:x_end]
    
    # 查找轮廓
    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        raise ValueError("在指定区域内没有检测到零件")
    
    # 找到最大的轮廓
    largest_contour = max(contours, key=cv2.contourArea)
    
    # 获取bounding box坐标（相对于ROI）
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    # 计算扩展量（5%的box尺寸）
    expand_x = int(w * expansion_percent)
    expand_y = int(h * expansion_percent)
    
    # 转换为原图坐标并扩展
    x1 = max(x + x_start - expand_x, 0)  # 确保不超出图像左边界
    y1 = max(y + y_start - expand_y, 0)  # 确保不超出图像上边界
    x2 = min(x + x_start + w + expand_x, width)  # 确保不超出图像右边界
    y2 = min(y + y_start + h + expand_y, height)  # 确保不超出图像下边界
    
    return x1, y1, x2, y2

def visualize_bounding_box(image_path, bbox):
    # 读取图像
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # 创建图形
    fig, ax = plt.subplots(1, figsize=(10, 10))
    ax.imshow(img)
    
    # 绘制原始搜索区域边界（浅灰色）
    height, width = img.shape[:2]
    search_area = plt.Rectangle((width*0.2, height*0.1), 
                               width*0.7, height*0.8,
                               linewidth=1, edgecolor='gray', 
                               facecolor='gray', alpha=0.2)
    ax.add_patch(search_area)
    
    # 绘制扩展后的bounding box（红色虚线）
    x1, y1, x2, y2 = bbox
    rect = Rectangle((x1, y1), x2 - x1, y2 - y1, 
                    linewidth=2, edgecolor='r', 
                    linestyle='--', facecolor='none')
    ax.add_patch(rect)
    
    # 添加文本说明
    ax.text(x1, y1 - 15, f"Expanded BBox: ({x1}, {y1}, {x2}, {y2})", 
           color='r', fontsize=12, bbox=dict(facecolor='white', alpha=0.7))
    
    plt.title("Bounding Box with 5% Expansion")
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    image_path = "figures/screenshot16.jpg"
    
    try:
        # 获取带扩展的bounding box
        bbox = find_part_bounding_box(image_path, expansion_percent=0.05)
        print(f"扩展后的Bounding Box坐标 (x1, y1, x2, y2): {bbox}")
        
        # 可视化
        visualize_bounding_box(image_path, bbox)
    except Exception as e:
        print(f"发生错误: {e}")