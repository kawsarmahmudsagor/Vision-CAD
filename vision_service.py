"""
Call 1 — Vision service.
Takes raw image bytes and returns a textual description suitable for
driving OpenSCAD code generation.

Supports two providers (selected per-request via the `provider` argument):
  - "ollama"       → Ollama /api/chat
  - "huggingface"  → Local HuggingFace model via transformers (no API key needed)
"""
import base64
import io
import httpx
from config import get_settings
from prompts import VISION_DESCRIPTION_PROMPT


async def describe_image(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    provider: str = "ollama",
) -> str:
    """
    Describe an image using the configured vision model.

    Args:
        image_bytes: Raw image bytes.
        media_type:  MIME type (e.g. "image/jpeg").
        provider:    "ollama" or "huggingface".

    Returns:
        A textual description of the image for 3D modelling.
    """
    if provider == "huggingface":
        return await _describe_image_local_hf(image_bytes, media_type)
    return await _describe_image_ollama(image_bytes, media_type)


# ── Ollama ────────────────────────────────────────────────────────────────────

async def _describe_image_ollama(image_bytes: bytes, media_type: str) -> str:
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
        "options": {"temperature": 0.1},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = resp.text.strip()
            raise RuntimeError(
                f"Ollama vision request failed with status {resp.status_code}: {body or resp.reason_phrase}"
            ) from exc

        data = resp.json()

    if not isinstance(data, dict):
        raise RuntimeError("Ollama vision response was not a JSON object.")

    message = data.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Ollama vision response did not contain a valid 'message' object.")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama vision response returned empty description content.")

    return content.strip()


# ── Local HuggingFace (transformers) ─────────────────────────────────────────

# Module-level cache so the model is loaded once per process lifetime.
_hf_pipeline = None
_hf_loaded_model: str | None = None


def _get_hf_pipeline(model_name: str):
    """
    Load (or return cached) a local transformers image-text-to-text pipeline.

    The pipeline is created once and reused across requests.  Loading happens
    in a thread pool (called via asyncio.to_thread) so it doesn't block the
    event loop.
    """
    global _hf_pipeline, _hf_loaded_model

    if _hf_pipeline is not None and _hf_loaded_model == model_name:
        return _hf_pipeline

    # Import here so the rest of the app works even if transformers isn't
    # installed (only needed when provider="huggingface" is actually used).
    try:
        from transformers import pipeline as hf_pipeline_fn
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "The 'transformers' and 'torch' packages are required for "
            "provider='huggingface'.  Install them with:\n"
            "  pip install transformers torch pillow"
        ) from exc

    device = 0 if torch.cuda.is_available() else -1  # GPU if available, else CPU

    _hf_pipeline = hf_pipeline_fn(
        "image-text-to-text",
        model=model_name,
        device=device,
        torch_dtype=torch.float16 if device == 0 else torch.float32,
    )
    _hf_loaded_model = model_name
    return _hf_pipeline


async def _describe_image_local_hf(image_bytes: bytes, media_type: str) -> str:
    """
    Run a local HuggingFace vision model using the transformers library.

    The model is loaded from HF_VISION_MODEL (a Hub model ID such as
    "meta-llama/Llama-3.2-11B-Vision-Instruct", or a local path like
    "./models/llava").  No API token or network access is required once the
    weights are downloaded.

    Model loading is offloaded to a thread so the async event loop isn't
    blocked during the (slow) first load.
    """
    import asyncio
    from PIL import Image  # type: ignore

    settings = get_settings()

    if not settings.hf_vision_model:
        raise ValueError(
            "HF_VISION_MODEL must be set to a Hub model ID or local path "
            "when using provider='huggingface'."
        )

    # Decode bytes → PIL Image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Build the message in the chat format most vision models expect
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": VISION_DESCRIPTION_PROMPT},
            ],
        }
    ]

    def _run_inference():
        pipe = _get_hf_pipeline(settings.hf_vision_model)
        # max_new_tokens caps the description length; adjust in .env if needed
        outputs = pipe(
            messages,
            max_new_tokens=getattr(settings, "hf_max_new_tokens", 1024),
            do_sample=False,
        )
        # transformers pipelines return a list; grab the generated text
        result = outputs[0]
        if isinstance(result, dict):
            # {"generated_text": [{"role": "assistant", "content": "..."}]}
            generated = result.get("generated_text", "")
            if isinstance(generated, list):
                # Last message is the assistant reply
                last = generated[-1]
                if isinstance(last, dict):
                    return last.get("content", "")
                return str(last)
            return str(generated)
        return str(result)

    # Run blocking inference in a thread pool so the event loop stays free
    description = await asyncio.to_thread(_run_inference)
    if not isinstance(description, str) or not description.strip():
        raise RuntimeError("HuggingFace vision model returned an empty description.")
    return description.strip()