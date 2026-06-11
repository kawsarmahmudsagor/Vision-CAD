"""
geometry_extractor.py
──────────────────────────────────────────────────────────────────────────────
Converts the raw physical geometry dict (from coco_parser) into a clean,
LLM-ready geometry context block.

This is the "deterministic owns geometry" layer — the LLM must NOT guess sizes.
It receives all dimensions from here, so it only needs to decide construction
logic and style.

Output: GeometryContext dict used by constraint_builder and codegen_service.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Sanity clamps for physical dimensions
_CLAMPS = {
    "stone_width":  (2.0,  20.0),
    "stone_height": (1.0,  15.0),
    "prong_radius": (0.1,   0.7),
    "gallery_h":    (0.5,  20.0),
    "halo_stone":   (0.3,   3.0),
}


def _clamp(val: float, key: str) -> float:
    lo, hi = _CLAMPS.get(key, (0.0, 1e9))
    return max(lo, min(hi, val))


def build_geometry_context(geometry: dict, semantics: dict) -> dict:
    """
    Merge physical geometry + semantic style into a single context dict
    that the LLM receives as ground truth for all numeric dimensions.

    Parameters
    ----------
    geometry  : output of coco_parser.parse_ring_geometry()
    semantics : output of vision_service.describe_image() — but this function
                also accepts a pre-parsed semantics dict for structured fields.

    Returns a GeometryContext dict with sections:
        band, center_stone, prongs?, gallery?, bridge?, halo?, constraints
    """
    shank = geometry.get("shank", {})
    head  = geometry.get("head",  {})
    band_g  = shank.get("band", {})
    stone_g = head.get("center_stone", {})
    prong_g = head.get("prongs",  {})
    gal_g   = head.get("gallery", {})
    br_g    = head.get("bridge",  {})
    halo_g  = head.get("halo",   {})

    # ── Band ─────────────────────────────────────────────────────────────────
    inner_r = float(band_g.get("inner_radius", 8.5))
    thick   = float(band_g.get("thickness",    1.8))
    width   = float(band_g.get("width",        2.5))
    outer_r = inner_r + thick

    band_ctx = {
        "inner_radius_mm": round(inner_r, 3),
        "outer_radius_mm": round(outer_r, 3),
        "thickness_mm":    round(thick,   3),
        "width_mm":        round(width,   3),
    }

    # ── Z stack — derived from first principles, same as ring pipeline ────────
    # gallery_h == 0 when gallery not annotated (stone base = band top + lift)
    gallery_h = 0.0
    if gal_g:
        raw_h = gal_g.get("height", 0.0)
        if 0.5 < raw_h < 20.0:
            gallery_h = raw_h
        else:
            stone_h_est = float(stone_g.get("height", 3.8))
            gallery_h = max(1.5, stone_h_est * 0.5)

    band_top_z   = outer_r
    gallery_base_z = band_top_z
    stone_base_z = gallery_base_z + gallery_h   # provisional; refined by validator

    # ── Center stone ─────────────────────────────────────────────────────────
    stone_cut    = semantics.get("center_stone_cut", "round").lower()
    stone_width  = _clamp(float(stone_g.get("width",  6.0)), "stone_width")
    stone_height = _clamp(float(stone_g.get("height", 3.8)), "stone_height")
    stone_length = stone_width if stone_cut == "round" else \
                   _clamp(float(stone_g.get("length", stone_width)), "stone_width")

    stone_ctx = {
        "cut":           stone_cut,
        "width_mm":      round(stone_width,  3),
        "length_mm":     round(stone_length, 3),
        "height_mm":     round(stone_height, 3),
        "base_z_mm":     round(stone_base_z, 3),   # pavilion tip world Z
        "radius_mm":     round(stone_width / 2.0, 3),
    }

    ctx: dict = {
        "band":         band_ctx,
        "center_stone": stone_ctx,
        "z_stack": {
            "band_top_z":    round(band_top_z,    3),
            "gallery_base_z": round(gallery_base_z, 3),
            "stone_base_z":  round(stone_base_z,  3),
            "stone_top_z":   round(stone_base_z + stone_height, 3),
        }
    }

    # ── Gallery (if annotated) ────────────────────────────────────────────────
    if gal_g:
        ctx["gallery"] = {
            "mode":      "explicit",
            "height_mm": round(gallery_h, 3),
            "width_mm":  round(stone_width + 0.4, 3),
            "base_z_mm": round(gallery_base_z, 3),
            "style":     semantics.get("ring_style", "solitaire").lower(),
        }
    else:
        # Always emit the structural role, even when not annotated
        ctx["gallery"] = {
            "mode":      "inferred",
            "height_mm": 0.0,
            "base_z_mm": round(band_top_z, 3),
        }

    # ── Prongs (if annotated) ─────────────────────────────────────────────────
    if prong_g:
        prong_count  = int(semantics.get("prong_count", 4))
        if prong_count not in (4, 6, 8):
            prong_count = 4
        prong_radius = _clamp(float(prong_g.get("width", 0.8)) / 2.0, "prong_radius")
        prong_angles = list(prong_g.get("prong_angles_deg", []))
        if not prong_angles:
            step = 360.0 / prong_count
            prong_angles = [round(i * step + 45, 1) for i in range(prong_count)] \
                           if prong_count == 4 else \
                           [round(i * step, 1) for i in range(prong_count)]

        # Enforce jewellery-realistic proportions.
        # A claw prong should be ~8-12% of stone radius — never a fat column.
        stone_r = stone_width / 2.0
        prong_radius = min(prong_radius, stone_r * 0.12)
        prong_radius = max(prong_radius, 0.25)   # never thinner than 0.25 mm

        # Prong base: always anchored at band_top_z so prongs rise from the
        # band shoulder, not from mid-air (happens when no gallery annotated).
        prong_base_z = round(band_top_z, 3)

        ctx["prongs"] = {
            "count":               prong_count,
            "radius_mm":           round(prong_radius, 3),
            "height_mm":           round(stone_height + 1.5, 3),
            "radial_distance_mm":  round(stone_r + prong_radius * 0.6, 3),
            "base_z_mm":           prong_base_z,
            "angles_deg":          prong_angles,
            "style":               semantics.get("prong_style", "claw"),
            "orientation":         prong_g.get("orientation", "radial"),
        }

    # ── Bridge (if annotated) ─────────────────────────────────────────────────
    if br_g:
        ctx["bridge"] = {
            "height_mm":  round(max(0.8, float(br_g.get("height", 1.2))), 3),
            "base_z_mm":  round(band_top_z - 0.5, 3),
        }

    # ── Halo (if annotated) ───────────────────────────────────────────────────
    if halo_g:
        hs = _clamp(float(halo_g.get("width", 1.2)), "halo_stone")
        hr = (stone_width / 2.0) + (hs / 2.0) + 0.3
        hc = max(8, int((2 * 3.14159 * hr) / (hs + 0.2)))
        ctx["halo"] = {
            "stone_count":       hc,
            "stone_size_mm":     round(hs, 3),
            "radial_distance_mm": round(hr, 3),
            "base_z_mm":         round(stone_base_z, 3),
        }

    # ── Style from semantics ──────────────────────────────────────────────────
    ctx["style"] = {
        "ring_style":   semantics.get("ring_style",   "Solitaire"),
        "setting_type": semantics.get("setting_type", "Prong"),
        "shank_style":  semantics.get("shank_style",  "Plain"),
        "symmetry":     semantics.get("symmetry",     "Bilateral"),
        "prong_style":  semantics.get("prong_style",  "claw"),
    }

    # ── Meta (for validator) ──────────────────────────────────────────────────
    ctx["_meta"] = geometry.get("meta", {})

    logger.info(
        f"GeometryContext built — "
        f"band_outer={outer_r:.2f}mm, stone={stone_width:.2f}×{stone_height:.2f}mm, "
        f"stone_base_z={stone_base_z:.2f}mm, "
        f"components={[k for k in ctx if not k.startswith('_') and k not in ('band','center_stone','z_stack','style')]}"
    )
    return ctx