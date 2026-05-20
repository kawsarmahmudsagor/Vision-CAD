"""
Call 1 — Vision service.
Takes a base64-encoded image and returns a textual description
suitable for driving OpenSCAD code generation.
"""
import base64
import httpx
from config import get_settings
from prompts import VISION_DESCRIPTION_PROMPT


def _auth_headers(api_key: str) -> dict:
    """Return Authorization header only when an API key is configured."""
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


async def describe_image(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
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
        "options": {
            "temperature": 0.2,
            "num_predict": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            headers=_auth_headers(settings.ollama_api_key),
        )
        resp.raise_for_status()
        data = resp.json()

    return data["message"]["content"].strip()