import cv2
import numpy as np

def match_icon_in_region(screenshot_path, query_path, search_region):
    """
    :param screenshot_path: 路径，Teamcenter 截图
    :param query_path: 路径，查询图标
    :param search_region: [(x1, y1), (x2, y2)]，归一化搜索区域
    :return: (x, y)，在原图中的中心像素坐标
    """
    # 读取图像
    screenshot = cv2.imread(screenshot_path)
    query = cv2.imread(query_path)
    if screenshot is None or query is None:
        raise FileNotFoundError("无法读取图像文件")

    h, w = screenshot.shape[:2]

    # 计算搜索区域的实际像素坐标
    (x1_norm, y1_norm), (x2_norm, y2_norm) = search_region
    x1, y1 = int(x1_norm * w), int(y1_norm * h)
    x2, y2 = int(x2_norm * w), int(y2_norm * h)

    roi = screenshot[y1:y2, x1:x2]

    # 初始化 SIFT
    sift = cv2.SIFT_create()

    # 特征提取
    kp1, des1 = sift.detectAndCompute(query, None)
    kp2, des2 = sift.detectAndCompute(roi, None)

    if des1 is None or des2 is None:
        print("未能检测到足够特征")
        return None

    # 使用 FLANN 匹配
    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)

    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)

    # Lowe's Ratio Test
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)

    if len(good_matches) < 4:
        print("匹配点过少")
        return None

    # 获取匹配点坐标
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches])

    # 单应矩阵估计
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

    if H is None:
        print("无法估计单应性")
        return None

    # 计算 query 图像在 roi 中的投影位置
    h_q, w_q = query.shape[:2]
    pts = np.float32([[0, 0], [0, h_q], [w_q, h_q], [w_q, 0]]).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(pts, H)

    # 求中心点
    center_x = np.mean(dst[:, 0, 0])
    center_y = np.mean(dst[:, 0, 1])

    # 映射回原图坐标
    global_x = int(center_x + x1)
    global_y = int(center_y + y1)

    return (global_x, global_y)

# 示例调用
if __name__ == "__main__":
    screenshot_path = "figures/screenshot27.jpg"
    query_path = "figures/query00.jpg"
    # search_region = [(0.3, 0.05), (0.4, 0.15)]  # 成功 (713, 118)
    search_region = [(0.28, 0.05), (0.42, 0.15)]  # 成功 (713, 118) 最大在268*108的框中可以保证特征匹配识别准确
    # search_region = [(0.27, 0.05), (0.43, 0.15)] # 失败 (700, 117)
    # search_region = [(0.3, 0.04), (0.4, 0.16)] # 勉强成功 (714, 122)
    # search_region = [(0.29, 0.04), (0.41, 0.16)] # 勉强成功 (714, 122)   


    result = match_icon_in_region(screenshot_path, query_path, search_region)
    if result:
        print("匹配图标中心点位置（全图坐标）:", result)
    else:
        print("未能成功匹配图标")
