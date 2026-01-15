import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def find_orange_bounding_box(image_path, pos, expansion_percent=0.1, visualize=True):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("无法加载图像，请检查路径是否正确")
    
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_orange = np.array([10, 100, 100])
    upper_orange = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower_orange, upper_orange)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    height, width = mask.shape
    if pos == 'right':
        x_start, x_end = int(width * 0.2), int(width * 0.9)
        y_start, y_end = int(height * 0.1), int(height * 0.9)
    elif pos == 'left':
        x_start, x_end = 0, int(width * 0.2)
        y_start, y_end = int(height * 0.1), int(height * 0.9)
    else:
        raise ValueError("pos应选择'left'或'right'")

    roi = mask[y_start:y_end, x_start:x_end]
    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        raise ValueError("在指定区域内没有检测到橙色区域")

    vis_img = img.copy()

    if pos == 'right':
        all_orange_pixels = np.vstack([cnt for cnt in contours])
        x, y, w, h = cv2.boundingRect(all_orange_pixels)
        expand_x = int(width * expansion_percent)
        expand_y = int(height * expansion_percent)
        x1 = max(x + x_start - expand_x, 0)
        y1 = max(y + y_start - expand_y, 0)
        x2 = min(x + x_start + w + expand_x, width)
        y2 = min(y + y_start + h + expand_y, height)
    elif pos == 'left':
        top_contour = min(contours, key=lambda cnt: cv2.boundingRect(cnt)[1])
        x, y, w, h = cv2.boundingRect(top_contour)
        x1 = x + x_start
        y1 = y + y_start
        x2 = x1 + w
        y2 = y1 + h

    # -------- 可视化部分 --------
    if visualize:
        for cnt in contours:
            cnt_shifted = cnt + [x_start, y_start]  # ROI坐标 → 原图
            cv2.drawContours(vis_img, [cnt_shifted], -1, (0, 255, 0), 2)  # 绿色轮廓

        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 0, 255), 2)  # 红色边框

        plt.figure(figsize=(10, 6))
        plt.imshow(cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB))
        plt.title("Detected Orange Region and Bounding Box")
        plt.axis("off")
        plt.show()

    return x1, y1, x2, y2


def visualize_orange_bounding_box(image_path, bbox):
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
    ax.text(x1, y1 - 15, f"Orange BBox: ({x1}, {y1}, {x2}, {y2})", 
           color='r', fontsize=12, bbox=dict(facecolor='white', alpha=0.7))
    
    plt.title("Orange Region Bounding Box with Expansion")
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    image_path = "figures/screenshot16.jpg"
    
    try:
        # 获取橙色区域的bounding box
        bbox = find_orange_bounding_box(image_path, expansion_percent=0.1, pos='left', visualize=True)
        print(f"橙色区域的Bounding Box坐标 (x1, y1, x2, y2): {bbox}")
        
        # 可视化
        visualize_orange_bounding_box(image_path, bbox)
    except Exception as e:
        print(f"发生错误: {e}")