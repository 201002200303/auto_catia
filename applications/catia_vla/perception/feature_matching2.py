import cv2
import numpy as np

def match_icon_with_sliding_sift(screenshot_path, query_path, search_region, grid_size=(3, 3)):
    """
    :param screenshot_path: 原图路径（Teamcenter）
    :param query_path: 查询图标路径
    :param search_region: [(x1, y1), (x2, y2)] 归一化搜索区域
    :param grid_size: 滑窗划分（列数, 行数），默认3x3
    :return: 最佳匹配点的图像全局坐标（x, y）
    """
    screenshot = cv2.imread(screenshot_path)
    query = cv2.imread(query_path)

    if screenshot is None or query is None:
        raise FileNotFoundError("无法读取图像文件")

    h_img, w_img = screenshot.shape[:2]

    # 计算搜索区域实际像素位置
    (x1_norm, y1_norm), (x2_norm, y2_norm) = search_region
    x1, y1 = int(x1_norm * w_img), int(y1_norm * h_img)
    x2, y2 = int(x2_norm * w_img), int(y2_norm * h_img)
    roi = screenshot[y1:y2, x1:x2]

    roi_h, roi_w = roi.shape[:2]
    cols, rows = grid_size
    step_x = roi_w // cols
    step_y = roi_h // rows

    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(query, None)
    if des1 is None:
        print("查询图标未提取到特征")
        return None

    # FLANN 参数
    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    best_score = 0
    best_center = None

    # 滑窗遍历
    for i in range(rows):
        for j in range(cols):
            sub_x1 = j * step_x
            sub_y1 = i * step_y
            sub_x2 = sub_x1 + step_x
            sub_y2 = sub_y1 + step_y

            window = roi[sub_y1:sub_y2, sub_x1:sub_x2]
            kp2, des2 = sift.detectAndCompute(window, None)
            if des2 is None or len(des2) < 2:
                continue

            matches = flann.knnMatch(des1, des2, k=2)

            # Lowe's ratio test
            good_matches = [m for m, n in matches if m.distance < 0.7 * n.distance]

            if len(good_matches) > best_score:
                best_score = len(good_matches)
                # 转换为原图坐标
                cx = sub_x1 + step_x // 2 + x1
                cy = sub_y1 + step_y // 2 + y1
                best_center = (cx, cy)

    if best_center:
        print(f"最佳匹配窗口特征点数: {best_score}")
    else:
        print("未能在滑窗中找到合适匹配")

    return best_center


if __name__ == "__main__":
    screenshot_path = "figures/screenshot27.jpg"
    query_path = "figures/query01.jpg"
    search_region = [(0.25, 0.05), (0.45, 0.15)]  # 可扩大一点范围
    grid_size = (4, 3)  # 可调滑窗密度（越大越精细，越慢）

    result = match_icon_with_sliding_sift(screenshot_path, query_path, search_region, grid_size)
    if result:
        print("匹配图标中心点位置（全图坐标）:", result)
    else:
        print("未能成功匹配图标")
