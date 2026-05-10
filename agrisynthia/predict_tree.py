# -*- coding: utf-8 -*-
import glob
import logging
import sys
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from numpy import random as np_random
import openpyxl
import torch
from natsort import natsorted

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.append(str(BASE_DIR / "detection" / "yolo"))

from models.experimental import attempt_load  # noqa: E402
from utils.datasets import LoadImages  # noqa: E402
from utils.general import non_max_suppression, scale_coords  # noqa: E402
from utils.plots import plot_one_box  # noqa: E402
from utils.torch_utils import select_device  # noqa: E402

_model_cache = {}
_device = None
_lock = threading.RLock()


def get_device() -> torch.device:
    global _device
    with _lock:
        if _device is None:
            try:
                _device = select_device("")
                logger.info("Device seçildi: %s", _device)
            except Exception as e:
                logger.error("Device seçim hatası: %s", e)
                raise RuntimeError(f"GPU/CPU seçimi başarısız: {e}")
        return _device


def get_model(model_name: str) -> Any:
    with _lock:
        if model_name not in _model_cache:
            try:
                device = get_device()
                model_path = Path(model_name)

                if not model_path.exists():
                    logger.error("Model dosyası bulunamadı: %s", model_path)
                    raise FileNotFoundError(f"Model bulunamadı: {model_path}")

                logger.info("Model yükleniyor: %s", model_name)
                model = attempt_load(str(model_path), map_location=device)
                model.eval()

                if device.type != "cpu":
                    model.half()

                _model_cache[model_name] = model
                logger.info("Model başarıyla yüklendi: %s", model_name)

            except FileNotFoundError:
                raise
            except Exception as e:
                logger.error("Model yükleme hatası %s: %s", model_name, e)
                raise RuntimeError(f"Model yüklenemedi {model_name}: {e}")

        return _model_cache[model_name]


def predict(
    path_to_weights: str, path_to_source: str, return_boxes: bool = False
) -> Tuple[bytes, str, float] | Tuple[bytes, str, float, List[Dict[str, int]]]:
    unique_id = str(uuid.uuid4())

    try:
        model = get_model(path_to_weights)
        device = get_device()

        img_size = 640
        conf_thres = 0.1
        iou_thres = 0.45

        try:
            dataset = LoadImages(path_to_source, img_size=img_size)
        except Exception as e:
            logger.error("Görüntü yükleme hatası: %s: %s", path_to_source, e)
            raise ValueError(f"Görüntü yüklenemedi: {e}")

        total_detections = 0
        confidence_scores: List[float] = []
        bbox_centers: List[Dict[str, int]] = []

        for path, img, im0s, vid_cap in dataset:
            try:
                img = torch.from_numpy(img).to(device)
                img = img.half() if device.type != "cpu" else img.float()
                img /= 255.0

                if img.ndimension() == 3:
                    img = img.unsqueeze(0)

                with torch.no_grad():
                    pred = model(img)[0]

                pred = non_max_suppression(pred, conf_thres, iou_thres)

                for i, det in enumerate(pred):
                    im0 = im0s.copy()

                    if det:
                        det[:, :4] = scale_coords(
                            img.shape[2:], det[:, :4], im0.shape
                        ).round()
                        total_detections = len(det)

                        colors = [[np_random.randint(0, 255) for _ in range(3)]]

                        for *xyxy, conf, cls in reversed(det):
                            x1, y1, x2, y2 = [float(v) for v in xyxy]
                            cx = int(round((x1 + x2) / 2.0))
                            cy = int(round((y1 + y2) / 2.0))
                            bbox_centers.append({"x": cx, "y": cy})
                            confidence_scores.append(float(conf))
                            label = f"{conf:.2f}"
                            plot_one_box(
                                xyxy,
                                im0,
                                label=label,
                                color=colors[0],
                                line_thickness=2,
                            )

                    try:
                        output_dir = BASE_DIR / "static" / "detected" / unique_id
                        output_dir.mkdir(parents=True, exist_ok=True)

                        img_name = Path(path).name
                        output_path = output_dir / img_name

                        if not cv2.imwrite(str(output_path), im0):
                            logger.error("Görüntü yazma hatası: %s", output_path)
                            raise IOError(f"Görüntü kaydedilemedi: {output_path}")

                    except Exception as e:
                        logger.error("Çıktı dosyası yazma hatası: %s", e)
                        raise IOError(f"Sonuç görüntüsü kaydedilemedi: {e}")

            except Exception as e:
                logger.error("Algılama işlemi hatası: %s: %s", path, e)
                raise

        count_str = f"{total_detections:02d}"
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0.0
        )
        if return_boxes:
            return count_str.encode("utf-8"), unique_id, avg_confidence, bbox_centers
        return count_str.encode("utf-8"), unique_id, avg_confidence

    except (FileNotFoundError, RuntimeError, ValueError, IOError):
        raise
    except Exception as e:
        logger.error("Preddict genel hatası: %s", e)
        raise RuntimeError(f"Algılama işlemi başarısız: {e}")


