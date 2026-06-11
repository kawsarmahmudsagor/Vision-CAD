"""
codegen_service.py
──────────────────────────────────────────────────────────────────────────────
Code generation service.

Key change vs original:
  The user message now contains a GEOMETRY CONTEXT block (from COCO) and a
  CONSTRAINTS block in addition to the prose description.  The LLM is
  instructed to treat these as ground truth and must encode them as OpenSCAD
  parameters verbatim — it must NOT invent its own dimensions.

Resilience additions:
  - generate_scad_code() retries the Ollama call up to MAX_CODEGEN_RETRIES
    times on transient HTTP errors (502/503/504) and network failures,
    with exponential backoff.  On total exhaustion it returns "" so the
    caller can decide what to do rather than crashing the pipeline.
  - generate_title() already had a bare try/except — unchanged.
"""

import asyncio
import base64
import logging

import httpx

from config import get_settings
from prompts import STRICT_CODE_PROMPT
from tools import strip_code_fences, extract_openscad_from_text

logger = logging.getLogger(__name__)

# ── Retry config ──────────────────────────────────────────────────────────────
MAX_CODEGEN_RETRIES  = 5      # total attempts (1 original + 2 retries)
_RETRY_BASE_DELAY    = 2.0    # seconds; doubles each attempt
# HTTP status codes that are worth retrying (transient upstream errors)
_RETRYABLE_STATUSES  = {502, 503, 504}


def _format_geometry_block(geo_ctx: dict | None, constraints: list | None) -> str:
    """Render geometry context + constraints as a structured prompt section."""
    if not geo_ctx:
        return ""

    band  = geo_ctx.get("band", {})
    stone = geo_ctx.get("center_stone", {})
    zs    = geo_ctx.get("z_stack", {})

    inner_r    = band.get("inner_radius_mm", 8.5)
    outer_r    = band.get("outer_radius_mm", 10.3)
    band_thick = band.get("thickness_mm",    1.8)
    band_width = band.get("width_mm",        2.5)
    stone_w    = stone.get("width_mm",       6.0)
    stone_h    = stone.get("height_mm",      3.8)
    setting_h  = round(stone_h + 1.5, 3)

    lines = [
        "",
        "═══════════════════════════════════════════════════",
        "GEOMETRY CONTEXT (from COCO annotations — GROUND TRUTH)",
        "These values are measured from the actual ring annotation.",
        "You MUST use them as your OpenSCAD parameter values.",
        "Do NOT invent or estimate any dimension listed here.",
        "═══════════════════════════════════════════════════",
        "",
        "BAND:",
        f"  inner_radius     = {inner_r}  // mm",
        f"  outer_radius     = {outer_r}  // mm  (= inner_radius + thickness)",
        f"  thickness        = {band_thick}  // mm  (radial wall)",
        f"  width            = {band_width}  // mm  (finger-axis depth of band)",
        "",
        "CENTER STONE (all heights are LOCAL — 0 = pavilion tip, positive = upward):",
        f"  cut              = \"{stone.get('cut', 'round')}\"",
        f"  width            = {stone_w}  // mm",
        f"  height           = {stone_h}  // mm  (local Z: 0 → {stone_h})",
        f"  setting_height   = {setting_h}  // mm  (total module height incl. prong tips)",
        "",
        "═══════════════════════════════════════════════════",
        "MANDATORY RING ASSEMBLY PATTERN",
        "═══════════════════════════════════════════════════",
        "The ring bore runs along Z. Wrap the full assembly in rotate([90,0,0])",
        "so it displays upright. INSIDE that rotate block:",
        "",
        "  1. ring_band()   — rotate_extrude in XY plane, bore along Z",
        "",
        "  2. Stone setting — ALWAYS placed like this (NO exceptions):",
        f"       translate([0, {outer_r}, 0])   // top of band in ring-local space",
        "       rotate([-90, 0, 0])              // tip tower outward along +Y",
        "       stone_setting_module();",
        "",
        "  Inside stone_setting_module(), ALL Z is LOCAL (0 = base, up = positive):",
        f"       gallery / basket  : local Z  0  →  {round(stone_h*0.4,2)}",
        f"       stone pavilion tip: local Z  0  (translate([0,0,0]))",
        f"       stone table       : local Z  {stone_h}",
        f"       prong tips        : local Z  {round(stone_h+0.8,2)}",
        "",
        "  NEVER use band_top_z, stone_base_z, or stone_top_z as absolute Z values.",
        "  NEVER place the stone at translate([0,0,stone_base_z]) in the main assembly.",
        "  ALL stone/prong heights are offsets from the base of stone_setting_module().",
        "═══════════════════════════════════════════════════",
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

    # ── Semantic construction recipes ─────────────────────────────────────────
    recipes = geo_ctx.get("_recipes")
    if not recipes:
        from semantic_recipe import build_semantic_recipes
        recipes = build_semantic_recipes(geo_ctx)
    lines.append(recipes)

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
    user_prompt:        str,
    vision_description: str,
    image_bytes:        bytes | None = None,
    media_type:         str = "image/jpeg",
    base_code:          str | None = None,
    error:              str | None = None,
    geo_ctx:            dict | None = None,
    constraints:        list | None = None,
    adjustments:        dict | None = None,
) -> str:
    """
    Generate OpenSCAD code via Ollama.

    Returns the generated code string, or "" on total failure (all retries
    exhausted).  Never raises — the caller handles the empty-string case.
    """
    settings = get_settings()

    geometry_block   = _format_geometry_block(geo_ctx, constraints)
    adjustment_block = _format_adjustment_block(adjustments)

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

    last_exc: Exception | None = None

    for attempt in range(1, MAX_CODEGEN_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/chat", json=payload
                )

            # Retry on transient gateway / overload errors
            if resp.status_code in _RETRYABLE_STATUSES:
                raise httpx.HTTPStatusError(
                    f"Upstream returned {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )

            resp.raise_for_status()   # non-retryable 4xx → propagate immediately

            raw  = resp.json()["message"]["content"].strip()
            code = strip_code_fences(raw).strip()
            if not code or len(code) < 20:
                code = extract_openscad_from_text(raw) or code

            if code and len(code) >= 20:
                return code

            # LLM returned something too short — log and retry
            logger.warning(
                f"[codegen attempt {attempt}/{MAX_CODEGEN_RETRIES}] "
                f"Response too short ({len(code)} chars) — retrying"
            )
            last_exc = ValueError(f"Generated code too short: {len(code)} chars")

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            if status not in _RETRYABLE_STATUSES:
                logger.error(f"[codegen] Non-retryable HTTP {status} — aborting")
                return ""
            logger.warning(
                f"[codegen attempt {attempt}/{MAX_CODEGEN_RETRIES}] "
                f"HTTP {status} from Ollama — retrying"
            )
            last_exc = exc

        except (httpx.TransportError, httpx.TimeoutException) as exc:
            logger.warning(
                f"[codegen attempt {attempt}/{MAX_CODEGEN_RETRIES}] "
                f"Network error: {exc} — retrying"
            )
            last_exc = exc

        except Exception as exc:
            logger.error(f"[codegen] Unexpected error: {exc}")
            return ""

        # Exponential back-off before next attempt (skip after last)
        if attempt < MAX_CODEGEN_RETRIES:
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info(f"[codegen] Waiting {delay:.1f}s before retry {attempt + 1}...")
            await asyncio.sleep(delay)

    logger.error(
        f"[codegen] All {MAX_CODEGEN_RETRIES} attempts failed. Last error: {last_exc}"
    )
    return ""


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