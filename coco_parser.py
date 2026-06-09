"""
coco_parser.py
──────────────────────────────────────────────────────────────────────────────
Parses a two-view COCO annotation file (top-view + side-view image IDs)
into physical millimetre dimensions for ring components.

Mirrors the approach in ring_generation_pipeline/coco_parser.py but is
self-contained and adapted for Vision-CAD's FastAPI context.

Output of parse_ring_geometry():
{
    "meta": {
        "scale_top": mm/px,
        "scale_side": mm/px,
        "origin_top":  {"x": cx_px, "y": cy_px},
        "origin_side": {"x": cx_px, "y": cy_px}
    },
    "shank": {
        "band": { inner_radius, width, thickness, outer_radius }
    },
    "head": {
        "center_stone": { width, length, height, z_offset, bbox_top, bbox_side },
        "prongs":        { ... },          # only if annotated
        "gallery":       { ... },          # only if annotated
        "bridge":        { ... },          # only if annotated
        "halo":          { ... }           # only if annotated
    }
}
"""

import json
import math
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Default physical constants (standard ring size ~6.5 US) ──────────────────
DEFAULT_INNER_DIAMETER_MM = 17.0
DEFAULT_BAND_THICKNESS_MM = 1.8
DEFAULT_BAND_WIDTH_MM     = 2.5


class BBox:
    def __init__(self, bbox_list: list):
        self.x  = float(bbox_list[0])
        self.y  = float(bbox_list[1])
        self.w  = float(bbox_list[2])
        self.h  = float(bbox_list[3])
        self.cx = self.x + self.w / 2.0
        self.cy = self.y + self.h / 2.0

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h,
                "cx": self.cx, "cy": self.cy}


def _normalise_category(raw: str) -> str:
    raw = raw.lower().strip()
    if raw in ("shank", "band", "ring_band"):
        return "band"
    if raw in ("void", "finger_hole"):
        return "inner_band"
    if raw in ("center_stone", "stone", "centerstone"):
        return "center_stone"
    if raw in ("prong", "prongs"):
        return "prongs"
    if raw in ("gallery", "undergallery"):
        return "gallery"
    if raw == "bridge":
        return "bridge"
    if raw == "halo":
        return "halo"
    if raw in ("shoulder", "shoulders"):
        return "shoulder"
    if raw in ("side_stones", "sidestones", "pave_shoulder"):
        return "side_stones"
    return raw


def load_annotations(coco_path: str, image_id: int) -> list:
    """Return a list of annotation dicts for the given image_id."""
    data = json.loads(Path(coco_path).read_text())
    cat_map = {c["id"]: c["name"] for c in data.get("categories", [])}

    results = []
    for ann in data.get("annotations", []):
        if ann.get("image_id") != image_id:
            continue
        cat_raw  = cat_map.get(ann.get("category_id", -1), "unknown")
        cat_name = _normalise_category(cat_raw)
        results.append({
            "category":    cat_name,
            "bbox":        BBox(ann.get("bbox", [0, 0, 1, 1])),
            "segmentation": ann.get("segmentation", []),
            "area":         ann.get("area", 0),
        })

    logger.info(f"Loaded {len(results)} annotations for image_id={image_id}")
    return results


def _combined_bbox(anns: list, category: str) -> Optional[BBox]:
    matching = [a for a in anns if a["category"] == category]
    if not matching:
        return None
    x_min = min(a["bbox"].x for a in matching)
    y_min = min(a["bbox"].y for a in matching)
    x_max = max(a["bbox"].x + a["bbox"].w for a in matching)
    y_max = max(a["bbox"].y + a["bbox"].h for a in matching)
    return BBox([x_min, y_min, x_max - x_min, y_max - y_min])


