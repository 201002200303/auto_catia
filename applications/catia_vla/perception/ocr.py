import os
import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, ImageFont, ImageDraw
import torch

from util.utils import check_ocr_box

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def draw_labeled_box(draw_ctx, bbox, tag, config):
    x1, y1, x2, y2 = bbox
    draw_ctx.rectangle([x1, y1, x2, y2], outline="red", width=config["thickness"])
    font_size = int(16 * config["text_scale"])
    try:
        font = ImageFont.truetype("arial.ttf", size=font_size)
    except:
        font = None
    draw_ctx.text((x2 + config["text_padding"], y2 - font_size), tag, fill="cyan", font=font)


def main(
    input_image_path="figures/screenshot8.jpg",
    query="居中",
    box_norm=[0.0, 0.0, 0.2, 1.0]
):
    output_dir = Path("result")
    output_dir.mkdir(exist_ok=True)

    print(f"📷 Loading image: {input_image_path}")
    full_image = Image.open(input_image_path).convert("RGB")
    W, H = full_image.size
    x1 = int(box_norm[0] * W)
    y1 = int(box_norm[1] * H)
    x2 = int(box_norm[2] * W)
    y2 = int(box_norm[3] * H)
    cropped_region = full_image.crop((x1, y1, x2, y2))

    print(f"🔍 OCR in region ({x1}, {y1}) - ({x2}, {y2})")
    ocr_bbox_rslt, _ = check_ocr_box(
        cropped_region,
        display_img=False,
        output_bb_format='xyxy',
        goal_filtering=None,
        easyocr_args={'paragraph': True, 'text_threshold': 0.6},
        use_paddleocr=True
    )
    text_list, ocr_bbox_list = ocr_bbox_rslt

    box_overlay_ratio = cropped_region.size[0] / 3200
    draw_bbox_config = {
        'text_scale': 0.8 * box_overlay_ratio,
        'text_thickness': max(int(2 * box_overlay_ratio), 1),
        'text_padding': max(int(3 * box_overlay_ratio), 1),
        'thickness': max(int(3 * box_overlay_ratio), 1),
    }

    parsed_info = []
    draw_image = full_image.copy()
    draw_ctx = ImageDraw.Draw(draw_image)

    matches = []
    is_digits_only = query.isdigit()

    for idx, (text, bbox) in enumerate(zip(text_list, ocr_bbox_list)):
        bx1, by1, bx2, by2 = [int(v) for v in bbox]
        global_box = [bx1 + x1, by1 + y1, bx2 + x1, by2 + y1]
        tag = f"ocr_box_{idx}"
        draw_labeled_box(draw_ctx, global_box, tag, draw_bbox_config)

        parsed_info.append({
            "id": tag,
            "text": text,
            "bbox": global_box
        })

        if (is_digits_only and query in text) or (not is_digits_only and text.strip() == query):
            matches.append((text, global_box))

    # 保存图像和 JSON（包含当前区域的全部识别结果）
    query_safe = query.replace("/", "_")
    draw_image.save(output_dir / f"ocr_bbox_{query_safe}.png")
    with open(output_dir / f"ocr_info_{query_safe}.json", "w", encoding="utf-8") as f:
        json.dump(parsed_info, f, indent=2, ensure_ascii=False)

    if not matches:
        print(f"❌ No match found for '{query}' in region ({x1},{y1})-({x2},{y2})")
        return None

    selected_text, selected_bbox = min(matches, key=lambda x: x[1][1])
    gx1, gy1, gx2, gy2 = selected_bbox
    cx = (gx1 + gx2) // 2
    cy = (gy1 + gy2) // 2

    print(f"✅ Found '{selected_text}' at global center ({cx}, {cy})")
    return cx, cy


if __name__ == "__main__":
    cx1, cy1 = main(
        input_image_path="figures/screenshot18.jpg",
        query="居中",
        box_norm=[0.0, 0.0, 0.2, 1]
    )
