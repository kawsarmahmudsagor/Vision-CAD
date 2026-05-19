"""
Code generation service — mirrors the STRICT_CODE_PROMPT call from index.ts.
Call 2: takes the vision description (+ optionally the image) and produces
raw OpenSCAD code via Ollama qwen3-vl:8b.
"""
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
    Call 2 — generate OpenSCAD code.

    Sends STRICT_CODE_PROMPT as system, then a user message containing:
      - The vision description
      - The original user prompt
      - Optionally the image (vision model supports it)
      - Optionally the existing code and/or an error to fix
    """
    settings = get_settings()

    # Build the user message content
    parts = [vision_description, "", f"User request: {user_prompt}"]

    if base_code:
        parts.append(f"\nExisting code to modify:\n{base_code}")

    if error:
        parts.append(f"\nFix this OpenSCAD error: {error}")

    user_text = "\n".join(parts)

    # Build messages for Ollama /api/chat
    user_message: dict = {
        "role": "user",
        "content": user_text,
    }

    # Attach image if available (qwen3-vl supports it)
    if image_bytes:
        user_message["images"] = [base64.b64encode(image_bytes).decode()]

    payload = {
        "model": settings.code_model,
        "messages": [
            {"role": "system", "content": STRICT_CODE_PROMPT},
            user_message,
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    raw = data["message"]["content"].strip()

    # Strip any markdown fences the model may have added despite instructions
    code = strip_code_fences(raw).strip()

    # If still looks wrapped, try the fallback extractor
    if not code or len(code) < 20:
        fallback = extract_openscad_from_text(raw)
        if fallback:
            code = fallback

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
        title = data["message"]["content"].strip()
        # Clean up
        title = title.strip('"\'').strip()
        import re
        title = re.sub(r"^title:\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"[.!?:;,]+$", "", title).strip()
        if len(title) > 27:
            title = title[:24] + "..."
        return title if len(title) >= 2 else "CAD Object"
    except Exception:
        return "CAD Object"
