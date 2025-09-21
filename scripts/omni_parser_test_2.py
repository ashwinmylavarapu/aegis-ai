#!/usr/bin/env python3
"""
OmniParser v2 on macOS (MPS) or CPU with YOLOv8 + Florence-2 and optional OCR.

This build hardens Florence captioning on M1:
  • Only passes minimal non-None inputs to model.generate()
  • Keeps integer tensors as integer; casts only floating tensors
  • Falls back to CPU if MPS generate() hits a runtime edge
  • OCR via Apple Vision (Swift CLI) or Tesseract (no Paddle)

Outputs:
  - outputs/annotated.png  (class | ["ocr text"] | caption)
  - outputs/results.json
"""

# ------------------------ Stability: set caps BEFORE imports -----------------
import os as _os
_os.environ.setdefault("OMP_NUM_THREADS", "1")
_os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
_os.environ.setdefault("MKL_NUM_THREADS", "1")
_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
_os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# ----------------------------- Standard imports ------------------------------
import sys
import json
import shutil
import argparse
import gc
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import torch
torch.set_float32_matmul_precision("high")
from huggingface_hub import snapshot_download, hf_hub_download
from PIL import Image, ImageDraw, ImageFont
import yaml

from ultralytics import YOLO
from transformers import AutoProcessor, AutoModelForCausalLM

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
HF_OMNIPARSER_REPO = "microsoft/OmniParser-v2.0"

OMNI_DETECT_FILES = [
    "icon_detect/train_args.yaml",
    "icon_detect/model.pt",
    "icon_detect/model.yaml",
]

OMNI_CAPTION_FILES = [
    "icon_caption/config.json",
    "icon_caption/generation_config.json",
    "icon_caption/model.safetensors",
]

# Smaller Florence model to conserve memory
FLORENCE_REPO = "microsoft/Florence-2-base-ft"

CONF_THRES = 0.25
IOU_THRES = 0.45
MAX_DETS = 200

OCR_LANG = "en"
MIN_OCR_IOU = 0.15

# -----------------------------------------------------------------------------
# Swift Apple Vision OCR source (compiled on first use)
# -----------------------------------------------------------------------------
SWIFT_OCR_SOURCE = r"""
import Foundation
import Vision
import ImageIO
import CoreGraphics

func loadCGImage(url: URL) -> CGImage? {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
    return CGImageSourceCreateImageAtIndex(src, 0, nil)
}

@main
struct App {
    static func main() {
        guard CommandLine.arguments.count >= 2 else {
            fputs("usage: mac_ocr <image-path>\n", stderr); exit(2)
        }
        let url = URL(fileURLWithPath: CommandLine.arguments[1])
        guard let cgImage = loadCGImage(url: url) else {
            fputs("bad image\n", stderr); exit(1)
        }

        let width = cgImage.width
        let height = cgImage.height
        var items: [[String: Any]] = []

        let request = VNRecognizeTextRequest { request, error in
            if let error = error {
                fputs("vision error: \(error)\n", stderr)
                return
            }
            guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
            for o in observations {
                guard let top = o.topCandidates(1).first else { continue }
                let bb = o.boundingBox
                let x1 = Int((bb.minX * CGFloat(width)).rounded())
                let y1 = Int(((1 - bb.maxY) * CGFloat(height)).rounded())
                let x2 = Int((bb.maxX * CGFloat(width)).rounded())
                let y2 = Int(((1 - bb.minY) * CGFloat(height)).rounded())
                let poly = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                items.append([
                    "poly": poly,
                    "bbox": [x1,y1,x2,y2],
                    "text": top.string,
                    "score": Double(top.confidence)
                ])
            }
        }
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        if #available(macOS 13.0, *) {
            request.revision = VNRecognizeTextRequestRevision3
        }

        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        do { try handler.perform([request]) } catch {
            fputs("vision error: \(error)\n", stderr); exit(1)
        }

        if let data = try? JSONSerialization.data(withJSONObject: items, options: []),
           let s = String(data: data, encoding: .utf8) {
            print(s)
        }
    }
}
"""

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def ensure_omniparser_weights(weights_dir: Path):
    weights_dir.mkdir(parents=True, exist_ok=True)
    for rel in OMNI_DETECT_FILES + OMNI_CAPTION_FILES:
        (weights_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        hf_hub_download(
            repo_id=HF_OMNIPARSER_REPO,
            filename=rel,
            local_dir=weights_dir,
        )
    src = weights_dir / "icon_caption"
    dst = weights_dir / "icon_caption_florence"
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))


