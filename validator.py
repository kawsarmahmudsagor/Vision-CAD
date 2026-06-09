"""
validator.py
──────────────────────────────────────────────────────────────────────────────
Validates rendered OpenSCAD views against COCO bounding boxes.

Pipeline:
    rendered PNGs → detect component bounding boxes (via colour or contour) →
    compare with COCO pixel bboxes → compute IoU + error_mm → produce
    adjustment deltas fed back into the refinement loop.

Because OpenSCAD models use named color() calls (enforced by STRICT_CODE_PROMPT),
we detect component bounding boxes by colour mask.  Where colour detection is
ambiguous we fall back to full-image contour detection.

Public API:
    validate(geometry, scad_path, output_dir, render_views_fn) -> ValidationReport
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Thresholds (mirrors ring pipeline config) ─────────────────────────────────
IOU_THRESHOLD    = 0.75   # slightly relaxed vs ring pipeline (0.85) — OpenSCAD camera distortion
MAX_ERROR_MM     = 1.0    # mm; error above this triggers an adjustment

# Known named-CSS-colour → rough HSV range for segmentation
# We only need to distinguish metal (silvery/gold/rose) from gem (cyan/transparent)
_COLOUR_RANGES = {
    "metal": [
        # Silver/platinum greys
        {"h": (0, 180), "s": (0, 60),  "v": (100, 255)},
    ],
    "gem": [
        # Typical gem_color = "#E0FFFF" (light cyan)
        {"h": (85, 110), "s": (30, 255), "v": (150, 255)},
        # Also diamond whites / near-white
        {"h": (0, 180),  "s": (0, 30),   "v": (220, 255)},
    ],
}


def _iou(box1: dict, box2: dict) -> float:
    x1 = max(box1["x"], box2["x"])
    y1 = max(box1["y"], box2["y"])
    x2 = min(box1["x"] + box1["w"], box2["x"] + box2["w"])
    y2 = min(box1["y"] + box1["h"], box2["y"] + box2["h"])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = box1["w"] * box1["h"]
    area2 = box2["w"] * box2["h"]
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def _detect_bbox_from_image(png_path: str) -> Optional[dict]:
    """
    Detect the overall non-background bounding box of the rendered model.
    Uses a white/near-white background assumption (OpenSCAD default).
    Returns {"x","y","w","h"} in pixels, or None.
    """
    if not png_path or not Path(png_path).exists():
        return None

    img = cv2.imread(png_path)
    if img is None:
        return None

    # Convert to greyscale; background is near-white (>240)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Morphological clean-up
    kernel = np.ones((5, 5), np.uint8)
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Bounding box of all contours merged
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}


def _detect_component_bbox(png_path: str, colour_key: str) -> Optional[dict]:
    """
    Detect bounding box for a specific colour group ("metal" or "gem").
    Returns None if colour not found or image missing.
    """
    if not png_path or not Path(png_path).exists():
        return None
    img = cv2.imread(png_path)
    if img is None:
        return None

    hsv   = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    masks = []
    for rng in _COLOUR_RANGES.get(colour_key, []):
        lo = np.array([rng["h"][0], rng["s"][0], rng["v"][0]], dtype=np.uint8)
        hi = np.array([rng["h"][1], rng["s"][1], rng["v"][1]], dtype=np.uint8)
        masks.append(cv2.inRange(hsv, lo, hi))

    if not masks:
        return None
    combined = masks[0]
    for m in masks[1:]:
        combined = cv2.bitwise_or(combined, m)

    kernel   = np.ones((5, 5), np.uint8)
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    if w < 5 or h < 5:
        return None
    return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}


def _coco_bbox_dict(bbox_raw: Optional[dict]) -> Optional[dict]:
    """Normalise COCO bbox_top/bbox_side dict to {x,y,w,h}."""
    if not bbox_raw:
        return None
    return {
        "x": float(bbox_raw.get("x", 0)),
        "y": float(bbox_raw.get("y", 0)),
        "w": float(bbox_raw.get("w", 1)),
        "h": float(bbox_raw.get("h", 1)),
    }


async def validate(
    geometry: dict,
    scad_path: str,
    output_dir: str,
    render_views_fn,
) -> dict:
    """
    Full validation cycle:
        1. Render OpenSCAD to top + side PNGs.
        2. Detect bounding boxes in rendered images.
        3. Compare against COCO annotation bboxes.
        4. Produce adjustment deltas and a ValidationReport.

    Returns:
    {
        "is_valid":    bool,
        "metrics":     { component: { iou, error_mm, ... } },
        "adjustments": { "geometry": { component: { param: delta } } },
        "render_paths": { "top": str, "side": str }
    }
    """
    # ── 1. Render ─────────────────────────────────────────────────────────────
    render_paths = await render_views_fn(scad_path, output_dir)
    top_png  = render_paths["top"]  if render_paths else None
    side_png = render_paths["side"] if render_paths else None

    meta       = geometry.get("meta", {})
    scale_top  = meta.get("scale_top",  0.05)
    scale_side = meta.get("scale_side", 0.05)
    head       = geometry.get("head",  {})
    shank      = geometry.get("shank", {})

    report = {
        "is_valid":    True,
        "metrics":     {},
        "adjustments": {"geometry": {}},
        "render_paths": {"top": top_png, "side": side_png},
    }

    if not render_paths:
        logger.warning("Render failed — skipping visual validation")
        report["is_valid"] = False
        report["render_error"] = "OpenSCAD render produced no output"
        return report

    # ── 2. Band validation (top view — overall ring diameter) ─────────────────
    band_geom  = shank.get("band", {})
    coco_outer = band_geom.get("outer_radius", 10.3) * 2.0  # mm diameter
    detected_ring = _detect_bbox_from_image(top_png)

    if detected_ring and coco_outer > 0:
        detected_d_mm = detected_ring["w"] * scale_top
        error_mm      = abs(detected_d_mm - coco_outer)
        iou_approx    = 1.0 - min(1.0, error_mm / coco_outer)

        report["metrics"]["band"] = {
            "detected_diameter_mm": round(detected_d_mm, 3),
            "coco_diameter_mm":     round(coco_outer, 3),
            "error_mm":             round(error_mm, 3),
            "iou":                  round(iou_approx, 3),
        }
        if error_mm > MAX_ERROR_MM:
            report["is_valid"] = False
            delta_thickness    = (coco_outer - detected_d_mm) / 2.0
            report["adjustments"]["geometry"]["band"] = {
                "thickness_delta_mm": round(delta_thickness, 3)
            }

    # ── 3. Center stone validation ─────────────────────────────────────────────
    stone_geom = head.get("center_stone", {})
    if stone_geom:
        # Top view: stone width
        coco_bbox_top  = _coco_bbox_dict(stone_geom.get("bbox_top"))
        detected_gem   = _detect_component_bbox(top_png, "gem")

        if coco_bbox_top and detected_gem:
            iou_top   = _iou(detected_gem, coco_bbox_top)
            w_error   = abs(detected_gem["w"] * scale_top - stone_geom.get("width", 6.0))

            report["metrics"]["center_stone"] = {
                "iou_top":       round(iou_top, 3),
                "width_error_mm": round(w_error, 3),
            }
            stone_adj = {}
            if iou_top < IOU_THRESHOLD or w_error > MAX_ERROR_MM:
                report["is_valid"]   = False
                coco_w_mm            = stone_geom.get("width", 6.0)
                detected_w_mm        = detected_gem["w"] * scale_top
                stone_adj["width_delta_mm"] = round(coco_w_mm - detected_w_mm, 3)

        # Side view: stone height + Z position
        coco_bbox_side  = _coco_bbox_dict(stone_geom.get("bbox_side"))
        detected_gem_s  = _detect_component_bbox(side_png, "gem")

        if coco_bbox_side and detected_gem_s and scale_side > 0:
            iou_side  = _iou(detected_gem_s, coco_bbox_side)
            h_error   = abs(detected_gem_s["h"] * scale_side - stone_geom.get("height", 3.8))

            # Z error: compare rendered gem top pixel with COCO
            meta_side  = meta.get("origin_side", {"y": 400.0})
            coco_stone_z    = stone_geom.get("z_offset", 12.0)
            detected_top_px = detected_gem_s["y"]
            detected_z_mm   = (meta_side["y"] - detected_top_px) * scale_side

            # detected_z_mm is the top of the gem; coco_stone_z is the base
            coco_h_mm    = stone_geom.get("height", 3.8)
            detected_base_z = detected_z_mm - detected_gem_s["h"] * scale_side
            z_error_mm   = abs(detected_base_z - coco_stone_z)

            report["metrics"].setdefault("center_stone", {}).update({
                "iou_side":        round(iou_side, 3),
                "height_error_mm": round(h_error, 3),
                "z_error_mm":      round(z_error_mm, 3),
            })

            stone_adj = report["adjustments"]["geometry"].get("center_stone", {})
            if iou_side < IOU_THRESHOLD or h_error > MAX_ERROR_MM:
                report["is_valid"] = False
                stone_adj["height_delta_mm"]  = round(coco_h_mm - detected_gem_s["h"] * scale_side, 3)
            if z_error_mm > MAX_ERROR_MM:
                report["is_valid"] = False
                stone_adj["z_delta_mm"] = round(coco_stone_z - detected_base_z, 3)

            if stone_adj:
                report["adjustments"]["geometry"]["center_stone"] = stone_adj

    # ── 4. Save report ────────────────────────────────────────────────────────
    report_path = os.path.join(output_dir, f"{Path(scad_path).stem}_validation.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Validation complete — valid={report['is_valid']} — report: {report_path}")

    return report