import cv2
import numpy as np
from sklearn.cluster import DBSCAN

def match_lowest_icon_in_region(screenshot_path, query_path, search_region):
    """
    :param screenshot_path: 路径，Teamcenter 截图
    :param query_path: 路径，旗子图标
    :param search_region: [(x1, y1), (x2, y2)]，归一化搜索区域
    :return: (x, y)，在原图中的最下方旗子的中心像素坐标
    """
    screenshot = cv2.imread(screenshot_path)
    query = cv2.imread(query_path)
    if screenshot is None or query is None:
        raise FileNotFoundError("无法读取图像文件")

    h, w = screenshot.shape[:2]

    # 像素坐标
    (x1_norm, y1_norm), (x2_norm, y2_norm) = search_region
    x1, y1 = int(x1_norm * w), int(y1_norm * h)
    x2, y2 = int(x2_norm * w), int(y2_norm * h)
    roi = screenshot[y1:y2, x1:x2]

    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(query, None)
    kp2, des2 = sift.detectAndCompute(roi, None)

    if des1 is None or des2 is None:
        print("未能检测到足够特征")
        return None

    # FLANN 匹配
    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=100)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    matches = flann.knnMatch(des1, des2, k=2)
    good_matches = [m for m, n in matches if m.distance < 0.7 * n.distance]

    if len(good_matches) < 4:
        print("匹配点过少")
        return None

    # 被匹配到的 query 中心在 roi 中的位置
    matched_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches])

    # 聚类匹配点（假设每个图标聚成一个簇）
    if len(matched_pts) < 4:
        print("有效匹配点过少，跳过聚类")
        return None

    # 用 DBSCAN 进行聚类
    clustering = DBSCAN(eps=20, min_samples=3).fit(matched_pts)
    labels = clustering.labels_

    all_centers = []

    for label in set(labels):
        if label == -1:
            continue  # -1 是噪声点

        cluster_indices = [i for i, lbl in enumerate(labels) if lbl == label]
        cluster_matches = [good_matches[i] for i in cluster_indices]

        src_pts = np.float32([kp1[m.queryIdx].pt for m in cluster_matches])
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in cluster_matches])

        if len(src_pts) < 4:
            continue

        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            continue

        h_q, w_q = query.shape[:2]
        pts = np.float32([[0, 0], [0, h_q], [w_q, h_q], [w_q, 0]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(pts, H)

        center_x = np.mean(dst[:, 0, 0])
        center_y = np.mean(dst[:, 0, 1])
        all_centers.append((center_x, center_y))

    if not all_centers:
        print("未能聚类出匹配图标")
        return None

    # 选 y 最大的，即最下方的
    lowest_center = max(all_centers, key=lambda p: p[1])

    # 映射回原图
    global_x = int(lowest_center[0] + x1)
    global_y = int(lowest_center[1] + y1)

    return (global_x, global_y)


if __name__ == "__main__":
    screenshot_path = "figures/screenshot28.jpg"
    query_path = "figures/query02.jpg"
    search_region = [(0.35, 0.2), (0.38, 0.26)]  # 调整为能匹配多个旗子的位置

    result = match_lowest_icon_in_region(screenshot_path, query_path, search_region)
    if result:
        print("最下方旗子的中心坐标（全图）:", result)
    else:
        print("未能成功匹配旗子")