def ensure_florence_local(florence_root: Path):
    if florence_root.exists():
        return
    snapshot_download(
        repo_id=FLORENCE_REPO,
        local_dir=florence_root,
        ignore_patterns=["*.md", "*.txt", "*.png", "*.jpg", "*.jpeg", "README*"],
    )


def load_yolo(weights_dir: Path):
    model_path = weights_dir / "icon_detect" / "model.pt"
    if not model_path.exists():
        raise FileNotFoundError(f"Missing YOLO weights at: {model_path}")
    return YOLO(str(model_path))


def class_names_from_yaml(weights_dir: Path) -> Dict[int, str]:
    yaml_path = weights_dir / "icon_detect" / "model.yaml"
    if not yaml_path.exists():
        return {}
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    names = data.get("names", {})
    if isinstance(names, dict):
        return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, list):
        return {i: str(n) for i, n in enumerate(names)}
    return {}


def install_flash_attn_stub():
    if "flash_attn" in sys.modules:
        return
    import types
    from importlib.machinery import ModuleSpec
    stub = types.ModuleType("flash_attn")
    def _missing(*args, **kwargs):
        raise ImportError("flash_attn is not available on this platform; using eager attention instead.")
    stub.__getattr__ = lambda name: _missing
    stub.__spec__ = ModuleSpec("flash_attn", loader=None)
    sys.modules["flash_attn"] = stub


def load_florence(florence_local_dir: Path, device: torch.device):
    install_flash_attn_stub()
    try:
        import timm  # noqa: F401
        import einops  # noqa: F401
    except ImportError as e:
        raise RuntimeError(f"Missing dependency: please 'pip install timm einops'. Original error: {e}")

    dtype = torch.float32 if device.type != "cuda" else torch.float16
    processor = AutoProcessor.from_pretrained(str(florence_local_dir), trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(florence_local_dir),
        trust_remote_code=True,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        attn_implementation="eager",
    )
    model.to(device)
    model.eval()
    return processor, model


def run_detection(yolo_model, image_path: Path) -> List[Dict[str, Any]]:
    res = yolo_model.predict(
        source=str(image_path),
        conf=CONF_THRES,
        iou=IOU_THRES,
        max_det=MAX_DETS,
        device="mps" if torch.backends.mps.is_available() else "cpu",
        imgsz=960,
        verbose=False,
    )
    out = []
    if res and res[0].boxes is not None:
        for b in res[0].boxes:
            out.append({
                "xyxy": [float(x) for x in b.xyxy[0].cpu().numpy().tolist()],
                "conf": float(b.conf[0].cpu()),
                "cls": int(b.cls[0].cpu()),
            })
    return out


def crop_boxes(pil_img: Image.Image, boxes):
    crops = []
    W, H = pil_img.size
    for i, b in enumerate(boxes):
        x1, y1, x2, y2 = map(int, b["xyxy"])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        if x2 > x1 and y2 > y1:
            crops.append((i, pil_img.crop((x1, y1, x2, y2))))
    return crops


