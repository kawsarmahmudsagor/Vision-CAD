"""
Main API router.

POST /generate                  — multipart: image file + optional prompt
POST /generate/text             — JSON: text prompt only (no image)
POST /apply-parameters          — JSON: patch param values in existing SCAD code
POST /refine-iterative          — JSON: iterative SCAD refinement against reference image
GET  /download/{filename}       — download a .scad file

The `provider` field controls which vision model is used:
  - "ollama"       — local Ollama vision model (default)
  - "huggingface"  — HuggingFace Inference API vision model

Code generation always uses Ollama regardless of provider.

ITERATIVE REFINEMENT PIPELINE
==============================
The /refine-iterative endpoint implements a feedback loop:
  1. Render current SCAD code to PNG (OpenSCAD preview)
  2. Vision model compares PNG vs input reference image
  3. Vision model provides specific feedback on what to change
  4. Code model refines SCAD based on visual feedback
  5. Repeat steps 1-4 until the model is satisfied (>confidence threshold)
  6. Return final SCAD code + all feedback history

This enables iterative refinement where the model continuously improves the
generated CAD code until it matches the reference image.
"""
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
import base64

from config import get_settings
from schemas import (
    GenerateResponse,
    GenerateRequest,
    ApplyParametersRequest,
    ApplyParametersResponse,
    IterativeRefinementRequest,
    IterativeRefinementResponse,
)
from vision_service import describe_image
from agent_service import run_agent
from codegen_service import generate_scad_code, generate_title
from file_service import save_scad_file
from tools import parse_parameters, apply_parameter_patch
from refinement_service import refine_until_satisfied
from image_memory import store_image, get_image

router = APIRouter()

VALID_PROVIDERS = ("ollama", "huggingface")


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
    effective_prompt = tool_args.get("text", user_prompt)
    effective_base   = tool_args.get("base_code", base_code)
    effective_error  = tool_args.get("error", error)

    # ── Call 2: generate OpenSCAD code (always Ollama) ────────────────────────
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
    provider: str = Form(
        default="ollama",
        description="Vision model provider: 'ollama' or 'huggingface'. Code generation always uses Ollama.",
    ),
    image_key: str = Form(default=None, description="Optional key to persist the uploaded image for later refinement."),
    refine: bool = Form(default=True, description="Run iterative refinement after initial generation when an image is provided."),
    max_iterations: int = Form(default=10, description="Maximum number of refinement iterations."),
    confidence_threshold: float = Form(default=0.75, description="Confidence threshold to stop refinement."),
):
    """
    Full pipeline:
    1. Vision model describes the image  (Ollama or HuggingFace — chosen by `provider`).
    2. Agent (gpt-4o) decides which tool to call.
    3. Code-gen model produces OpenSCAD code  (always Ollama).
    4. .scad file is saved to disk.
    """
    if provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"provider must be one of {VALID_PROVIDERS}",
        )

    image_bytes = await image.read()
    media_type = image.content_type or "image/jpeg"
    image_key = store_image(image_bytes, image_key)

    try:
        vision_description = await describe_image(image_bytes, media_type, provider=provider)
    except Exception as exc:
        detail = str(exc) or repr(exc)
        raise HTTPException(status_code=502, detail=f"Vision model error: {detail}")

    try:
        result = await _build_model(
            user_prompt=prompt,
            vision_description=vision_description,
            image_bytes=image_bytes,
            media_type=media_type,
            base_code=base_code,
            error=error,
        )

        if image_bytes and refine:
            try:
                refinement = await refine_until_satisfied(
                    input_image_bytes=image_bytes,
                    initial_scad_code=result.scad_code,
                    vision_description=vision_description,
                    user_prompt=prompt,
                    max_iterations=max_iterations,
                    confidence_threshold=confidence_threshold,
                )
                refined_code = refinement["final_scad_code"]
                refined_path = save_scad_file(refined_code, "refined_model")
                response_data = result.model_dump()
                response_data.pop("image_key", None)
                response_data.update(
                    {
                        "initial_scad_code": result.scad_code,
                        "scad_code": refined_code,
                        "scad_file_path": refined_path,
                        "refined": True,
                        "refinement_iterations": refinement["iterations"],
                        "refinement_satisfied": refinement["satisfied"],
                        "refinement_feedback_history": refinement["feedback_history"],
                        "refinement_render_history": refinement["render_history"],
                        "final_png_base64": base64.b64encode(refinement["final_png_bytes"]).decode()
                        if refinement.get("final_png_bytes")
                        else None,
                        "message": (
                            result.message
                            + f" Refinement completed in {refinement['iterations']} iterations."
                        ),
                    }
                )
                return GenerateResponse(**response_data, image_key=image_key)
            except Exception as exc:
                response_data = result.model_dump()
                response_data.pop("image_key", None)
                response_data.update(
                    {
                        "refined": False,
                        "message": result.message + f" Refinement failed: {exc}",
                    }
                )
                return GenerateResponse(**response_data, image_key=image_key)

        response_data = result.model_dump()
        response_data.pop("image_key", None)
        return GenerateResponse(**response_data, image_key=image_key)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate/text", response_model=GenerateResponse, summary="Generate SCAD from text only")
