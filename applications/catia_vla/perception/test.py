from ultralytics import YOLO

def test_model(
    model_path='runs/detect/dataset3_yolo11s2/weights/best.pt',
    data_yaml='dataset3/data.yaml',
    imgsz=640,
    device=0,
    cache=False
):
    # 加载模型
    model = YOLO(model_path)

    # 评估模型在测试集上的表现
    metrics = model.val(
        data=data_yaml,
        imgsz=imgsz,
        split='test',
        device=device
    )

    print("\n✅ 测试集评估结果：")
    print(f"mAP50:        {metrics.box.map50:.4f}")
    print(f"mAP50-95:     {metrics.box.map:.4f}")
    print(f"Precision:    {metrics.box.mp:.4f}")
    print(f"Recall:       {metrics.box.mr:.4f}")
    print(f"Number of classes: {metrics.box.nc}")


if __name__ == '__main__':
    test_model()