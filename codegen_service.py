"""
Code generation service — mirrors the STRICT_CODE_PROMPT call from index.ts.
Call 2: takes the vision description (+ optionally the image) and produces
raw OpenSCAD code via Ollama.
"""
import re
import base64
import httpx
from config import get_settings
from prompts import STRICT_CODE_PROMPT
from tools import strip_code_fences, extract_openscad_from_text


async def generate_scad_code(
    user_prompt: str,
    vision_description: str,
    image_bytes: bytes | None = None,
    media_type: str = "image/jpeg",
    base_code: str | None = None,
    error: str | None = None,
) -> str:
    """
    Call 2 — generate OpenSCAD code using Ollama.

    Sends STRICT_CODE_PROMPT as system, then a user message containing:
      - The vision description
      - The original user prompt
      - Optionally the image (vision model supports it)
      - Optionally the existing code and/or an error to fix
    """
    settings = get_settings()

    parts = [vision_description, "", f"User request: {user_prompt}"]
    if base_code:
        parts.append(f"\nExisting code to modify:\n{base_code}")
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

    async def parse_response(data: dict[str, object]) -> tuple[str, str]:
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
        else:
            content = message

        if not isinstance(content, str):
            raise RuntimeError(
                "Code generation response did not contain a valid text content field."
            )

        raw_text = content.strip()
        code_text = strip_code_fences(raw_text).strip()
        if not code_text or len(code_text) < 20:
            fallback = extract_openscad_from_text(raw_text)
            if fallback:
                code_text = fallback
        return code_text, raw_text

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    code, raw = await parse_response(data)
    if not code or len(code) < 20:
        # Retry once with a stronger explicit instruction to return only code.
        retry_message = {
            "role": "user",
            "content": (
                user_text
                + "\n\nReturn only valid OpenSCAD code. If you cannot, write ERROR."
            ),
        }
        if "images" in user_message:
            retry_message["images"] = user_message["images"]

        retry_payload = {
            "model": settings.code_model,
            "messages": [
                {"role": "system", "content": STRICT_CODE_PROMPT},
                retry_message,
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 8192},
        }
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=retry_payload,
        )
        resp.raise_for_status()
        data = resp.json()
        code, raw = await parse_response(data)

    if not code or len(code) < 20:
        snippet = raw.replace("\n", " ")[:500]
        raise RuntimeError(
            f"Code generation returned empty or invalid OpenSCAD code. Raw response snippet: {snippet}"
        )

    return code


async def generate_title(description: str, user_prompt: str) -> str:
    """
    Generate a short title for the 3D object using Ollama.
    """
    settings = get_settings()
    from prompts import TITLE_PROMPT

    payload = {
        "model": settings.code_model,
        "messages": [
            {"role": "system", "content": TITLE_PROMPT},
            {
                "role": "user",
                "content": f"Object description: {description}\nUser request: {user_prompt}\nTitle:",
            },
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 30},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        title = data["message"]["content"].strip().strip("\"'").strip()
        title = re.sub(r"^title:\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"[.!?:;,]+$", "", title).strip()
        if len(title) > 27:
            title = title[:24] + "..."
        return title if len(title) >= 2 else "CAD Object"
    except Exception:
        return "CAD Object"


async def refine_scad_code(
    current_code: str,
    visual_feedback: str,
    vision_description: str,
    user_prompt: str,
) -> str:
    """
    Refine existing OpenSCAD code based on visual comparison feedback.

    This is called during the iterative refinement loop. The vision model
    has compared the rendered output to the input image and provided specific
    feedback on what needs to change.

    Args:
        current_code: Current OpenSCAD code to modify.
        visual_feedback: Feedback from vision model on what to change.
        vision_description: Original description of the input image.
        user_prompt: Original user request.

    Returns:
        Modified OpenSCAD code. If the model cannot produce usable code after
        retries, returns ``current_code`` unchanged (fail soft) so the caller
        can stop refining and keep the best version it already has, rather than
        aborting the whole request.
    """
    settings = get_settings()
    from prompts import ITERATIVE_REFINEMENT_PROMPT

    base_parts = [
        ITERATIVE_REFINEMENT_PROMPT,
        "",
        f"Original image description: {vision_description}",
        f"Original user request: {user_prompt}",
        "",
        "Current OpenSCAD code:",
        current_code,
        "",
        "Visual feedback (what to change):",
        visual_feedback,
    ]

    async def attempt_refinement(attempt_num: int = 1) -> str:
        """Make one attempt to refine the SCAD code."""
        if attempt_num > 1:
            # On retry, be explicit but do NOT invite an "ERROR" sentinel —
            # a literal "ERROR" reply is short enough to fail the length check
            # and was a direct cause of spurious refinement failures.
            parts = base_parts + [
                "",
                "Return ONLY the complete, valid OpenSCAD code — no prose, no markdown.",
            ]
        else:
            parts = base_parts + ["", "Refined code:"]

        user_text = "\n".join(parts)

        payload = {
            "model": settings.code_model,
            "messages": [
                {
                    "role": "system",
                    "content": STRICT_CODE_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
            "stream": False,
            "options": {"temperature": 0.15 if attempt_num > 1 else 0.2, "num_predict": 8192},
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else message
        raw = (content or "").strip() if isinstance(content, str) else ""
        code = strip_code_fences(raw).strip()

        if not code or len(code) < 20:
            fallback = extract_openscad_from_text(raw)
            if fallback:
                code = fallback

        return code

    # First attempt
    code = await attempt_refinement(1)

    # Retry if empty or invalid
    if not code or len(code) < 20:
        code = await attempt_refinement(2)

    # Fail soft: if we still can't get usable code, keep the existing code
    # rather than raising. The caller will detect the unchanged result, stop
    # refining, and return the best version it already has — instead of
    # aborting the whole request with "could not generate valid OpenSCAD code".
    if not code or len(code) < 20:
        return current_code

    return code