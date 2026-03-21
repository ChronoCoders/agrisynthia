# -*- coding: utf-8 -*-
import argparse
import time
from pathlib import Path
import cv2
import torch
import torch.backends.cudnn as cudnn
from numpy import random
from models.experimental import attempt_load
from utils.datasets import LoadStreams, LoadImages
from utils.general import (
    check_img_size,
    check_imshow,
    non_max_suppression,
    apply_classifier,
    scale_coords,
    xyxy2xywh,
    strip_optimizer,
    set_logging,
)
from utils.plots import plot_one_box
from utils.torch_utils import (
    select_device,
    load_classifier,
    time_synchronized,
    TracedModel,
)
from osgeo import gdal
import numpy as np

total_last: list[int] = []


def read_geotiff(filename):
    try:
        ds = gdal.Open(filename)
        if ds is None:
            raise ValueError(f"GeoTIFF açılamadı: {filename}")
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray()
        return arr, ds
    except Exception as e:
        print(f"GeoTIFF okuma hatası: {e}")
        return None, None


def write_geotiff(filename, arr, in_ds):
    try:
        if arr.dtype == np.float32:
            arr_type = gdal.GDT_Float32
        else:
            arr_type = gdal.GDT_Int32

        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(filename, arr.shape[1], arr.shape[0], 1, arr_type)
        out_ds.SetProjection(in_ds.GetProjection())
        out_ds.SetGeoTransform(in_ds.GetGeoTransform())
        band = out_ds.GetRasterBand(1)
        band.WriteArray(arr)
        band.FlushCache()
        band.ComputeStatistics(False)
        return True
    except Exception as e:
        print(f"GeoTIFF yazma hatası: {e}")
        return False


def count(founded_classes, im0, total_last):
    try:
        model_values = []
        aligns = im0.shape
        align_bottom = aligns[0]
        color_blue = (255, 0, 0)
        thickness = 2

        total_last.append(*founded_classes.values())

        for i, (k, v) in enumerate(founded_classes.items()):
            b = f"{k}={sum(total_last)}"
            model_values.append(v)
            align_bottom = align_bottom - 35

            cv2.putText(
                im0,
                str(b),
                (0, 170),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                color_blue,
                thickness,
                cv2.LINE_AA,
            )

        print(int(*total_last))
    except Exception as e:
        print(f"Sayım hatası: {e}")


def total(founded_classes, im0, total_last):
    try:
        total_last.append(*founded_classes.values())
    except Exception as e:
        print(f"Toplam hesaplama hatası: {e}")