async def generate_from_text(body: GenerateRequest):
    """
    Text-only pipeline (no image) — vision step is skipped entirely.
    Code generation always uses Ollama.
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
    """
    updates = [u.model_dump() for u in body.updates]
    patched = apply_parameter_patch(body.scad_code, updates)
    file_path = save_scad_file(patched, "updated_model")
    return ApplyParametersResponse(
        scad_code=patched,
        scad_file_path=file_path,
        parameters=parse_parameters(patched),
    )


@router.post("/refine-iterative", response_model=IterativeRefinementResponse, summary="Iteratively refine SCAD against reference image")
async def refine_iterative(body: IterativeRefinementRequest):
    """
    Iterative refinement loop:
    1. Render current SCAD to PNG
    2. Vision model compares PNG vs input image and provides feedback
    3. Code model refines SCAD based on feedback
    4. Repeat until satisfied or max iterations reached
    
    The input_image_bytes should be base64-encoded.
    """
    try:
        image_bytes = None
        if body.image_key:
            image_bytes = get_image(body.image_key)
            if image_bytes is None:
                raise HTTPException(status_code=404, detail="Stored image not found for image_key.")
        elif body.input_image_bytes:
            try:
                image_bytes = base64.b64decode(body.input_image_bytes)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid base64 image: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either image_key or input_image_bytes must be provided.",
            )

        if not body.scad_code:
            if not body.prompt:
                raise HTTPException(
                    status_code=400,
                    detail="prompt is required when scad_code is not provided.",
                )
            generated = await _build_model(
                user_prompt=body.prompt,
                vision_description=body.vision_description or "",
                image_bytes=image_bytes,
                media_type="image/jpeg",
                base_code=None,
                error=None,
            )
            initial_scad_code = generated.scad_code
            initial_vision_description = generated.description
            user_prompt = body.prompt
        else:
            initial_scad_code = body.scad_code
            initial_vision_description = body.vision_description or ""
            user_prompt = body.prompt or ""

        # Run the iterative refinement loop
        result = await refine_until_satisfied(
            input_image_bytes=image_bytes,
            initial_scad_code=initial_scad_code,
            vision_description=initial_vision_description,
            user_prompt=user_prompt,
            max_iterations=body.max_iterations,
            confidence_threshold=body.confidence_threshold,
        )
        
        # Save final SCAD code
        file_path = save_scad_file(result["final_scad_code"], "refined_model")
        
        # Encode final PNG if available
        final_png_b64 = None
        if result.get("final_png_bytes"):
            final_png_b64 = base64.b64encode(result["final_png_bytes"]).decode()
        
        return IterativeRefinementResponse(
            final_scad_code=result["final_scad_code"],
            scad_file_path=file_path,
            iterations=result["iterations"],
            satisfied=result["satisfied"],
            final_png_bytes=final_png_b64,
            feedback_history=result["feedback_history"],
            render_history=result["render_history"],
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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