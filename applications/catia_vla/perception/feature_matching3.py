import cv2
import numpy as np

def match_icon_template_multiscale(screenshot_path, query_path, search_region, scales=[1.0, 0.9, 1.1, 0.8, 1.2]):
    """
    :param screenshot_path: 原图路径（Teamcenter）
    :param query_path: 查询图标路径
    :param search_region: [(x1, y1), (x2, y2)] 归一化坐标
    :param scales: 缩放比列表，用于模板多尺度匹配
    :return: (x, y)，图标中心点在原图中的像素坐标
    """
    screenshot = cv2.imread(screenshot_path)
    template = cv2.imread(query_path)
    if screenshot is None or template is None:
        raise FileNotFoundError("图像读取失败")

    h_img, w_img = screenshot.shape[:2]
    (x1_norm, y1_norm), (x2_norm, y2_norm) = search_region
    x1, y1 = int(x1_norm * w_img), int(y1_norm * h_img)
    x2, y2 = int(x2_norm * w_img), int(y2_norm * h_img)
    roi = screenshot[y1:y2, x1:x2]

    best_val = -1
    best_loc = None
    best_scale = 1.0
    best_w, best_h = 0, 0

    for scale in scales:
        resized_template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h_temp, w_temp = resized_template.shape[:2]

        if roi.shape[0] < h_temp or roi.shape[1] < w_temp:
            continue  # 模板太大，跳过

        res = cv2.matchTemplate(roi, resized_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_scale = scale
            best_w, best_h = w_temp, h_temp

    if best_loc is None:
        print("模板匹配失败")
        return None

    top_left = best_loc
    center_x = top_left[0] + best_w // 2 + x1
    center_y = top_left[1] + best_h // 2 + y1

    print(f"最佳匹配分数: {best_val:.3f}，缩放: {best_scale}")
    return (center_x, center_y)


if __name__ == "__main__":
    screenshot_path = "figures/screenshot27.jpg"
    query_path = "figures/query01.jpg"
    search_region = [(0.28, 0.05), (0.42, 0.15)]

    result = match_icon_template_multiscale(screenshot_path, query_path, search_region)
    if result:
        print("匹配图标中心点位置（全图坐标）:", result)
    else:
        print("未能成功匹配图标")
