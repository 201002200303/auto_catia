from ultralytics import YOLO

def main():
    # 加载模型
    model = YOLO('models/yolo11s.pt')
    
    # # 冻结前20层（Backbone + Neck的早期部分）
    # for param in model.model.model[:23].parameters():
    #     param.requires_grad = False

    # # # 解冻最后几层（C3k2 + Detect）
    # for param in model.model.model[23:].parameters():
    #     param.requires_grad = True

    # 打印确认哪些参数在训练
    # print("Trainable layers:")
    # for i, (m, name) in enumerate(zip(model.model.model, range(len(model.model.model)))):
    #     requires_grad = any(p.requires_grad for p in m.parameters())
    #     print(f"Layer {name:02d}: {m.__class__.__name__} - {'Trainable' if requires_grad else 'Frozen'}")

    # 启动训练
    model.train(
        data='dataset_with_noise/data.yaml',
        epochs=400,
        imgsz=640,
        batch=0.90,
        # lr0=1e-3,
        name='dataset_with_noise_yolo11s',
        device=0
    )

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