def parse_ring_geometry(coco_path: str,
                        top_image_id: int,
                        side_image_id: int) -> dict:
    """
    Parse a two-view COCO file into physical ring geometry (mm).

    Z-convention (matches ring_generation_pipeline + OpenSCAD assembly):
        Z = 0        → ring geometric centre / equator
        Z = +outer_r → band top  (where head components attach)
        Z = -outer_r → band bottom

    All z_offset values = BASE (lowest Z point) of that component.
    """
    top_anns  = load_annotations(coco_path, top_image_id)
    side_anns = load_annotations(coco_path, side_image_id)

    # ── Scale + origin from top view ─────────────────────────────────────────
    top_band  = _combined_bbox(top_anns, "band")
    top_inner = _combined_bbox(top_anns, "inner_band")

    inner_d = DEFAULT_INNER_DIAMETER_MM
    outer_d = inner_d + 2 * DEFAULT_BAND_THICKNESS_MM

    if top_inner:
        scale_top = inner_d / top_inner.w
        cx_top, cy_top = top_inner.cx, top_inner.cy
    elif top_band:
        scale_top = outer_d / top_band.w
        cx_top, cy_top = top_band.cx, top_band.cy
    else:
        scale_top = 0.05
        cx_top = cy_top = 400.0
        logger.warning("No band/void in top view — using default scale")

    # ── Scale + origin from side view ────────────────────────────────────────
    side_band  = _combined_bbox(side_anns, "band")
    side_inner = _combined_bbox(side_anns, "inner_band")

    if side_band:
        scale_side = outer_d / side_band.w
        cx_side = side_band.cx
        cy_side = side_band.cy   # ring centre pixel = Z=0 in world space
    elif side_inner:
        scale_side = inner_d / ((side_inner.w + side_inner.h) / 2.0)
        cx_side = side_inner.cx
        cy_side = side_inner.cy
    else:
        scale_side = 0.05
        cx_side = cy_side = 400.0
        logger.warning("No band/void in side view — using default scale")

    # ── Band physical dims ────────────────────────────────────────────────────
    band_thickness = DEFAULT_BAND_THICKNESS_MM
    band_width     = DEFAULT_BAND_WIDTH_MM
    if top_band and top_inner:
        band_thickness = ((top_band.w - top_inner.w) / 2.0) * scale_top

    inner_radius = inner_d / 2.0
    outer_radius = inner_radius + band_thickness

    # ── Helper: pixel bbox → physical mm dims ─────────────────────────────────
    def _physical(bbox_top: Optional[BBox], bbox_side: Optional[BBox]) -> dict:
        dims: dict = {}
        if bbox_top:
            dims["width"]    = bbox_top.w * scale_top
            dims["length"]   = bbox_top.h * scale_top
            dims["x_offset"] = (bbox_top.cx - cx_top)  * scale_top
            dims["y_offset"] = (cy_top - bbox_top.cy)  * scale_top
        if bbox_side:
            if "width" not in dims:
                dims["width"] = bbox_side.w * scale_side
            comp_h  = bbox_side.h * scale_side
            dims["height"]      = comp_h
            dims["x_offset_side"] = (bbox_side.cx - cx_side) * scale_side
            # Base Z: pixel above cy_side → positive world Z
            center_z         = (cy_side - bbox_side.cy) * scale_side
            dims["z_offset"] = center_z - comp_h / 2.0
        return dims

    geometry: dict = {
        "meta": {
            "scale_top":   scale_top,
            "scale_side":  scale_side,
            "origin_top":  {"x": cx_top,  "y": cy_top},
            "origin_side": {"x": cx_side, "y": cy_side},
        },
        "shank": {
            "band": {
                "inner_radius": inner_radius,
                "width":        band_width,
                "thickness":    band_thickness,
                "outer_radius": outer_radius,
            }
        },
        "head": {}
    }

    # ── Head components ───────────────────────────────────────────────────────
    for cat in ("center_stone", "prongs", "gallery", "bridge", "halo"):
        bt = _combined_bbox(top_anns,  cat)
        bs = _combined_bbox(side_anns, cat)
        if bt or bs:
            dims = _physical(bt, bs)
            dims["bbox_top"]  = bt.to_dict() if bt else None
            dims["bbox_side"] = bs.to_dict() if bs else None
            geometry["head"][cat] = dims

    # ── Per-prong angle extraction (mirrors ring_generation_pipeline) ─────────
    individual_prongs = [a for a in top_anns if a["category"] == "prongs"]
    stone_top         = _combined_bbox(top_anns, "center_stone")

    if len(individual_prongs) > 1 and stone_top:
        angles = []
        for ann in individual_prongs:
            dx = ann["bbox"].cx - stone_top.cx
            dy = ann["bbox"].cy - stone_top.cy
            angles.append(round(math.degrees(math.atan2(dy, dx)), 1))

        avg_aspect = sum(
            a["bbox"].h / a["bbox"].w if a["bbox"].w > 0 else 1.0
            for a in individual_prongs
        ) / len(individual_prongs)
        orientation = "radial" if avg_aspect > 1.1 else "vertical"

        if "prongs" in geometry["head"]:
            geometry["head"]["prongs"]["prong_angles_deg"] = angles
            geometry["head"]["prongs"]["orientation"]      = orientation
    else:
        if "prongs" in geometry["head"]:
            geometry["head"]["prongs"].setdefault("prong_angles_deg", [])
            geometry["head"]["prongs"].setdefault("orientation", "radial")

    return geometry