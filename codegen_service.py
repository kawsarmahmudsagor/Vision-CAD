"""
codegen_service.py
──────────────────────────────────────────────────────────────────────────────
Code generation service.

Key change vs original:
  The user message now contains a GEOMETRY CONTEXT block (from COCO) and a
  CONSTRAINTS block in addition to the prose description.  The LLM is
  instructed to treat these as ground truth and must encode them as OpenSCAD
  parameters verbatim — it must NOT invent its own dimensions.
"""

import base64
import json
import logging
import httpx
from config import get_settings
from prompts import STRICT_CODE_PROMPT
from tools import strip_code_fences, extract_openscad_from_text

logger = logging.getLogger(__name__)


def _format_geometry_block(geo_ctx: dict | None, constraints: list | None) -> str:
    """Render geometry context + constraints as a structured prompt section."""
    if not geo_ctx:
        return ""

    lines = [
        "",
        "═══════════════════════════════════════════════════",
        "GEOMETRY CONTEXT (from COCO annotations — GROUND TRUTH)",
        "These values are measured from the actual ring annotation.",
        "You MUST use them as your OpenSCAD parameter values.",
        "Do NOT invent or estimate any dimension listed here.",
        "═══════════════════════════════════════════════════",
    ]

    band  = geo_ctx.get("band", {})
    stone = geo_ctx.get("center_stone", {})
    zs    = geo_ctx.get("z_stack", {})

    lines += [
        f"",
        f"BAND:",
        f"  inner_radius     = {band.get('inner_radius_mm', 8.5)}  // mm",
        f"  outer_radius     = {band.get('outer_radius_mm', 10.3)}  // mm",
        f"  thickness        = {band.get('thickness_mm', 1.8)}  // mm",
        f"  width            = {band.get('width_mm', 2.5)}  // mm (finger-axis depth)",
        f"",
        f"CENTER STONE:",
        f"  cut              = \"{stone.get('cut', 'round')}\"",
        f"  width            = {stone.get('width_mm', 6.0)}  // mm (diameter for round)",
        f"  height           = {stone.get('height_mm', 3.8)}  // mm (pavilion tip to table)",
        f"  base_z           = {stone.get('base_z_mm', 10.3)}  // mm (world Z of pavilion tip)",
        f"",
        f"Z STACK (world Z, ring centre = 0):",
        f"  band_top_z       = {zs.get('band_top_z', 10.3)}  // where band metal ends",
        f"  stone_base_z     = {zs.get('stone_base_z', 10.3)}  // pavilion tip Z",
        f"  stone_top_z      = {zs.get('stone_top_z', 14.1)}  // table Z",
    ]

    for key in ("gallery", "prongs", "halo", "bridge"):
        comp = geo_ctx.get(key)
        if not comp:
            continue
        mode = comp.get("mode", "")
        if mode == "inferred":
            lines.append(f"\n{key.upper()}: not annotated — use structural defaults")
            continue
        lines.append(f"\n{key.upper()}:")
        for k, v in comp.items():
            if k not in ("mode",):
                lines.append(f"  {k:<22} = {v}")

    style = geo_ctx.get("style", {})
    if style:
        lines += [
            "",
            "STYLE (from vision model):",
            f"  ring_style   = {style.get('ring_style',   'Solitaire')}",
            f"  setting_type = {style.get('setting_type', 'Prong')}",
            f"  shank_style  = {style.get('shank_style',  'Plain')}",
            f"  prong_style  = {style.get('prong_style',  'claw')}",
        ]

    if constraints:
        lines += ["", "SPATIAL CONSTRAINTS (encode these as derived OpenSCAD parameters):"]
        for c in constraints:
            lines.append(f"  [{c['type']}] {' + '.join(c['objects'])} → {c['note']}")

    lines.append("═══════════════════════════════════════════════════\n")
    return "\n".join(lines)


def _format_adjustment_block(adjustments: dict | None) -> str:
    """Format validator adjustment deltas as a correction instruction."""
    if not adjustments or not adjustments.get("geometry"):
        return ""

    lines = [
        "",
        "VALIDATION CORRECTIONS (apply these deltas to the current parameter values):",
    ]
    for comp, params in adjustments["geometry"].items():
        for param, delta in params.items():
            sign = "+" if delta >= 0 else ""
            lines.append(f"  {comp}.{param}: {sign}{delta:.3f} mm")
    lines.append("Regenerate the complete OpenSCAD file with the corrected values.\n")
    return "\n".join(lines)


async def generate_scad_code(
    user_prompt:       str,
    vision_description: str,
    image_bytes:       bytes | None = None,
    media_type:        str = "image/jpeg",
    base_code:         str | None = None,
    error:             str | None = None,
    geo_ctx:           dict | None = None,
    constraints:       list | None = None,
    adjustments:       dict | None = None,
) -> str:
    settings = get_settings()

    geometry_block    = _format_geometry_block(geo_ctx, constraints)
    adjustment_block  = _format_adjustment_block(adjustments)

    parts = [vision_description, geometry_block]

    if adjustment_block:
        parts.append(adjustment_block)
    elif base_code:
        parts.append(f"\nExisting code to refine:\n{base_code}")

    parts.append(f"\nUser request: {user_prompt}")

    if error:
        parts.append(f"\nFix this OpenSCAD error: {error}")

    user_text = "\n".join(parts)

    user_message: dict = {"role": "user", "content": user_text}
    if image_bytes:
        user_message["images"] = [base64.b64encode(image_bytes).decode()]

    payload = {
        "model": settings.code_model,
        "messages": [
            {"role": "system", "content": STRICT_CODE_PROMPT},
            user_message,
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 8192},
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
        resp.raise_for_status()

    raw  = resp.json()["message"]["content"].strip()
    code = strip_code_fences(raw).strip()
    if not code or len(code) < 20:
        code = extract_openscad_from_text(raw) or code
    return code


async def generate_title(description: str, user_prompt: str) -> str:
    settings = get_settings()
    from prompts import TITLE_PROMPT

    payload = {
        "model": settings.code_model,
        "messages": [
            {"role": "system", "content": TITLE_PROMPT},
            {"role": "user", "content": f"Object description: {description}\nUser request: {user_prompt}\nTitle:"},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 30},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
        import re
        title = resp.json()["message"]["content"].strip().strip('"\'')
        title = re.sub(r"^title:\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"[.!?:;,]+$", "", title).strip()
        return title[:27] if len(title) > 27 else (title if len(title) >= 2 else "Ring Model")
    except Exception:
        return "Ring Model"