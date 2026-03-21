# -*- coding: utf-8 -*-
from utils.add_nms import RegisterNMS
from utils.torch_utils import select_device
from utils.general import set_logging, check_img_size
from utils.activations import Hardswish, SiLU
from models.experimental import attempt_load, End2End
import models
from torch.utils.mobile_optimizer import optimize_for_mobile
import torch.nn as nn
import torch
import argparse
import sys
import time
import warnings

sys.path.append("./")


def export_torchscript(model, img, opt):
    try:
        print("\nStarting TorchScript export with torch %s..." % torch.__version__)
        f = opt.weights.replace(".pt", ".torchscript.pt")
        ts = torch.jit.trace(model, img, strict=False)
        ts.save(f)
        print(f"TorchScript export success, saved as {f}")
        return ts
    except Exception as e:
        print(f"TorchScript export failure: {e}")
        return None


def export_coreml(ts, img, opt):
    try:
        import coremltools as ct

        print(f"\nStarting CoreML export with coremltools {ct.__version__}...")
        ct_model = ct.convert(
            ts,
            inputs=[
                ct.ImageType("image", shape=img.shape, scale=1 / 255.0, bias=[0, 0, 0])
            ],
        )

        bits, mode = (
            (8, "kmeans_lut")
            if opt.int8
            else (16, "linear") if opt.fp16 else (32, None)
        )

        if bits < 32:
            if sys.platform.lower() == "darwin":
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=DeprecationWarning)
                    ct_model = (
                        ct.models.neural_network.quantization_utils.quantize_weights(
                            ct_model, bits, mode
                        )
                    )
            else:
                print("quantization only supported on macOS, skipping...")

        f = opt.weights.replace(".pt", ".mlmodel")
        ct_model.save(f)
        print(f"CoreML export success, saved as {f}")
    except Exception as e:
        print(f"CoreML export failure: {e}")


def export_torchscript_lite(model, img, opt):
    try:
        print("\nStarting TorchScript-Lite export with torch %s..." % torch.__version__)
        f = opt.weights.replace(".pt", ".torchscript.ptl")
        tsl = torch.jit.trace(model, img, strict=False)
        tsl = optimize_for_mobile(tsl)
        tsl._save_for_lite_interpreter(f)
        print("TorchScript-Lite export success, saved as %s" % f)
    except Exception as e:
        print("TorchScript-Lite export failure: %s" % e)


def export_onnx(model, img, opt, labels):
    try:
        import onnx

        print("\nStarting ONNX export with onnx %s..." % onnx.__version__)
        f = opt.weights.replace(".pt", ".onnx")
        model.eval()

        output_names = ["classes", "boxes"] if opt.include_nms else ["output"]
        dynamic_axes = None

        if opt.dynamic:
            dynamic_axes = {
                "images": {0: "batch", 2: "height", 3: "width"},
                "output": {0: "batch", 2: "y", 3: "x"},
            }

        if opt.dynamic_batch:
            opt.batch_size = "batch"
            dynamic_axes = {"images": {0: "batch"}}

            if opt.end2end and opt.max_wh is None:
                output_axes = {
                    "num_dets": {0: "batch"},
                    "det_boxes": {0: "batch"},
                    "det_scores": {0: "batch"},
                    "det_classes": {0: "batch"},
                }
            else:
                output_axes = {"output": {0: "batch"}}

            dynamic_axes.update(output_axes)

        if opt.grid:
            if opt.end2end:
                print(
                    "\nStarting export end2end onnx model for %s..."
                    % ("TensorRT" if opt.max_wh is None else "onnxruntime")
                )
                model = End2End(
                    model,
                    opt.topk_all,
                    opt.iou_thres,
                    opt.conf_thres,
                    opt.max_wh,
                    device,
                    len(labels),
                )

                if opt.end2end and opt.max_wh is None:
                    output_names = [
                        "num_dets",
                        "det_boxes",
                        "det_scores",
                        "det_classes",
                    ]
                    shapes = [
                        opt.batch_size,
                        1,
                        opt.batch_size,
                        opt.topk_all,
                        4,
                        opt.batch_size,
                        opt.topk_all,
                        opt.batch_size,
                        opt.topk_all,
                    ]
                else:
                    output_names = ["output"]
            else:
                model.model[-1].concat = True

        torch.onnx.export(
            model,
            img,
            f,
            verbose=False,
            opset_version=12,
            input_names=["images"],
            output_names=output_names,
            dynamic_axes=dynamic_axes,
        )

        onnx_model = onnx.load(f)
        onnx.checker.check_model(onnx_model)

        if opt.end2end and opt.max_wh is None:
            for i in onnx_model.graph.output:
                for j in i.type.tensor_type.shape.dim:
                    j.dim_param = str(shapes.pop(0))

        if opt.simplify:
            try:
                import onnxsim

                print("\nStarting to simplify ONNX...")
                onnx_model, check = onnxsim.simplify(onnx_model)
                if not check:
                    raise RuntimeError("ONNX simplification check failed")
            except Exception as e:
                print(f"Simplifier failure: {e}")

        onnx.save(onnx_model, f)
        print("ONNX export success, saved as %s" % f)

        if opt.include_nms:
            print("Registering NMS plugin for ONNX...")
            mo = RegisterNMS(f)
            mo.register_nms()
            mo.save(f)

    except Exception as e:
        print("ONNX export failure: %s" % e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, default="./yolor-csp-c.pt")
    parser.add_argument("--img-size", nargs="+", type=int, default=[640, 640])
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--dynamic", action="store_true")
    parser.add_argument("--dynamic-batch", action="store_true")
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--end2end", action="store_true")
    parser.add_argument("--max-wh", type=int, default=None)
    parser.add_argument("--topk-all", type=int, default=100)
    parser.add_argument("--iou-thres", type=float, default=0.45)
    parser.add_argument("--conf-thres", type=float, default=0.25)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--simplify", action="store_true")
    parser.add_argument("--include-nms", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--int8", action="store_true")
    opt = parser.parse_args()

    opt.img_size *= 2 if len(opt.img_size) == 1 else 1
    opt.dynamic = opt.dynamic and not opt.end2end
    opt.dynamic = False if opt.dynamic_batch else opt.dynamic

    print(opt)
    set_logging()
    t = time.time()

    try:
        device = select_device(opt.device)
        model = attempt_load(opt.weights, map_location=device)
        labels = model.names

        gs = int(max(model.stride))
        opt.img_size = [check_img_size(x, gs) for x in opt.img_size]

        img = torch.zeros(opt.batch_size, 3, *opt.img_size).to(device)

        for k, m in model.named_modules():
            m._non_persistent_buffers_set = set()
            if isinstance(m, models.common.Conv):
                if isinstance(m.act, nn.Hardswish):
                    m.act = Hardswish()
                elif isinstance(m.act, nn.SiLU):
                    m.act = SiLU()

        model.model[-1].export = not opt.grid
        y = model(img)

        if opt.include_nms:
            model.model[-1].include_nms = True
            y = None

        ts = export_torchscript(model, img, opt)

        if ts is not None:
            export_coreml(ts, img, opt)

        export_torchscript_lite(model, img, opt)
        export_onnx(model, img, opt, labels)

        print(
            "\nExport complete (%.2fs). Visualize with https://github.com/lutzroeder/netron."
            % (time.time() - t)
        )

    except Exception as e:
        print(f"Export failed: {e}")
        raise