def multi_predictor(
    path_to_weights: str, path_to_source: str, ekim_sirasi: str, hashing: str
) -> str:
    try:
        try:
            a_str, b_str = ekim_sirasi.split("-")
            a: int = int(a_str)
            b: int = int(b_str)
        except (ValueError, AttributeError) as e:
            logger.error("Ekim sırası parse hatası: %s: %s", ekim_sirasi, e)
            raise ValueError(f"Geçersiz ekim sırası formatı: {ekim_sirasi}")

        try:
            path_to_source_images = natsorted(glob.glob(f"{path_to_source}/*"))
            if not path_to_source_images:
                logger.error("Kaynak dizinde görüntü bulunamadı: %s", path_to_source)
                raise FileNotFoundError(f"Görüntü bulunamadı: {path_to_source}")
        except Exception as e:
            logger.error("Görüntü listesi oluşturma hatası: %s", e)
            raise

        model = get_model(path_to_weights)
        device = get_device()

        img_size = 640
        conf_thres = 0.1
        iou_thres = 0.45

        detection_counts = []

        try:
            output_dir = Path(path_to_source) / "detected"
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Çıktı dizini oluşturma hatası: %s", e)
            raise IOError(f"Dizin oluşturulamadı: {e}")

        for img_path in path_to_source_images:
            try:
                dataset = LoadImages(img_path, img_size=img_size)

                for path, img, im0s, vid_cap in dataset:
                    img = torch.from_numpy(img).to(device)
                    img = img.half() if device.type != "cpu" else img.float()
                    img /= 255.0

                    if img.ndimension() == 3:
                        img = img.unsqueeze(0)

                    with torch.no_grad():
                        pred = model(img)[0]

                    pred = non_max_suppression(pred, conf_thres, iou_thres)

                    total_detections = 0
                    for i, det in enumerate(pred):
                        im0 = im0s.copy()

                        if det:
                            det[:, :4] = scale_coords(
                                img.shape[2:], det[:, :4], im0.shape
                            ).round()
                            total_detections = len(det)

                            colors = [[np_random.randint(0, 255) for _ in range(3)]]

                            for *xyxy, conf, cls in reversed(det):
                                label = f"{conf:.2f}"
                                plot_one_box(
                                    xyxy,
                                    im0,
                                    label=label,
                                    color=colors[0],
                                    line_thickness=2,
                                )

                        img_name = Path(path).name
                        output_path = output_dir / img_name
                        if not cv2.imwrite(str(output_path), im0):
                            logger.error("Görüntü kaydetme hatası: %s", output_path)

                    detection_counts.append(total_detections)

            except Exception as e:
                logger.error("Görüntü işleme hatası %s: %s", img_path, e)
                detection_counts.append(0)

        try:
            excel_dir = Path(path_to_source) / "excel"
            excel_dir.mkdir(parents=True, exist_ok=True)

            expected_size = a * b
            actual_size = len(detection_counts)
            if expected_size != actual_size:
                logger.error(
                    f"Reshape boyut uyumsuzluğu: beklenen {expected_size} "
                    f"({a}x{b}), gerçek {actual_size}"
                )
                raise ValueError(
                    f"Ekim sırası ({a}x{b}={expected_size}) ile görüntü sayısı "
                    f"({actual_size}) uyuşmuyor. Lütfen doğru ekim sırası giriniz."
                )

            data = np.array(detection_counts).reshape(a, b)
            wb = openpyxl.Workbook()
            ws = wb.active
            if ws is None:
                raise IOError("Excel worksheet oluşturulamadı")
            for row in data:
                ws.append([int(x) for x in row])

            excel_path = excel_dir / "output.xlsx"
            wb.save(str(excel_path))
            logger.info("Excel dosyası oluşturuldu: %s", excel_path)

        except Exception as e:
            logger.error("Excel oluşturma hatası: %s", e)
            raise IOError(f"Excel dosyası oluşturulamadı: {e}")

        try:
            zip_path = BASE_DIR / "media" / f"{hashing}_result.zip"
            zip_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(
                str(zip_path), mode="w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.write(str(excel_dir / "output.xlsx"), "output.xlsx")
                for img in natsorted(output_dir.glob("*")):
                    archive.write(str(img), f"detected/{img.name}")

            logger.info("ZIP dosyası oluşturuldu: %s", zip_path)

        except Exception as e:
            logger.error("ZIP oluşturma hatası: %s", e)
            raise IOError(f"ZIP dosyası oluşturulamadı: {e}")

        return hashing

    except (FileNotFoundError, ValueError, IOError, RuntimeError):
        raise
    except Exception as e:
        logger.error("Multi predictor genel hatası: %s", e)
        raise RuntimeError(f"Çoklu algılama işlemi başarısız: {e}")


