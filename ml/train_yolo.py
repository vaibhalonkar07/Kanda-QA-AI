"""Train / validate / export the onion segmentation model.

    pip install -r ../backend/requirements-ml.txt
    python train_yolo.py train --data dataset.yaml --epochs 100
    python train_yolo.py val   --weights runs/segment/onion/weights/best.pt --data dataset.yaml
    python train_yolo.py export --weights runs/segment/onion/weights/best.pt      # ONNX for edge devices

Then copy best.pt to backend/models/onion_seg.pt and set VISION_BACKEND=yolo.
"""
import argparse

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "val", "export"])
    ap.add_argument("--data", default="dataset.yaml")
    ap.add_argument("--weights", default="yolov8s-seg.pt")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args()
    model = YOLO(a.weights)
    if a.cmd == "train":
        model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, project="runs/segment", name="onion",
                    hsv_h=0.01, hsv_s=0.4, hsv_v=0.4, degrees=180, flipud=0.5, fliplr=0.5, mosaic=1.0)
    elif a.cmd == "val":
        m = model.val(data=a.data, imgsz=a.imgsz)
        print("mask mAP50:", m.seg.map50, "mask mAP50-95:", m.seg.map)
    else:
        print("Exported to", model.export(format="onnx", imgsz=a.imgsz))


if __name__ == "__main__":
    main()
