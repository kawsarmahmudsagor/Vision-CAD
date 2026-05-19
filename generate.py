"""
Main API router.

POST /generate          — multipart: image file + optional prompt
POST /generate/text     — JSON: text prompt only (no image)
POST /apply-parameters  — JSON: patch param values in existing SCAD code
GET  /download/{filename} — download a .scad file
"""
import os
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse

from config import get_settings
from schemas import (
    GenerateResponse,
    GenerateRequest,
    ApplyParametersRequest,
    ApplyParametersResponse,
)
from vision_service import describe_image
from agent_service import run_agent
from codegen_service import generate_scad_code, generate_title
from file_service import save_scad_file
from tools import parse_parameters, apply_parameter_patch

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

async def _build_model(
    user_prompt: str,
    vision_description: str,
    image_bytes: bytes | None,
    media_type: str,
    base_code: str | None,
    error: str | None,
) -> GenerateResponse:
    """Shared logic for both image and text-only generation."""

    # ── Call 1b: agent decides what tool to call ──────────────────────────────
    agent_result = await run_agent(
        user_text=user_prompt,
        vision_description=vision_description or None,
        base_code=base_code,
    )

    tool_name = agent_result.get("tool_name")
    tool_args = agent_result.get("tool_args") or {}
    agent_text = agent_result.get("text", "")

    # ── Handle apply_parameter_changes (no code-gen needed) ──────────────────
    if tool_name == "apply_parameter_changes" and base_code:
        updates = tool_args.get("updates", [])
        patched = apply_parameter_patch(base_code, updates)
        title = "Updated Model"
        file_path = save_scad_file(patched, title)
        return GenerateResponse(
            title=title,
            scad_code=patched,
            scad_file_path=file_path,
            parameters=parse_parameters(patched),
            description=vision_description or "",
            message=agent_text or "Parameters updated.",
        )

    # ── Handle build_parametric_model (or fallback) ───────────────────────────
    # Use tool args if available, otherwise fall back to raw inputs
    effective_prompt = tool_args.get("text", user_prompt)
    effective_base = tool_args.get("base_code", base_code)
    effective_error = tool_args.get("error", error)

    # ── Call 2: generate OpenSCAD code ────────────────────────────────────────
    scad_code = await generate_scad_code(
        user_prompt=effective_prompt,
        vision_description=vision_description or effective_prompt,
        image_bytes=image_bytes,
        media_type=media_type,
        base_code=effective_base,
        error=effective_error,
    )

    if not scad_code or len(scad_code.strip()) < 20:
        raise HTTPException(
            status_code=502,
            detail="Code generation returned empty or invalid OpenSCAD code.",
        )

    # ── Generate title + save file ────────────────────────────────────────────
    title = await generate_title(
        description=vision_description or effective_prompt,
        user_prompt=effective_prompt,
    )
    file_path = save_scad_file(scad_code, title)
    params = parse_parameters(scad_code)

    return GenerateResponse(
        title=title,
        scad_code=scad_code,
        scad_file_path=file_path,
        parameters=params,
        description=vision_description or "",
        message=agent_text or f"I've generated a parametric model for: {effective_prompt}",
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse, summary="Generate SCAD from image")
async def generate_from_image(
    image: UploadFile = File(..., description="Image of the object to model"),
    prompt: str = Form(default="Create a parametric 3D model of this object."),
    base_code: str = Form(default=None),
    error: str = Form(default=None),
):
    """
    Full pipeline:
    1. Vision model (qwen3-vl:8b) describes the image.
    2. Agent (gpt-4o) decides which tool to call.
    3. Code-gen model (qwen3-vl:8b) produces OpenSCAD code.
    4. .scad file is saved to disk.
    """
    image_bytes = await image.read()
    media_type = image.content_type or "image/jpeg"

    # ── Call 1: vision description ────────────────────────────────────────────
    try:
        vision_description = await describe_image(image_bytes, media_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vision model error: {exc}")

    try:
        return await _build_model(
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
    """
    Text-only pipeline (no image):
    1. Agent (gpt-4o) decides which tool to call.
    2. Code-gen model (qwen3-vl:8b) produces OpenSCAD code.
    3. .scad file is saved to disk.
    """
    try:
        return await _build_model(
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


@router.post("/apply-parameters", response_model=ApplyParametersResponse, summary="Patch parameters in SCAD code")
async def apply_parameters(body: ApplyParametersRequest):
    """
    Deterministically patch named parameter values in existing OpenSCAD code.
    Mirrors apply_parameter_changes tool logic from index.ts.
    """
    updates = [u.model_dump() for u in body.updates]
    patched = apply_parameter_patch(body.scad_code, updates)
    file_path = save_scad_file(patched, "updated_model")
    return ApplyParametersResponse(
        scad_code=patched,
        scad_file_path=file_path,
        parameters=parse_parameters(patched),
    )


@router.get("/download/{filename}", summary="Download a generated .scad file")
async def download_scad(filename: str):
    settings = get_settings()
    file_path = Path(settings.output_dir) / filename
    if not file_path.exists() or file_path.suffix != ".scad":
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename,
    )


@router.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}