# ------------------------ Hardened Florence captioning -----------------------
@torch.inference_mode()
def florence_caption(processor, model, pil_img: Image.Image, device: torch.device, task: str = "<CAPTION>"):
    """
    Minimal, dtype-safe, None-safe call into Florence generate().
    Falls back to CPU if MPS path raises.
    """
    try:
        tokens = processor(text=task, images=pil_img, return_tensors="pt")

        # Keep only non-None keys
        tokens = {k: v for k, v in tokens.items() if v is not None}

        # Move & cast properly: float tensors -> model dtype, ints stay ints
        for k, v in list(tokens.items()):
            if hasattr(v, "to"):
                if v.is_floating_point():
                    tokens[k] = v.to(device=device, dtype=model.dtype)
                else:
                    tokens[k] = v.to(device=device)

        # Ensure essential fields + dtypes
        if "input_ids" in tokens:
            tokens["input_ids"] = tokens["input_ids"].to(torch.long)
        if "pixel_values" in tokens:
            tokens["pixel_values"] = tokens["pixel_values"].to(device=device, dtype=model.dtype)
        if "attention_mask" not in tokens and "input_ids" in tokens:
            tokens["attention_mask"] = torch.ones_like(tokens["input_ids"])

        # Pass only the minimal keys Florence expects
        gen = model.generate(
            input_ids=tokens.get("input_ids"),
            attention_mask=tokens.get("attention_mask"),
            pixel_values=tokens.get("pixel_values"),
            max_new_tokens=32,
            do_sample=False,
            num_beams=1,
        )
        out = processor.batch_decode(gen, skip_special_tokens=True)[0]
        return out.replace(task, "").strip()

    except Exception as e:
        # Fallback: try once on CPU (common MPS workaround)
        try:
            cpu = torch.device("cpu")
            model_cpu = model.to(cpu)
            tokens = processor(text=task, images=pil_img, return_tensors="pt")
            tokens = {k: v for k, v in tokens.items() if v is not None}
            for k, v in list(tokens.items()):
                if hasattr(v, "to"):
                    if v.is_floating_point():
                        tokens[k] = v.to(device=cpu, dtype=model_cpu.dtype)
                    else:
                        tokens[k] = v.to(device=cpu)
            if "input_ids" in tokens:
                tokens["input_ids"] = tokens["input_ids"].to(torch.long)
            if "attention_mask" not in tokens and "input_ids" in tokens:
                tokens["attention_mask"] = torch.ones_like(tokens["input_ids"])

            gen = model_cpu.generate(
                input_ids=tokens.get("input_ids"),
                attention_mask=tokens.get("attention_mask"),
                pixel_values=tokens.get("pixel_values"),
                max_new_tokens=32,
                do_sample=False,
                num_beams=1,
            )
            out = processor.batch_decode(gen, skip_special_tokens=True)[0]
            # Move back to original device for next crops
            model_cpu.to(device)
            return out.replace(task, "").strip()
        except Exception as ee:
            return f"(caption_error: {ee})"

# -----------------------------------------------------------------------------
# OCR: Apple Vision (Swift CLI) + Tesseract fallback
# -----------------------------------------------------------------------------
def ensure_mac_ocr_cli(workdir: Path) -> Optional[Path]:
    bin_path = workdir / "mac_ocr"
    if bin_path.exists() and bin_path.stat().st_size > 0 and _os.access(bin_path, _os.X_OK):
        return bin_path
    swiftc = shutil.which("swiftc")
    if swiftc is None:
        return None
    src_path = workdir / "mac_ocr.swift"
    src_path.write_text(SWIFT_OCR_SOURCE, encoding="utf-8")
    try:
        subprocess.check_call([swiftc, "-O", "-parse-as-library", "-o", str(bin_path), str(src_path)])
        bin_path.chmod(0o755)
        return bin_path
    except subprocess.CalledProcessError as e:
        print(f"Swift compile failed: {e}", file=sys.stderr)
        return None


