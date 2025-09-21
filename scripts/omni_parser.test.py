#!/usr/bin/env python3
"""
OmniParser v2 on macOS (MPS) or CPU, with YOLOv8 + Florence-2, optional PaddleOCR.

This script incorporates numerous fixes and optimizations for memory-constrained
M1 Macs, including JIT model loading, thread limiters, and robust API handling.

Outputs:
  - outputs/annotated.png  (class | [ocr text] | caption)
  - outputs/results.json
"""

import os
# FIX: Set thread caps BEFORE heavy imports to prevent segfaults on macOS
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
import json
import shutil
import argparse
import gc
from pathlib import Path
from typing import List, Dict, Tuple, Any

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
OMNI_DETECT_FILES = ["icon_detect/train_args.yaml", "icon_detect/model.pt", "icon_detect/model.yaml"]
OMNI_CAPTION_FILES = ["icon_caption/config.json", "icon_caption/generation_config.json", "icon_caption/model.safetensors"]
FLORENCE_REPO = "microsoft/Florence-2-base-ft"

CONF_THRES = 0.25
IOU_THRES = 0.45
MAX_DETS = 200
MIN_OCR_IOU = 0.1

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
        hf_hub_download(repo_id=HF_OMNIPARSER_REPO, filename=rel, local_dir=weights_dir, local_dir_use_symlinks=False)
    src = weights_dir / "icon_caption"
    dst = weights_dir / "icon_caption_florence"
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))

def ensure_florence_local(florence_root: Path):
    if florence_root.exists(): return
    snapshot_download(repo_id=FLORENCE_REPO, local_dir=florence_root, local_dir_use_symlinks=False, ignore_patterns=["*.md", "*.txt", "*.png", "*.jpg", "*.jpeg", "README*"])

def load_yolo(weights_dir: Path):
    model_path = weights_dir / "icon_detect" / "model.pt"
    if not model_path.exists(): raise FileNotFoundError(f"Missing YOLO weights at: {model_path}")
    return YOLO(str(model_path))

def class_names_from_yaml(weights_dir: Path) -> Dict[int, str]:
    yaml_path = weights_dir / "icon_detect" / "model.yaml"
    if not yaml_path.exists(): return {}
    with open(yaml_path, "r", encoding="utf-8") as f: data = yaml.safe_load(f)
    names = data.get("names", {})
    if isinstance(names, dict): return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, list): return {i: str(n) for i, n in enumerate(names)}
    return {}

def install_flash_attn_stub():
    if "flash_attn" in sys.modules: return
    import types
    from importlib.machinery import ModuleSpec
    stub = types.ModuleType("flash_attn")
    def _missing(*args, **kwargs): raise ImportError("flash_attn is not available on this platform")
    stub.__getattr__ = lambda name: _missing
    stub.__spec__ = ModuleSpec("flash_attn", loader=None)
    sys.modules["flash_attn"] = stub

def load_florence(florence_local_dir: Path, device: torch.device):
    install_flash_attn_stub()
    try:
        import timm; import einops
    except ImportError as e:
        raise RuntimeError(f"Missing dependency: 'pip install timm einops'. Original error: {e}")

    dtype = torch.float32 if device.type != "cuda" else torch.float16
    processor = AutoProcessor.from_pretrained(str(florence_local_dir), trust_remote_code=True)
    
    with torch.inference_mode():
        model = AutoModelForCausalLM.from_pretrained(
            str(florence_local_dir),
            trust_remote_code=True,
            dtype=dtype,
            low_cpu_mem_usage=True,
            attn_implementation="eager",
        ).to(device).eval()
    return processor, model

def run_detection(yolo_model, image_path: Path) -> List[Dict[str, Any]]:
    res = yolo_model.predict(
        source=str(image_path),
        conf=CONF_THRES, iou=IOU_THRES, max_det=MAX_DETS,
        device="mps" if torch.backends.mps.is_available() else "cpu",
        imgsz=960,
        verbose=False
    )
    out = []
    if res and res[0].boxes is not None:
        for b in res[0].boxes:
            out.append({"xyxy": b.xyxy[0].cpu().numpy().tolist(), "conf": float(b.conf[0].cpu()), "cls": int(b.cls[0].cpu())})
    return out

def crop_boxes(pil_img: Image.Image, boxes):
    crops = []
    W, H = pil_img.size
    for i, b in enumerate(boxes):
        x1, y1, x2, y2 = map(int, b["xyxy"])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        if x2 > x1 and y2 > y1: crops.append((i, pil_img.crop((x1, y1, x2, y2))))
    return crops

