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


# ── helpers ───────────────────────────────────────────────────────────────────

async def _build_model_with_coco(
    user_prompt:   str,
    vision_description: str,
    semantics:     dict,
    image_bytes:   bytes | None,
    media_type:    str,
    coco_path:     str,
    base_code:     str | None,
    error:         str | None,
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
    scad_code        = base_code
    validation_report = None
    adjustments      = None
    output_dir       = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)

    for iteration in range(1, settings.max_refinement_iterations + 1):
        logger.info(f"[Iteration {iteration}/{settings.max_refinement_iterations}] Generating OpenSCAD...")

        scad_code = await generate_scad_code(
            user_prompt=effective_prompt,
            vision_description=vision_description or effective_prompt,
            image_bytes=image_bytes,
            media_type=media_type,
            base_code=scad_code if iteration > 1 else None,
            error=effective_error,
            geo_ctx=geo_ctx,
            constraints=constraints,
            adjustments=adjustments,
        )

        if not scad_code or len(scad_code.strip()) < 20:
            raise HTTPException(status_code=502, detail="Code generation returned invalid OpenSCAD.")

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
        # Apply deltas to geo_ctx for next iteration
        for comp, params in adjustments.get("geometry", {}).items():
            for param_key, delta in params.items():
                # Strip "_delta_mm" suffix to find the real param name
                real_key = param_key.replace("_delta_mm", "_mm")
                if comp in geo_ctx and real_key in geo_ctx[comp]:
                    geo_ctx[comp][real_key] = round(geo_ctx[comp][real_key] + delta, 3)
                    logger.info(f"  Adjusted geo_ctx[{comp}][{real_key}] by {delta:+.3f}")

    # ── 8. Final save + response ──────────────────────────────────────────────
    title     = await generate_title(vision_description or effective_prompt, effective_prompt)
    file_path = save_scad_file(scad_code, title)

    return GenerateResponse(
        title=title,
        scad_code=scad_code,
        scad_file_path=file_path,
        parameters=parse_parameters(scad_code),
        description=vision_description or "",
        message=agent_text or f"Generated parametric ring model: {title}",
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
    Behaviour identical to Vision-CAD v1.
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
    if not scad_code or len(scad_code.strip()) < 20:
        raise HTTPException(status_code=502, detail="Code generation returned empty or invalid OpenSCAD code.")

    title     = await generate_title(vision_description or effective_prompt, effective_prompt)
    file_path = save_scad_file(scad_code, title)
    return GenerateResponse(
        title=title, scad_code=scad_code, scad_file_path=file_path,
        parameters=parse_parameters(scad_code), description=vision_description or "",
        message=agent_text or f"Generated model: {title}",
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
    """
    image_bytes = await image.read()
    media_type  = image.content_type or "image/jpeg"

    try:
        vision_description = await describe_image(image_bytes, media_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vision model error: {exc}")

    # Extract structured semantics separately (new)
    try:
        semantics = await extract_semantics(image_bytes, media_type)
    except Exception:
        semantics = {}

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
        raise HTTPException(status_code=500, detail=str(exc))


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
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/apply-parameters", response_model=ApplyParametersResponse, summary="Patch parameters in SCAD")
async def apply_parameters(body: ApplyParametersRequest):
    updates  = [u.model_dump() for u in body.updates]
    patched  = apply_parameter_patch(body.scad_code, updates)
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