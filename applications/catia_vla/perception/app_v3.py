import os
import json
import base64
from pathlib import Path
from typing import Optional, List, Tuple

import torch
import io
import matplotlib.pyplot as plt
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from transformers import CLIPProcessor, CLIPModel
from util.utils import check_ocr_box, get_yolo_model, get_caption_model_processor, get_som_labeled_img


# ─── Global Config ─────────────────────────────────────
YOLO_MODEL_PATH = '../OmniParserV2/icon_detect/model.pt'
CLIP_MODEL_DIR = './clip-vit-base-patch32'
CAPTION_MODEL_PROCESSOR = None
DEVICE = torch.device('cuda')

# ─── Model Loaders ─────────────────────────────────────
yolo_model = get_yolo_model(model_path=YOLO_MODEL_PATH)


# ─── Core Functions ────────────────────────────────────
@torch.inference_mode()
def process_image_with_yolo_and_ocr(
    image_input: Image.Image,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    use_paddleocr: bool = True,
    imgsz: int = 640
) -> Tuple[Image.Image, List[dict]]:
    box_overlay_ratio = image_input.size[0] / 3200
    draw_bbox_config = {
        'text_scale': 0.8 * box_overlay_ratio,
        'text_thickness': max(int(2 * box_overlay_ratio), 1),
        'text_padding': max(int(3 * box_overlay_ratio), 1),
        'thickness': max(int(3 * box_overlay_ratio), 1),
    }

    ocr_bbox_rslt, _ = check_ocr_box(
        image_input,
        display_img=False,
        output_bb_format='xyxy',
        goal_filtering=None,
        easyocr_args={'paragraph': False, 'text_threshold': 0.9},
        use_paddleocr=use_paddleocr
    )
    text, ocr_bbox = ocr_bbox_rslt

    encoded_img, _, parsed_info = get_som_labeled_img(
        image_input,
        yolo_model,
        BOX_TRESHOLD=box_threshold,
        output_coord_in_ratio=True,
        ocr_bbox=ocr_bbox,
        draw_bbox_config=draw_bbox_config,
        caption_model_processor=CAPTION_MODEL_PROCESSOR,
        ocr_text=text,
        iou_threshold=iou_threshold,
        imgsz=imgsz,
    )

    labeled_image = Image.open(io.BytesIO(base64.b64decode(encoded_img)))
    return labeled_image, parsed_info


def preprocess_icon(image: Image.Image, output_size: int = 64) -> Image.Image:
    image = image.convert("RGB")
    w, h = image.size
    max_side = max(w, h)
    padding = (
        (max_side - w) // 2,
        (max_side - h) // 2,
        (max_side - w + 1) // 2,
        (max_side - h + 1) // 2,
    )
    image = ImageOps.expand(image, padding, fill=(255, 255, 255))
    
    image = image.resize((output_size, output_size), resample=Image.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.05)    
    image = image.filter(ImageFilter.UnsharpMask(radius=0.5, percent=100, threshold=3))
    
    return image


def compute_clip_similarity(gt_icon_path: Path, parsed_info: List[dict], image_input: Image.Image, top_k: int = 5):
    W, H = image_input.size

    model = CLIPModel.from_pretrained(CLIP_MODEL_DIR).eval().to(DEVICE)
    processor = CLIPProcessor.from_pretrained(CLIP_MODEL_DIR)

    gt_img = preprocess_icon(Image.open(gt_icon_path))
    gt_inputs = processor(images=[gt_img], return_tensors="pt", padding=True).to(DEVICE)
    with torch.no_grad():
        gt_feat = model.get_image_features(**gt_inputs)
        gt_feat = gt_feat / gt_feat.norm(p=2, dim=-1, keepdim=True)

    results = []
    for entry in parsed_info:
        if entry["type"] != "icon":
            continue
        x1, y1, x2, y2 = entry["bbox"]
        left, top = int(x1 * W), int(y1 * H)
        right, bottom = int(x2 * W), int(y2 * H)
        crop = preprocess_icon(image_input.crop((left, top, right, bottom)))

        inputs = processor(images=[crop], return_tensors="pt", padding=True).to(DEVICE)
        with torch.no_grad():
            feat = model.get_image_features(**inputs)
            feat = feat / feat.norm(p=2, dim=-1, keepdim=True)

        sim = torch.cosine_similarity(gt_feat, feat).item()
        results.append({
            "bbox": entry["bbox"],
            "sim": sim,
            "center": [(x1 + x2) / 2, (y1 + y2) / 2],
            "pixel_bbox": [left, top, right, bottom],
            "image": crop
        })

    results.sort(key=lambda x: x["sim"], reverse=True)

    print("Top matches by similarity:")
    for r in results[:top_k]:
        print(f"sim={r['sim']:.4f}, center=({r['center'][0]:.3f}, {r['center'][1]:.3f}), pixel_bbox={r['pixel_bbox']}")

    fig, axs = plt.subplots(1, top_k, figsize=(3 * top_k, 3))
    for i in range(top_k):
        axs[i].imshow(results[i]['image'])
        axs[i].axis('off')
        axs[i].set_title(f"sim={results[i]['sim']:.3f}\n{results[i]['pixel_bbox']}")
    plt.tight_layout()
    plt.show()


# ─── Main Execution ────────────────────────────────────
def main():
    input_image_path = "figures/screenshot24.jpg"
    gt_icon_path = Path("dataset/BackView​.bmp")
    output_dir = Path("result")
    output_dir.mkdir(exist_ok=True)

    print(f"Loading image: {input_image_path}")
    image_input = Image.open(input_image_path).convert("RGB")

    print("Running YOLO + OCR processing...")
    labeled_img, parsed_info = process_image_with_yolo_and_ocr(image_input)

    labeled_img.save(output_dir / "result_labeled.png")
    with open(output_dir / "result_info.json", "w", encoding="utf-8") as f:
        json.dump(parsed_info, f, indent=2, ensure_ascii=False)
    
    parsed_info = json.load(open("result/result_info.json", encoding="utf-8"))
    
    # print("Running CLIP similarity matching...")
    # compute_clip_similarity(gt_icon_path, parsed_info, image_input)


if __name__ == "__main__":
    main()