def detect(save_img=False):
    source = opt.source
    weights = opt.weights
    view_img = opt.view_img
    save_txt = opt.save_txt
    imgsz = opt.img_size
    trace = not opt.no_trace

    save_img = not opt.nosave and not source.endswith(".txt")
    webcam = (
        source.isnumeric()
        or source.endswith(".txt")
        or source.lower().startswith(("rtsp://", "rtmp://", "http://", "https://"))
    )

    save_dir = Path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok)
    (save_dir / "labels" if save_txt else save_dir).mkdir(parents=False, exist_ok=True)

    set_logging()
    device = select_device(opt.device)
    half = False

    try:
        model = attempt_load(weights, map_location=device)
        stride = int(model.stride.max())
        imgsz = check_img_size(imgsz, s=stride)

        if trace:
            model = TracedModel(model, device, opt.img_size)

        if half:
            model.half()

        classify = False
        if classify:
            modelc = load_classifier(name="resnet101", n=2)
            modelc.load_state_dict(
                torch.load("weights/resnet101.pt", map_location=device)["model"]
            ).to(device).eval()

        vid_path, vid_writer = None, None
        if webcam:
            view_img = check_imshow()
            cudnn.benchmark = True
            dataset = LoadStreams(source, img_size=imgsz, stride=stride)
        else:
            dataset = LoadImages(source, img_size=imgsz, stride=stride)

        names = model.module.names if hasattr(model, "module") else model.names
        colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

        if device.type != "cpu":
            model(
                torch.zeros(1, 3, imgsz, imgsz)
                .to(device)
                .type_as(next(model.parameters()))
            )

        old_img_w = old_img_h = imgsz
        old_img_b = 1

        time.time()

        for path, img, im0s, vid_cap in dataset:
            img = torch.from_numpy(img).to(device)
            img = img.half() if half else img.float()
            img /= 255.0

            if img.ndimension() == 3:
                img = img.unsqueeze(0)

            if device.type != "cpu" and (
                old_img_b != img.shape[0]
                or old_img_h != img.shape[2]
                or old_img_w != img.shape[3]
            ):
                old_img_b = img.shape[0]
                old_img_h = img.shape[2]
                old_img_w = img.shape[3]
                for i in range(3):
                    model(img, augment=opt.augment)[0]

            time_synchronized()
            pred = model(img, augment=opt.augment)[0]
            time_synchronized()

            pred = non_max_suppression(
                pred,
                opt.conf_thres,
                opt.iou_thres,
                classes=opt.classes,
                agnostic=opt.agnostic_nms,
            )
            time_synchronized()

            if classify:
                pred = apply_classifier(pred, modelc, img, im0s)

            for i, det in enumerate(pred):
                if webcam:
                    p, s, im0, frame = (
                        path[i],
                        "%g: " % i,
                        im0s[i].copy(),
                        dataset.count,
                    )
                else:
                    p, s, im0, frame = path, "", im0s, getattr(dataset, "frame", 0)

                p = Path(p)
                save_path = str(save_dir / p.name)
                txt_path = str(save_dir / "labels" / p.stem) + (
                    "" if dataset.mode == "image" else f"_{frame}"
                )
                gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]

                if det:
                    det[:, :4] = scale_coords(
                        img.shape[2:], det[:, :4], im0.shape
                    ).round()

                    founded_classes = {}

                    for c in det[:, -1].unique():
                        n = (det[:, -1] == c).sum()
                        class_index = int(c)
                        founded_classes[names[class_index]] = int(n)
                        s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "

                    count(
                        founded_classes=founded_classes, im0=im0, total_last=total_last
                    )
                    total(founded_classes, im0, total_last)

                    for *xyxy, conf, cls in reversed(det):
                        if save_txt:
                            xywh = (
                                (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn)
                                .view(-1)
                                .tolist()
                            )
                            line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)
                            with open(txt_path + ".txt", "a") as f:
                                f.write(("%g " * len(line)).rstrip() % line + "\n")

                        if save_img or view_img:
                            label = f"{names[int(cls)]} {conf:.2f}"
                            plot_one_box(
                                xyxy,
                                im0,
                                label=label,
                                color=colors[int(cls)],
                                line_thickness=1,
                            )

                if view_img:
                    cv2.imshow(str(p), im0)
                    cv2.waitKey(1)

                if save_img:
                    if dataset.mode == "image":
                        nlcd16_arr, nlcd16_ds = read_geotiff(source)
                        if nlcd16_ds is not None:
                            write_geotiff("output.tif", im0, nlcd16_ds)
                        cv2.imwrite(save_path, im0)
                    else:
                        if vid_path != save_path:
                            vid_path = save_path
                            if isinstance(vid_writer, cv2.VideoWriter):
                                vid_writer.release()
                            if vid_cap:
                                fps = vid_cap.get(cv2.CAP_PROP_FPS)
                                w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            else:
                                fps, w, h = 30, im0.shape[1], im0.shape[0]
                                save_path += ".mp4"
                            vid_writer = cv2.VideoWriter(
                                save_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)
                            )
                        vid_writer.write(im0)

    except Exception as e:
        print(f"Algılama hatası: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", nargs="+", type=str, default="yolov7.pt")
    parser.add_argument("--source", type=str, default="inference/images")
    parser.add_argument("--img-size", type=int, default=640)
    parser.add_argument("--conf-thres", type=float, default=0.25)
    parser.add_argument("--iou-thres", type=float, default=0.45)
    parser.add_argument("--device", default="")
    parser.add_argument("--view-img", action="store_true")
    parser.add_argument("--save-txt", action="store_true")
    parser.add_argument("--save-conf", action="store_true")
    parser.add_argument("--nosave", action="store_true")
    parser.add_argument("--classes", nargs="+", type=int)
    parser.add_argument("--agnostic-nms", action="store_true")
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--project", default="runs/detect")
    parser.add_argument("--name", default="exp")
    parser.add_argument("--exist-ok", action="store_true")
    parser.add_argument("--no-trace", action="store_true")
    opt = parser.parse_args()

    with torch.no_grad():
        if opt.update:
            for opt.weights in ["yolov7.pt"]:
                detect()
                strip_optimizer(opt.weights)
        else:
            detect()
