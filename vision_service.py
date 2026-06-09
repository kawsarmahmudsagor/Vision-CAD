"""
vision_service.py
──────────────────────────────────────────────────────────────────────────────
Call 1 — Vision / Semantic Extraction service.

Returns TWO things:
    description  : prose description for the code-gen LLM (unchanged)
    semantics    : structured dict of style attributes — the LLM must NOT
                   guess these, and must NOT guess geometry (that comes from
                   COCO).  This mirrors semantic_extractor.py in the ring
                   pipeline.

When no image is available, safe defaults are returned.
"""

import base64
import json
import logging
import httpx
from config import get_settings
from prompts import VISION_DESCRIPTION_PROMPT, VISION_SEMANTIC_PROMPT

logger = logging.getLogger(__name__)

_DEFAULT_SEMANTICS = {
    "ring_style":       "Solitaire",
    "setting_type":     "Prong",
    "center_stone_cut": "Round",
    "shank_style":      "Plain",
    "shoulders":        "Plain",
    "prong_count":      4,
    "prong_style":      "claw",
    "symmetry":         "Bilateral",
}


async def describe_image(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """Return prose 3D-modelling description (unchanged from original)."""
    settings = get_settings()
    b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": settings.vision_model,
        "messages": [{"role": "user", "content": VISION_DESCRIPTION_PROMPT, "images": [b64]}],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
        resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


async def extract_semantics(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    Extract structured semantic style attributes from the ring image.
    The LLM sees the image and returns a JSON dict of style fields ONLY —
    all numeric geometry comes from COCO, not from here.
    """
    settings = get_settings()
    b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": settings.vision_model,
        "messages": [{"role": "user", "content": VISION_SEMANTIC_PROMPT, "images": [b64]}],
        "stream": False,
        "options": {"temperature": 0.05},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()

        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]

        parsed = json.loads(raw.strip())

        # Sanitise: drop any geometry keys the LLM hallucinated
        for banned in ("inner_diameter", "outer_diameter", "stone_width",
                       "stone_height", "gallery", "halo", "bridge"):
            parsed.pop(banned, None)

        # Fill missing with defaults; validate prong_count
        for k, v in _DEFAULT_SEMANTICS.items():
            if k not in parsed:
                parsed[k] = v
        if parsed.get("prong_count") not in (4, 6, 8):
            parsed["prong_count"] = 4
        if parsed.get("prong_style") not in ("claw", "round_tip", "flat", "double_claw"):
            parsed["prong_style"] = "claw"

        logger.info(f"Extracted semantics: {parsed}")
        return parsed

    except Exception as e:
        logger.error(f"Semantic extraction failed: {e} — using defaults")
        return _DEFAULT_SEMANTICS.copy()