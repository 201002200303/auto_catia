import os
import random
from pathlib import Path
from PIL import Image

# ================= 配置区域 =================
# 目标图标路径 (正样本)
target_dir = Path('figures/icons')
# 噪声图标路径 (负样本 - 这里的图标只会贴图，不会生成标签)
noise_dir = Path('figures/noise_icons')

output_dir = Path('dataset_with_noise')
images_dir = output_dir / 'images'
labels_dir = output_dir / 'labels'

canvas_color = (random.randint(180, 220), random.randint(180, 220), random.randint(180, 220))  # 随机灰度，防止过拟合
cols = 9
total_samples = 500

# 每张图中包含的数量
num_targets_per_img = 50  # 想要检测的图标数量
num_noise_per_img = 15    # 干扰图标数量

# ===========================================

# 创建目录
for split in ['train', 'val', 'test']:
    (images_dir / split).mkdir(parents=True, exist_ok=True)
    (labels_dir / split).mkdir(parents=True, exist_ok=True)

# 1. 读取目标图标 (只有这些会生成 class_id)
# 过滤非图片文件，并确保文件名开头是数字(根据你的习惯)
target_files = sorted([f for f in target_dir.glob("*.png")])
# 生成映射表: 'icon_name' -> id
# ⚠️ 注意: 只有目标图标才有 ID
target_labels = {f.stem: i for i, f in enumerate(target_files)} 

print(f"🎯 目标图标数量: {len(target_files)} (ID范围: 0-{len(target_files)-1})")

# 2. 读取噪声图标
noise_files = sorted([f for f in noise_dir.glob("*.png")])
print(f"👻 噪声图标数量: {len(noise_files)}")

def generate_column_indices(num_icons):
    # (保持原有的列分配逻辑不变)
    base = num_icons // cols
    extra = num_icons % cols
    col_counts = [base] * cols
    for i in random.sample(range(cols), extra):
        col_counts[i] += 1
    indices = []
    for col, count in enumerate(col_counts):
        indices.extend([col] * count)
    random.shuffle(indices)
    return indices

def create_composite_image(sample_id, split):
    # --- 核心修改 A: 混合正负样本 ---
    # 随机抽取目标
    current_targets = random.sample(target_files, min(len(target_files), num_targets_per_img))
    # 随机抽取噪声 (允许重复抽取以填满数量)
    if len(noise_files) > 0:
        current_noise = random.choices(noise_files, k=num_noise_per_img)
    else:
        current_noise = []
    
    # 合并列表
    # 我们需要标记哪些是目标，哪些是噪声。
    # 格式: (file_path, is_target)
    mixed_icons = [(p, True) for p in current_targets] + [(p, False) for p in current_noise]
    random.shuffle(mixed_icons) # 打乱顺序，让噪声混在目标里

    # --- 布局计算 (逻辑微调以适应 mixed_icons) ---
    column_indices = generate_column_indices(len(mixed_icons))
    column_data = [[] for _ in range(cols)]

    for (icon_path, is_target), col in zip(mixed_icons, column_indices):
        column_data[col].append((icon_path, is_target))

    # 计算列宽
    col_xs = []
    current_x = 0
    for col_items in column_data:
        if not col_items:
            max_w = 0
        else:
            max_w = max(Image.open(p[0]).size[0] for p in col_items)
        col_xs.append(current_x)
        current_x += max_w

    canvas_w = current_x
    if canvas_w == 0: canvas_w = 100 # 防止空图
    
    # 放置图标
    all_placements = []
    max_h = 0

    for col_idx, items in enumerate(column_data):
        x = col_xs[col_idx]
        y = random.randint(5, 15)
        for icon_path, is_target in items:
            icon = Image.open(icon_path).convert("RGBA")
            # 建议: 随机背景色增强鲁棒性
            # if random.random() > 0.5: icon = add_random_noise(icon) 
            
            w, h = icon.size
            # 记录放置信息，多存一个 is_target 标记
            all_placements.append({
                "img": icon, "x": x, "y": y, 
                "w": w, "h": h, 
                "name": icon_path.stem, 
                "is_target": is_target
            })
            y += h + random.randint(5, 20)
        max_h = max(max_h, y)

    if max_h == 0: max_h = 100
    
    # 创建画布
    # 建议: 随机微调背景色，模拟真实屏幕色差
    bg_r = 212 + random.randint(-10, 10)
    bg_g = 212 + random.randint(-10, 10)
    bg_b = 228 + random.randint(-10, 10)
    canvas = Image.new("RGB", (canvas_w, max_h), (bg_r, bg_g, bg_b))
    
    annotations = []

    # --- 核心修改 B: 只有 is_target=True 才写标签 ---
    for item in all_placements:
        # 1. 无论是否目标，都贴图 (这就是制造视觉噪声)
        canvas.paste(item["img"], (item["x"], item["y"]), item["img"])
        
        # 2. 只有目标才生成坐标
        if item["is_target"]:
            x_center = (item["x"] + item["w"] / 2) / canvas.width
            y_center = (item["y"] + item["h"] / 2) / canvas.height
            w_norm = item["w"] / canvas.width
            h_norm = item["h"] / canvas.height
            
            # 从目标字典里获取 ID
            class_id = target_labels[item["name"]]
            
            annotations.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

    # 保存
    img_name = f"{sample_id:04d}.jpg"
    label_name = f"{sample_id:04d}.txt"
    canvas.save(images_dir / split / img_name)
    with open(labels_dir / split / label_name, 'w') as f:
        f.write("\n".join(annotations))

# 划分比例 (保持不变)
train_ratio = 0.8
val_ratio = 0.1
test_ratio = 0.1

train_n = int(total_samples * train_ratio)
val_n = int(total_samples * val_ratio)

for i in range(total_samples):
    if i < train_n:
        split = "train"
    elif i < train_n + val_n:
        split = "val"
    else:
        split = "test"
    create_composite_image(i, split)
    if i % 50 == 0: print(f"Processing {i}/{total_samples}...")

print("✅ 包含噪声数据的混合数据集生成完毕！")
