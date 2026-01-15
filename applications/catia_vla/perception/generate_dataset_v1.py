import os
import random
from pathlib import Path
from PIL import Image

# 参数配置
icons_dir = Path('figures/icons')
output_dir = Path('dataset4')
images_dir = output_dir / 'images'
labels_dir = output_dir / 'labels'

# 创建目录结构
for split in ['train', 'val', 'test']:
    (images_dir / split).mkdir(parents=True, exist_ok=True)
    (labels_dir / split).mkdir(parents=True, exist_ok=True)

canvas_color = (212, 212, 228)
cols = 9
total_samples = 500

# 划分比例
train_ratio = 0.6
val_ratio = 0.2
train_n = int(total_samples * train_ratio)
val_n = int(total_samples * val_ratio)

# 读取图标
icon_files = sorted([f for f in icons_dir.glob("*.png") if f.name[:3].isdigit()])
icon_labels = {f.stem: i for i, f in enumerate(icon_files)}  # '000' -> 0

def generate_column_indices(num_icons):
    base = num_icons // cols
    extra = num_icons % cols
    # 每列至少 base 个
    col_counts = [base] * cols
    # 随机将 extra 个图标均匀撒入不同列
    for i in random.sample(range(cols), extra):
        col_counts[i] += 1

    indices = []
    for col, count in enumerate(col_counts):
        indices.extend([col] * count)

    random.shuffle(indices)  # 打乱分布，避免规律性
    return indices

def create_composite_image(sample_id, split):
    selected_icons = random.sample(icon_files, 75)
    column_indices = generate_column_indices(len(selected_icons))
    column_icons = [[] for _ in range(cols)]

    for icon_path, col in zip(selected_icons, column_indices):
        column_icons[col].append(icon_path)

    col_xs = []
    current_x = 0

    for col in column_icons:
        max_w = max(Image.open(icon).size[0] for icon in col)
        col_xs.append(current_x)
        current_x += max_w  # 紧贴排列

    canvas_w = current_x
    canvas_h = 0
    all_placements = []
    max_h = 0

    for col_idx, icons in enumerate(column_icons):
        x = col_xs[col_idx]
        y = random.randint(5, 15)
        for icon_path in icons:
            icon = Image.open(icon_path).convert("RGBA")
            w, h = icon.size
            if w > 4 and h > 4:
                icon = icon.crop((2, 2, w - 2, h - 2))
            w, h = icon.size
            all_placements.append((icon, x, y, icon_path.stem, w, h))
            y += h + random.randint(5, 20)
        max_h = max(max_h, y)

    canvas = Image.new("RGB", (canvas_w, max_h), canvas_color)
    annotations = []

    for icon, x, y, label_str, w, h in all_placements:
        canvas.paste(icon, (x, y), icon)
        x_center = (x + w / 2) / canvas.width
        y_center = (y + h / 2) / canvas.height
        w_norm = w / canvas.width
        h_norm = h / canvas.height
        class_id = icon_labels[label_str]
        annotations.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

    img_name = f"{sample_id:04d}.jpg"
    label_name = f"{sample_id:04d}.txt"
    canvas.save(images_dir / split / img_name)
    with open(labels_dir / split / label_name, 'w') as f:
        f.write("\n".join(annotations))

# 生成图像并按比例分配
for i in range(total_samples):
    if i < train_n:
        split = "train"
    elif i < train_n + val_n:
        split = "val"
    else:
        split = "test"
    create_composite_image(i, split)

print("✅ dataset 数据集生成完成，使用比例变量动态划分 train/val/test。")
