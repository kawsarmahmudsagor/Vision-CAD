"""
generate.py
──────────────────────────────────────────────────────────────────────────────
Main API router — Vision-CAD v2.

New pipeline (image + COCO path):

    POST /generate (multipart: image + coco_path + prompt)
    ┌─────────────────────────────────────────────────────────┐
    │ 1. vision_service.describe_image()  → prose description │
    │ 2. vision_service.extract_semantics() → style dict      │
    │ 3. coco_parser.parse_ring_geometry() → physical dims    │
    │ 4. geometry_extractor.build_geometry_context()          │
    │ 5. constraint_builder.build_constraints()               │
    │ 6. agent_service.run_agent()                            │
    │ 7. ┌── Refinement loop (max N iterations) ──────────┐   │
    │    │  codegen_service.generate_scad_code()          │   │
    │    │  file_service.save_scad_file()                 │   │
    │    │  renderer.render_views()                       │   │
    │    │  validator.validate()                          │   │
    │    │  → if valid or max iters: break                │   │
    │    └─────────────────────────────────────────────────┘  │
    │ 8. Return GenerateResponse                              │
    └─────────────────────────────────────────────────────────┘

Legacy endpoint (image only, no COCO) still works — skips steps 3-5 and
the validation loop, behaving identically to the original Vision-CAD.

Resilience additions vs original:
  - Refinement loop never raises HTTPException mid-loop; bad codegen attempts
    are retried inline (up to CODEGEN_EMPTY_RETRIES extra attempts) before
    the loop continues with whatever previous-good code it has.
  - A minimal fallback SCAD skeleton is returned instead of a 502 when all
    attempts fail, so the client always receives a usable GenerateResponse.
  - All sub-pipeline errors are caught and logged; the pipeline degrades
    gracefully to the legacy path rather than 500-ing.
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse

from config import get_settings
from schemas import (
    GenerateResponse, GenerateRequest,
    ApplyParametersRequest, ApplyParametersResponse,
)
from vision_service import describe_image, extract_semantics
from agent_service import run_agent
from codegen_service import generate_scad_code, generate_title
from file_service import save_scad_file
from tools import parse_parameters, apply_parameter_patch

# New modules
from coco_parser import parse_ring_geometry
from geometry_extractor import build_geometry_context
from constraint_builder import build_constraints
from renderer import render_views
from validator import validate

logger = logging.getLogger(__name__)
router = APIRouter()

# How many times to retry codegen within a single loop iteration when it
# returns empty/invalid code (on top of the retries already inside
# generate_scad_code itself).
CODEGEN_EMPTY_RETRIES = 5

# Minimal fallback OpenSCAD returned when every attempt to generate real code
# fails.  It is valid, renderable, and carries a clear comment so the user
# knows something went wrong.
_FALLBACK_SCAD = """\
// Vision-CAD — fallback skeleton (code generation failed)
// The upstream model did not return valid OpenSCAD.
// Adjust the parameters below and regenerate.

ring_inner_diameter = 17.0;
band_width          = 3.0;
band_thickness      = 1.8;
metal_color         = "#C0C0C0";

inner_radius = ring_inner_diameter / 2;
outer_radius = inner_radius + band_thickness;

