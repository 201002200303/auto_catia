import cv2
import numpy as np

def match_icon_in_region_template(screenshot_path, query_path, search_region, threshold=0.85):
    """
    使用模板匹配，在指定区域内查找所有匹配图标，返回最下方一个的中心坐标。

    :param screenshot_path: 路径，Teamcenter 截图
    :param query_path: 路径，查询图标
    :param search_region: [(x1, y1), (x2, y2)]，归一化搜索区域
    :param threshold: 匹配得分阈值，默认0.85
    :return: (x, y)，最下方匹配图标的中心点像素坐标（全图坐标），若未匹配返回 None
    """
    # 读取图像
    screenshot = cv2.imread(screenshot_path)
    query = cv2.imread(query_path)
    if screenshot is None or query is None:
        raise FileNotFoundError("无法读取图像文件")

    h, w = screenshot.shape[:2]
    (x1_norm, y1_norm), (x2_norm, y2_norm) = search_region
    x1, y1 = int(x1_norm * w), int(y1_norm * h)
    x2, y2 = int(x2_norm * w), int(y2_norm * h)

    roi = screenshot[y1:y2, x1:x2]

    # 转灰度
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    query_gray = cv2.cvtColor(query, cv2.COLOR_BGR2GRAY)

    template_h, template_w = query_gray.shape[:2]

    # 模板匹配
    result = cv2.matchTemplate(roi_gray, query_gray, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    if len(locations[0]) == 0:
        print("没有匹配到任何图标")
        return None

    # 获取所有匹配中心点（在 ROI 中）
    points = list(zip(*locations[::-1]))  # (x, y)
    centers = [(x + template_w // 2, y + template_h // 2) for x, y in points]

    # 去除重复（非极大值抑制的简化版）
    deduped = []
    for pt in sorted(centers, key=lambda p: p[1]):  # 按 y 排序
        if all(abs(pt[0] - p[0]) > 10 or abs(pt[1] - p[1]) > 10 for p in deduped):
            deduped.append(pt)

    if not deduped:
        print("匹配重复过滤后为空")
        return None

    # 找出 y 最大的点（最下方）
    lowest = max(deduped, key=lambda p: p[1])

    # 映射回原图
    global_x = lowest[0] + x1
    global_y = lowest[1] + y1

    return (int(global_x), int(global_y))


if __name__ == "__main__":
    screenshot_path = "figures/screenshot28.jpg"
    query_path = "figures/query03.jpg"
    search_region = [(0.2, 0), (0.5, 0.45)]

    # screenshot_path = "figures/screenshot27.jpg"
    # query_path = "figures/query01.jpg"
    # search_region = [(0.28, 0.05), (0.42, 0.15)]

    result = match_icon_in_region_template(screenshot_path, query_path, search_region)
    if result:
        print("最下方旗子的中心坐标（全图）:", result)
    else:
        print("未能成功匹配旗子")