def pad_to_square(pil_img, background_color=(0, 0, 0)):
    width, height = pil_img.size
    if width == height:
        return pil_img
    elif width > height:
        result = Image.new(pil_img.mode, (width, width), background_color)
        result.paste(pil_img, (0, (width - height) // 2))
        return result
    else:
        result = Image.new(pil_img.mode, (height, height), background_color)
        result.paste(pil_img, ((height - width) // 2, 0))
        return result

def florence_caption(processor, model, pil_img: Image.Image, device: torch.device, task="<CAPTION>"):
    with torch.inference_mode():
        try:
            inputs = processor(text=task, images=pil_img, return_tensors="pt")
            if 'pixel_values' not in inputs or inputs['pixel_values'] is None:
                return "(caption_error: Processor failed)"
            for k, v in list(inputs.items()):
                if hasattr(v, "to"): inputs[k] = v.to(device=device, dtype=model.dtype)
            inputs['input_ids'] = inputs['input_ids'].to(torch.long)
            
            # FINAL FIX: Disable the KV cache to prevent an MPS-related bug in the model.
            gen = model.generate(
                **inputs,
                max_new_tokens=32,
                do_sample=False,
                num_beams=1,
                use_cache=False
            )
            out = processor.batch_decode(gen, skip_special_tokens=True)[0]
            return out.replace(task, "").strip()
        except Exception as e:
            return f"(caption_error: {e})"

# ------------------------------- OCR helpers ---------------------------------
def try_import_paddleocr():
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR
    except ImportError:
        return None

def _build_paddleocr(PaddleOCR):
    return PaddleOCR(ocr_version="PP-OCRv3", lang="en", use_textline_orientation=False)

def run_ocr_on_image(image_path: Path):
    PaddleOCR = try_import_paddleocr()
    if PaddleOCR is None: return [], False

    ocr = _build_paddleocr(PaddleOCR)
    items = []
    
    # Switch to the modern `predict` method to fix "0 items" issue.
    results = ocr.predict(str(image_path))
    if results and results[0]:
        for res in results[0]:
            try:
                poly, (text, score) = res
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
                items.append({"poly": [p.tolist() for p in poly], "bbox": bbox, "text": text, "score": float(score)})
            except (ValueError, TypeError):
                continue
    return items, True

def iou(b1, b2) -> float:
    x1, y1, x2, y2 = b1
    X1, Y1, X2, Y2 = b2
    inter_x1, inter_y1 = max(x1, X1), max(y1, Y1)
    inter_x2, inter_y2 = min(x2, X2), min(y2, Y2)
    iw, ih = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter == 0: return 0.0
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

def annotate_image(pil_img: Image.Image, boxes, class_map):
    draw = ImageDraw.Draw(pil_img)
    try: font = ImageFont.truetype("Arial.ttf", 14)
    except IOError: font = ImageFont.load_default()
    for b in boxes:
        x1, y1, x2, y2 = map(int, b["xyxy"])
        draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=2)
        cls_name = class_map.get(b.get("cls", -1), f"class_{b.get('cls', -1)}")
        parts = [cls_name]
        if b.get("ocr_text"): parts.append(f'"{b["ocr_text"]}"')
        if b.get("caption"): parts.append(b["caption"])
        text = " | ".join(parts)
        text_draw = text[:80] + "…" if len(text) > 80 else text
        try:
            bbox = draw.textbbox((x1, y1), text_draw, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 3
            y_top = max(0, y1 - text_h - 2 * pad)
            draw.rectangle([(x1, y_top), (x1 + text_w + 2*pad, y_top + text_h + 2*pad)], fill="red")
            draw.text((x1 + pad, y_top + pad), text_draw, fill="white", font=font)
        except Exception:
            draw.text((x1, y1 - 10), text_draw, fill="red")
    return pil_img

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", type=str, required=True, help="Path to a PNG screenshot/image")
    ap.add_argument("--workdir", type=str, default="omni_workdir", help="Working directory")
    ap.add_argument("--outputs", type=str, default="outputs", help="Output directory")
    ap.add_argument("--enable_ocr", action="store_true", help="Run PaddleOCR and attach text")
    ap.add_argument("--disable_caption", action="store_true", help="Skip Florence-2 captioning")
    ap.add_argument("--min_ocr_iou", type=float, default=MIN_OCR_IOU, help="Min IoU to attach OCR text")
    args = ap.parse_args()

    png_path = Path(args.png)
    if not png_path.exists(): raise FileNotFoundError(f"PNG not found: {png_path}")
    workdir, outputs = Path(args.workdir), Path(args.outputs)
    outputs.mkdir(parents=True, exist_ok=True)
    weights_dir = workdir / "OmniParser" / "weights"
    device = get_device()
    print(f">> Device: {device}")

    print(">> Ensuring model weights are downloaded...")
    ensure_omniparser_weights(weights_dir)
    if not args.disable_caption: ensure_florence_local(workdir / "Florence-2-base-ft")

    pil_img = Image.open(png_path).convert("RGB")
    class_map = class_names_from_yaml(weights_dir)

    print(">> Loading YOLOv8 detector...")
    yolo = load_yolo(weights_dir)
    print(">> Detecting UI elements...")
    boxes = run_detection(yolo, png_path)
    print(f"  detections: {len(boxes)}")
    del yolo
    if device.type == 'mps': gc.collect(); torch.mps.empty_cache()

    ocr_items = []
    if args.enable_ocr:
        print(">> Running PaddleOCR...")
        ocr_items, ok = run_ocr_on_image(png_path)
        if not ok: print("!! PaddleOCR not installed; skipping OCR.")
        else:
            boxes = attach_ocr_to_boxes(boxes, ocr_items, iou_thresh=args.min_ocr_iou)
            print(f"  OCR items: {len(ocr_items)}")

    if not args.disable_caption:
        print(">> Loading Florence-2...")
        florence_local = workdir / "Florence-2-base-ft"
        processor, model = load_florence(florence_local, device)
        print(">> Captioning with Florence-2...")
        
        MIN_CROP_DIM = 32
        crops = crop_boxes(pil_img, boxes)
        for i, crop in crops:
            if crop.width < MIN_CROP_DIM or crop.height < MIN_CROP_DIM:
                boxes[i]["caption"] = f"(caption_skipped: Crop too small {crop.width}x{crop.height})"
                continue
            
            padded_crop = pad_to_square(crop)
            boxes[i]["caption"] = florence_caption(processor, model, padded_crop, device)
            
        del processor, model
        if device.type == 'mps': gc.collect(); torch.mps.empty_cache()
    else:
        for b in boxes: b["caption"] = ""

    result = {"image": str(png_path), "num_detections": len(boxes), "detections": boxes, "ocr_items": ocr_items}
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
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    main()