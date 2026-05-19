"""
Call 1 — Vision service.
Takes a base64-encoded image and returns a textual description
suitable for driving OpenSCAD code generation.
"""
import base64
import httpx
from config import get_settings
from prompts import VISION_DESCRIPTION_PROMPT


async def describe_image(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """
    Send image to Ollama's qwen3-vl:8b and get a 3D-modelling description back.
    Uses Ollama's native /api/chat endpoint with vision support.
    """
    settings = get_settings()
    b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": VISION_DESCRIPTION_PROMPT,
                "images": [b64],
            }
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["message"]["content"].strip()