color(metal_color)
rotate_extrude($fn = 120)
translate([inner_radius, 0, 0])
square([band_thickness, band_width], center = true);
"""


# ── helpers ───────────────────────────────────────────────────────────────────

async def _safe_codegen(
    *,
    user_prompt: str,
    vision_description: str,
    image_bytes: bytes | None,
    media_type: str,
    base_code: str | None,
    error: str | None,
    geo_ctx: dict | None,
    constraints: list | None,
    adjustments: dict | None,
    iteration: int,
) -> str | None:
    """
    Call generate_scad_code with per-iteration empty-result retries.
    Returns the code string on success, or None if every attempt came back
    empty (generate_scad_code already exhausted its own HTTP retries).
    """
    for attempt in range(1, CODEGEN_EMPTY_RETRIES + 2):  # +2: 1 original + N retries
        code = await generate_scad_code(
            user_prompt=user_prompt,
            vision_description=vision_description,
            image_bytes=image_bytes,
            media_type=media_type,
            base_code=base_code if iteration > 1 else None,
            error=error,
            geo_ctx=geo_ctx,
            constraints=constraints,
            adjustments=adjustments,
        )
        if code and len(code.strip()) >= 20:
            return code
        logger.warning(
            f"[Iteration {iteration}, codegen attempt {attempt}] "
            f"Empty/invalid code returned — "
            f"{'retrying' if attempt <= CODEGEN_EMPTY_RETRIES else 'giving up'}"
        )
    return None


async def _build_model_with_coco(
    user_prompt:        str,
    vision_description: str,
    semantics:          dict,
    image_bytes:        bytes | None,
    media_type:         str,
    coco_path:          str,
    base_code:          str | None,
    error:              str | None,
) -> GenerateResponse:
    """
    Full pipeline: COCO-informed geometry + constraint-first generation
    + render/validate refinement loop.
    """
    settings = get_settings()

    # ── 3. Parse COCO geometry ────────────────────────────────────────────────
    try:
        geometry = parse_ring_geometry(
            coco_path,
            top_image_id=settings.top_image_id,
            side_image_id=settings.side_image_id,
        )
    except Exception as e:
        logger.error(f"COCO parse failed: {e} — falling back to no-COCO pipeline")
        return await _build_model_legacy(
            user_prompt, vision_description, image_bytes, media_type, base_code, error
        )

    # ── 4. Build geometry context ─────────────────────────────────────────────
    geo_ctx = build_geometry_context(geometry, semantics)

    # ── 5. Build constraints ──────────────────────────────────────────────────
    constraints = build_constraints(geo_ctx)

    # ── 6. Agent decides tool ─────────────────────────────────────────────────
    agent_result = await run_agent(
        user_text=user_prompt,
        vision_description=vision_description or None,
        base_code=base_code,
    )
    tool_name  = agent_result.get("tool_name")
    tool_args  = agent_result.get("tool_args") or {}
    agent_text = agent_result.get("text", "")

    if tool_name == "apply_parameter_changes" and base_code:
        patched   = apply_parameter_patch(base_code, tool_args.get("updates", []))
        title     = "Updated Model"
        file_path = save_scad_file(patched, title)
        return GenerateResponse(
            title=title, scad_code=patched, scad_file_path=file_path,
            parameters=parse_parameters(patched), description=vision_description or "",
            message=agent_text or "Parameters updated.",
            geometry_context=geo_ctx, constraints=constraints,
        )

    effective_prompt = tool_args.get("text", user_prompt)
    effective_error  = tool_args.get("error", error)

    # ── 7. Refinement loop ────────────────────────────────────────────────────
    scad_code         = base_code
    last_good_code    = base_code       # track last successfully generated code
    validation_report = None
    adjustments       = None
    output_dir        = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)
    degraded          = False           # set True if we fell back to skeleton

    for iteration in range(1, settings.max_refinement_iterations + 1):
        logger.info(f"[Iteration {iteration}/{settings.max_refinement_iterations}] Generating OpenSCAD...")

        new_code = await _safe_codegen(
            user_prompt=effective_prompt,
            vision_description=vision_description or effective_prompt,
            image_bytes=image_bytes,
            media_type=media_type,
            base_code=scad_code,
            error=effective_error,
            geo_ctx=geo_ctx,
            constraints=constraints,
            adjustments=adjustments,
            iteration=iteration,
        )

        if new_code:
            scad_code      = new_code
            last_good_code = new_code
        else:
            logger.error(
                f"[Iteration {iteration}] All codegen attempts returned empty. "
                f"{'Using previous good code.' if last_good_code else 'Using fallback skeleton.'}"
            )
            if last_good_code:
                scad_code = last_good_code
            else:
                scad_code = _FALLBACK_SCAD
                degraded  = True
            # No point running the validator on a skeleton — exit loop
            break

        # Save to disk so renderer can read it
        tmp_title = f"ring_iter{iteration}"
        scad_path = save_scad_file(scad_code, tmp_title)

        # ── Render + validate ─────────────────────────────────────────────────
        logger.info(f"[Iteration {iteration}] Rendering and validating...")
        try:
            validation_report = await validate(
                geometry=geometry,
                scad_path=scad_path,
                output_dir=output_dir,
                render_views_fn=render_views,
            )
        except Exception as e:
            logger.warning(f"Validation error on iteration {iteration}: {e}")
            break

        if validation_report.get("is_valid"):
            logger.info(f"[Iteration {iteration}] Validation passed.")
            break

        adjustments = validation_report.get("adjustments")
        if not adjustments or not adjustments.get("geometry"):
            logger.warning("Validator produced no adjustments — stopping loop.")
            break

        logger.info(f"[Iteration {iteration}] Adjustments: {adjustments}")
        for comp, params in adjustments.get("geometry", {}).items():
            for param_key, delta in params.items():
                real_key = param_key.replace("_delta_mm", "_mm")
                if comp in geo_ctx and real_key in geo_ctx[comp]:
                    geo_ctx[comp][real_key] = round(geo_ctx[comp][real_key] + delta, 3)
                    logger.info(f"  Adjusted geo_ctx[{comp}][{real_key}] by {delta:+.3f}")

    # ── 8. Final save + response ──────────────────────────────────────────────
    title     = await generate_title(vision_description or effective_prompt, effective_prompt)
    file_path = save_scad_file(scad_code, title)

    status_msg = (
        "⚠️ Code generation failed after all retries — returning a minimal skeleton. "
        "Check the Ollama service and retry."
        if degraded
        else (agent_text or f"Generated parametric ring model: {title}")
    )

    return GenerateResponse(
        title=title,
        scad_code=scad_code,
        scad_file_path=file_path,
        parameters=parse_parameters(scad_code),
        description=vision_description or "",
        message=status_msg,
        geometry_context=geo_ctx,
        constraints=constraints,
        validation_report=validation_report,
        iterations=settings.max_refinement_iterations,
    )


async def _build_model_legacy(
    user_prompt:        str,
    vision_description: str,
    image_bytes:        bytes | None,
    media_type:         str,
    base_code:          str | None,
    error:              str | None,
) -> GenerateResponse:
    """
    Original single-pass pipeline — used when no COCO file is provided.
    Behaviour identical to Vision-CAD v1, but now returns a fallback skeleton
    instead of raising a 502 when codegen fails.
    """
    agent_result = await run_agent(
        user_text=user_prompt,
        vision_description=vision_description or None,
        base_code=base_code,
    )
    tool_name  = agent_result.get("tool_name")
    tool_args  = agent_result.get("tool_args") or {}
    agent_text = agent_result.get("text", "")

    if tool_name == "apply_parameter_changes" and base_code:
        patched   = apply_parameter_patch(base_code, tool_args.get("updates", []))
        title     = "Updated Model"
        file_path = save_scad_file(patched, title)
        return GenerateResponse(
            title=title, scad_code=patched, scad_file_path=file_path,
            parameters=parse_parameters(patched), description=vision_description or "",
            message=agent_text or "Parameters updated.",
        )

    effective_prompt = tool_args.get("text", user_prompt)
    effective_base   = tool_args.get("base_code", base_code)
    effective_error  = tool_args.get("error", error)

    scad_code = await generate_scad_code(
        user_prompt=effective_prompt,
        vision_description=vision_description or effective_prompt,
        image_bytes=image_bytes,
        media_type=media_type,
        base_code=effective_base,
        error=effective_error,
    )

    degraded = False
    if not scad_code or len(scad_code.strip()) < 20:
        logger.error("Legacy pipeline: codegen returned empty code — using fallback skeleton")
        scad_code = _FALLBACK_SCAD
        degraded  = True

    title     = await generate_title(vision_description or effective_prompt, effective_prompt)
    file_path = save_scad_file(scad_code, title)

    status_msg = (
        "⚠️ Code generation failed after all retries — returning a minimal skeleton. "
        "Check the Ollama service and retry."
        if degraded
        else (agent_text or f"Generated model: {title}")
    )

    return GenerateResponse(
        title=title, scad_code=scad_code, scad_file_path=file_path,
        parameters=parse_parameters(scad_code), description=vision_description or "",
        message=status_msg,
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse, summary="Generate SCAD from image + optional COCO")
async def generate_from_image(
    image:     UploadFile = File(..., description="Image of the ring to model"),
    prompt:    str  = Form(default="Create a parametric 3D model of this ring."),
    coco_path: str  = Form(default=None,  description="Server path to COCO annotation JSON file"),
    base_code: str  = Form(default=None),
    error:     str  = Form(default=None),
):
    """
    Full pipeline:
    - With coco_path: COCO geometry extraction → constraint builder → generation → render → validate → refine
    - Without coco_path: original single-pass Vision-CAD behaviour
    In both cases a valid GenerateResponse is always returned; a 502 is never
    raised — failure information is surfaced in the `message` field instead.
    """
    image_bytes = await image.read()
    media_type  = image.content_type or "image/jpeg"

    # Vision description — hard failure is still a 502 (the image itself is needed)
    try:
        vision_description = await describe_image(image_bytes, media_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vision model error: {exc}")

    # Semantic extraction — soft failure (empty dict is fine)
    try:
        semantics = await extract_semantics(image_bytes, media_type)
    except Exception:
        semantics = {}

    # Pipeline — always returns a GenerateResponse; never raises 502
    try:
        if coco_path and Path(coco_path).exists():
            return await _build_model_with_coco(
                user_prompt=prompt,
                vision_description=vision_description,
                semantics=semantics,
                image_bytes=image_bytes,
                media_type=media_type,
                coco_path=coco_path,
                base_code=base_code,
                error=error,
            )
        else:
            if coco_path:
                logger.warning(f"COCO path provided but not found: {coco_path} — using legacy pipeline")
            return await _build_model_legacy(
                user_prompt=prompt,
                vision_description=vision_description,
                image_bytes=image_bytes,
                media_type=media_type,
                base_code=base_code,
                error=error,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unhandled pipeline error: {exc}")
        # Last-resort: return the fallback skeleton rather than a 500
        title     = "Ring Model"
        file_path = save_scad_file(_FALLBACK_SCAD, title)
        return GenerateResponse(
            title=title,
            scad_code=_FALLBACK_SCAD,
            scad_file_path=file_path,
            parameters=parse_parameters(_FALLBACK_SCAD),
            description=vision_description or "",
            message=f"⚠️ Unexpected pipeline error: {exc}. Returning fallback skeleton.",
        )


@router.post("/generate/text", response_model=GenerateResponse, summary="Generate SCAD from text only")
async def generate_from_text(body: GenerateRequest):
    """Text-only pipeline — no image, no COCO."""
    try:
        return await _build_model_legacy(
            user_prompt=body.prompt,
            vision_description="",
            image_bytes=None,
            media_type="image/jpeg",
            base_code=body.base_code,
            error=body.error,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Text pipeline error: {exc}")
        title     = "Ring Model"
        file_path = save_scad_file(_FALLBACK_SCAD, title)
        return GenerateResponse(
            title=title,
            scad_code=_FALLBACK_SCAD,
            scad_file_path=file_path,
            parameters=parse_parameters(_FALLBACK_SCAD),
            description="",
            message=f"⚠️ Unexpected pipeline error: {exc}. Returning fallback skeleton.",
        )


@router.post("/apply-parameters", response_model=ApplyParametersResponse, summary="Patch parameters in SCAD")
async def apply_parameters(body: ApplyParametersRequest):
    updates   = [u.model_dump() for u in body.updates]
    patched   = apply_parameter_patch(body.scad_code, updates)
    file_path = save_scad_file(patched, "updated_model")
    return ApplyParametersResponse(
        scad_code=patched,
        scad_file_path=file_path,
        parameters=parse_parameters(patched),
    )


@router.get("/download/{filename}", summary="Download a generated .scad file")
async def download_scad(filename: str):
    settings  = get_settings()
    file_path = Path(settings.output_dir) / filename
    if not file_path.exists() or file_path.suffix != ".scad":
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path), media_type="application/octet-stream", filename=filename)


@router.get("/health")
async def health():
    return {"status": "ok"}