def run_ocr_apple_vision(image_path: Path, bin_path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    try:
        out = subprocess.check_output([str(bin_path), str(image_path)], text=True)
        items = json.loads(out)
        for it in items:
            x1, y1, x2, y2 = it["bbox"]
            it["bbox"] = (int(x1), int(y1), int(x2), int(y2))
        return items, True
    except Exception as e:
        print(f"Apple Vision OCR failed: {e}", file=sys.stderr)
        return [], False


def run_ocr_tesseract(image_path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    try:
        import pytesseract
    except ImportError:
        return [], False

    from PIL import Image
    try:
        img = Image.open(image_path).convert("L")
        data = pytesseract.image_to_data(
            img, lang="eng", output_type=pytesseract.Output.DICT, config="--psm 6"
        )
        items: List[Dict[str, Any]] = []
        n = len(data["text"])
        for i in range(n):
            text = (data["text"][i] or "").strip()
            conf = data["conf"][i]
            if not text or conf == "-1":
                continue
            x, y, w, h = map(int, (data["left"][i], data["top"][i], data["width"][i], data["height"][i]))
            bbox = (x, y, x + w, y + h)
            poly = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            items.append({"poly": poly, "bbox": bbox, "text": text, "score": float(conf) / 100.0})
        return items, True
    except Exception as e:
        print(f"Tesseract OCR failed: {e}", file=sys.stderr)
        return [], False


def run_ocr_auto(image_path: Path, workdir: Path, prefer: str = "vision") -> Tuple[List[Dict[str, Any]], bool, str]:
    tried = []
    if prefer == "vision":
        tried.append("vision")
        bin_path = ensure_mac_ocr_cli(workdir)
        if bin_path is not None:
            items, ok = run_ocr_apple_vision(image_path, bin_path)
            if ok:
                return items, True, "vision"
        tried.append("tesseract")
        items, ok = run_ocr_tesseract(image_path)
        if ok:
            return items, True, "tesseract"
    else:
        tried.append("tesseract")
        items, ok = run_ocr_tesseract(image_path)
        if ok:
            return items, True, "tesseract"
        tried.append("vision")
        bin_path = ensure_mac_ocr_cli(workdir)
        if bin_path is not None:
            items, ok = run_ocr_apple_vision(image_path, bin_path)
            if ok:
                return items, True, "vision"

    print(f"!! OCR auto failed (tried: {tried})", file=sys.stderr)
    return [], False, "none"

# ------------------------------- Geometry ------------------------------------
def iou(b1, b2) -> float:
    x1, y1, x2, y2 = b1
    X1, Y1, X2, Y2 = b2
    inter_x1, inter_y1 = max(x1, X1), max(y1, Y1)
    inter_x2, inter_y2 = min(x2, X2), min(y2, Y2)
    iw, ih = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    a1 = max(0, x2 - x1) * max(0, y2 - y1)
    a2 = max(0, X2 - X1) * max(0, Y2 - Y1)
    return inter / (a1 + a2 - inter + 1e-9)


def attach_ocr_to_boxes(boxes, ocr_items, iou_thresh=MIN_OCR_IOU):
    for b in boxes:
        best_iou, best_txt, best_score = 0.0, "", 0.0
        for o in ocr_items:
            i = iou(b["xyxy"], o["bbox"])
            if i > best_iou and i >= iou_thresh:
                best_iou, best_txt, best_score = i, o["text"], o["score"]
        b["ocr_text"] = best_txt
        b["ocr_score"] = best_score
    return boxes

# ------------------------------- Visualization -------------------------------
def annotate_image(pil_img: Image.Image, boxes, class_map):
    draw = ImageDraw.Draw(pil_img)
    try:
        font = ImageFont.truetype("Arial.ttf", 14)
    except IOError:
        font = ImageFont.load_default()

    for b in boxes:
        x1, y1, x2, y2 = map(int, b["xyxy"])
        draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=2)
        cls_name = class_map.get(b.get("cls", -1), f"class_{b.get('cls', -1)}")
        parts = [cls_name]
        if b.get("ocr_text"):
            parts.append(f"\"{b['ocr_text']}\"")
        if b.get("caption"):
            parts.append(b["caption"])
        text = " | ".join(parts)
        text_draw = text[:80] + "…" if len(text) > 80 else text

        try:
            bbox = draw.textbbox((x1, y1), text_draw, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 3
            y_top = max(0, y1 - text_h - 2 * pad)
            draw.rectangle([(x1, y_top), (x1 + text_w + 2 * pad, y_top + text_h + 2 * pad)], fill="red")
            draw.text((x1 + pad, y_top + pad), text_draw, fill="white", font=font)
        except Exception:
            draw.text((x1, max(0, y1 - 10)), text_draw, fill="red")

    return pil_img

# ----------------------------------- Main ------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", type=str, required=True, help="Path to a PNG screenshot/image")
    ap.add_argument("--workdir", type=str, default="omni_workdir", help="Working directory")
    ap.add_argument("--outputs", type=str, default="outputs", help="Output directory")
    ap.add_argument("--enable_ocr", action="store_true", help="Run OCR and attach text")
    ap.add_argument("--ocr_backend", type=str, default="auto", choices=["auto","vision","tesseract","none"],
                    help="OCR backend to use")
    ap.add_argument("--disable_caption", action="store_true", help="Skip Florence-2 captioning")
    ap.add_argument("--min_ocr_iou", type=float, default=MIN_OCR_IOU, help="Min IoU to attach OCR text")
    args = ap.parse_args()

    png_path = Path(args.png)
    if not png_path.exists():
        raise FileNotFoundError(f"PNG not found: {png_path}")
    workdir = Path(args.workdir)
    outputs = Path(args.outputs)
    outputs.mkdir(parents=True, exist_ok=True)
    repo_root = workdir / "OmniParser"
    weights_dir = repo_root / "weights"
    device = get_device()
    print(f">> Device: {device}")

    print(">> Ensuring model weights are downloaded...")
    ensure_omniparser_weights(weights_dir)
    if not args.disable_caption:
        ensure_florence_local(workdir / "Florence-2-base-ft")

    pil_img = Image.open(png_path).convert("RGB")
    class_map = class_names_from_yaml(weights_dir)

    print(">> Loading YOLOv8 detector...")
    yolo = load_yolo(weights_dir)
    print(">> Detecting UI elements...")
    boxes = run_detection(yolo, png_path)
    print(f"  detections: {len(boxes)}")
    del yolo
    if device.type == "mps":
        gc.collect(); torch.mps.empty_cache()

    # OCR
    ocr_items: List[Dict[str, Any]] = []
    if args.enable_ocr and args.ocr_backend != "none":
        backend_used = "none"
        print(">> Running OCR...")
        if args.ocr_backend == "vision":
            bin_path = ensure_mac_ocr_cli(workdir)
            if bin_path is None:
                print("!! Apple Vision OCR unavailable; falling back to Tesseract.")
                ocr_items, ok = run_ocr_tesseract(png_path)
                backend_used = "tesseract" if ok else "none"
            else:
                ocr_items, ok = run_ocr_apple_vision(png_path, bin_path)
                backend_used = "vision" if ok else "none"
        elif args.ocr_backend == "tesseract":
            ocr_items, ok = run_ocr_tesseract(png_path)
            backend_used = "tesseract" if ok else "none"
        else:
            ocr_items, ok, backend_used = run_ocr_auto(png_path, workdir, prefer="vision")

        if backend_used == "none":
            print("!! OCR failed; continuing without OCR.")
        else:
            boxes = attach_ocr_to_boxes(boxes, ocr_items, iou_thresh=args.min_ocr_iou)
            print(f"  OCR backend: {backend_used} | items: {len(ocr_items)}")

    # Florence captioning
    if not args.disable_caption:
        print(">> Loading Florence-2...")
        florence_local = workdir / "Florence-2-base-ft"
        processor, model = load_florence(florence_local, device)
        print(">> Captioning with Florence-2...")
        crops = crop_boxes(pil_img, boxes)
        for i, crop in crops:
            boxes[i]["caption"] = florence_caption(processor, model, crop, device)
        del processor, model
        if device.type == "mps":
            gc.collect(); torch.mps.empty_cache()
    else:
        for b in boxes:
            b["caption"] = ""

    result = {
        "image": str(png_path),
        "num_detections": len(boxes),
        "detections": boxes,
        "ocr_items": ocr_items,
    }
    json_path = outputs / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f">> Wrote {json_path}")

    annotated = annotate_image(pil_img.copy(), boxes, class_map)
    out_png = outputs / "annotated.png"
    annotated.save(out_png)
    print(f">> Wrote {out_png}")
    print(">> Done.")


if __name__ == "__main__":
    main()
