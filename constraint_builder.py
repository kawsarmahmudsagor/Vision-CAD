"""
constraint_builder.py
──────────────────────────────────────────────────────────────────────────────
Derives named spatial constraints from the geometry context.

These are far more valuable to the LLM than raw coordinates because they
describe *relationships*, not absolute positions.  The LLM can then write
OpenSCAD code that encodes these relationships as derived parameters, making
the model self-consistent when any base parameter changes.

Constraint types:
    centered        — object A is centred relative to object B
    inside          — object A sits geometrically inside object B
    touching        — objects share a surface
    symmetric       — radially or bilaterally symmetric
    stacked_above   — A base sits at B top (tight vertical adjacency)
    supported_by    — A is structurally held up by B

Output: list of constraint dicts consumed by codegen_service prompt builder.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _has(ctx: dict, key: str) -> bool:
    return key in ctx and ctx[key] is not None


def build_constraints(geo_ctx: dict) -> list[dict]:
    """
    Analyse geometry context and return a list of named constraint dicts.

    Each constraint:
    {
        "type":    str,             # constraint class
        "objects": [str, str],      # which components
        "axis":    str | None,      # "X" | "Y" | "Z" | "XY" | "XZ" | "radial"
        "note":    str              # human-readable explanation for the LLM
    }
    """
    constraints = []
    band    = geo_ctx.get("band", {})
    stone   = geo_ctx.get("center_stone", {})
    prongs  = geo_ctx.get("prongs",  None)
    gallery = geo_ctx.get("gallery", None)
    halo    = geo_ctx.get("halo",    None)
    bridge  = geo_ctx.get("bridge",  None)
    zstack  = geo_ctx.get("z_stack", {})

    outer_r     = band.get("outer_radius_mm", 10.3)
    stone_base_z = stone.get("base_z_mm", outer_r)
    stone_r      = stone.get("radius_mm",  3.0)

    # ── 1. Stone is centred on ring axis ──────────────────────────────────────
    constraints.append({
        "type":    "centered",
        "objects": ["center_stone", "band"],
        "axis":    "XY",
        "note":    "Stone centre is on the ring's rotational axis (X=0, Y=0 in OpenSCAD bore-along-Z orientation).",
    })

    # ── 2. Stone sits above band top ──────────────────────────────────────────
    constraints.append({
        "type":    "stacked_above",
        "objects": ["center_stone", "band"],
        "axis":    "Z",
        "note":    f"Stone base Z = {stone_base_z:.2f} mm, band top Z = {outer_r:.2f} mm. "
                   f"Stone must clear the band by {stone_base_z - outer_r:.2f} mm.",
    })

    # ── 3. Gallery (if present) bridges band top to stone base ───────────────
    if gallery and gallery.get("mode") == "explicit":
        gal_h = gallery.get("height_mm", 0.0)
        constraints.append({
            "type":    "touching",
            "objects": ["gallery", "band"],
            "axis":    "Z",
            "note":    f"Gallery base touches band top at Z={outer_r:.2f} mm.",
        })
        constraints.append({
            "type":    "touching",
            "objects": ["gallery", "center_stone"],
            "axis":    "Z",
            "note":    f"Gallery top (Z={outer_r + gal_h:.2f} mm) is the stone seat — stone base rests here.",
        })

    # ── 4. Prongs grip the stone at its girdle ─────────────────────────────────
    if prongs:
        pd = prongs.get("radial_distance_mm", stone_r)
        constraints.append({
            "type":    "touching",
            "objects": ["prongs", "center_stone"],
            "axis":    "radial",
            "note":    f"Prong shafts are at radial distance {pd:.2f} mm from centre — "
                       f"equal to stone radius {stone_r:.2f} mm. Tips curve over the girdle.",
        })
        constraints.append({
            "type":    "symmetric",
            "objects": ["prongs"],
            "axis":    "radial",
            "note":    f"{prongs.get('count', 4)} prongs distributed at angles {prongs.get('angles_deg')}° "
                       f"around the stone — radially symmetric.",
        })
        constraints.append({
            "type":    "supported_by",
            "objects": ["center_stone", "prongs"],
            "axis":    "Z",
            "note":    "Prong tips define the stone seat; stone base Z is derived from prong height + base.",
        })

    # ── 5. Halo surrounds stone ───────────────────────────────────────────────
    if halo:
        hr = halo.get("radial_distance_mm", stone_r + 1.5)
        constraints.append({
            "type":    "symmetric",
            "objects": ["halo", "center_stone"],
            "axis":    "radial",
            "note":    f"Halo stones orbit at {hr:.2f} mm from centre, encircling the stone.",
        })
        constraints.append({
            "type":    "centered",
            "objects": ["halo", "center_stone"],
            "axis":    "XY",
            "note":    "Halo shares the same XY centre as the stone (co-axial).",
        })

    # ── 6. Bridge (if present) reinforces gallery underside ───────────────────
    if bridge:
        constraints.append({
            "type":    "touching",
            "objects": ["bridge", "band"],
            "axis":    "Z",
            "note":    f"Bridge base is flush with / slightly below band top at Z≈{outer_r - 0.5:.2f} mm.",
        })

    # ── 7. Overall ring symmetry ──────────────────────────────────────────────
    constraints.append({
        "type":    "symmetric",
        "objects": ["band"],
        "axis":    "bilateral",
        "note":    "Ring is bilaterally symmetric about the XZ plane (finger axis = Y).",
    })

    logger.info(f"Built {len(constraints)} constraints for geometry context")
    return constraints