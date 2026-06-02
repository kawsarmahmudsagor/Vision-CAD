"""
Comparison service — uses vision model to validate rendered SCAD against input image.

Compares the generated PNG render with the original input image and provides
specific feedback on what needs to change to match the original.
"""
import base64
import httpx
from config import get_settings
from prompts import ITERATIVE_COMPARISON_PROMPT


async def compare_renders(
    input_image_bytes: bytes,
    rendered_png_bytes: bytes,
    iteration: int = 1,
) -> dict:
    """
    Compare the input image with the rendered SCAD preview.

    Uses the vision model to analyze both images and provide specific feedback
    on what changes are needed to match the original.

    Args:
        input_image_bytes: Original reference image bytes.
        rendered_png_bytes: Rendered SCAD preview PNG bytes.
        iteration: Current iteration number (for context).

    Returns:
        dict with keys:
            - "is_satisfied": bool — whether the match is close enough
            - "feedback": str — specific changes needed (if not satisfied)
            - "confidence": float — how confident the model is (0-1)
            - "reasoning": str — brief explanation of assessment
    """
    settings = get_settings()

    # Encode both images to base64
    input_b64 = base64.b64encode(input_image_bytes).decode()
    rendered_b64 = base64.b64encode(rendered_png_bytes).decode()

    # Build message with both images
    payload = {
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": ITERATIVE_COMPARISON_PROMPT.format(
                    iteration=iteration,
                    input_image="[INPUT IMAGE - original reference]",
                    rendered_image="[RENDERED IMAGE - current SCAD preview]",
                ),
                "images": [input_b64, rendered_b64],  # Order: input first, then rendered
            }
        ],
        "stream": False,
        "options": {"temperature": 0.3},  # Lower temperature for consistency
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    response_text = data["message"]["content"].strip()

    # Parse the vision model's response
    # Expected format:
    # SATISFIED: <yes/no>
    # CONFIDENCE: <0-1>
    # FEEDBACK: <specific changes needed>
    # REASONING: <brief explanation>

    result = {
        "is_satisfied": False,
        "feedback": "",
        "confidence": 0.5,
        "reasoning": "",
        "raw_response": response_text,
    }

    lines = response_text.split("\n")
    for line in lines:
        if line.startswith("SATISFIED:"):
            result["is_satisfied"] = "yes" in line.lower()
        elif line.startswith("CONFIDENCE:"):
            try:
                conf_str = line.replace("CONFIDENCE:", "").strip()
                result["confidence"] = float(conf_str)
            except ValueError:
                pass
        elif line.startswith("FEEDBACK:"):
            result["feedback"] = line.replace("FEEDBACK:", "").strip()
        elif line.startswith("REASONING:"):
            result["reasoning"] = line.replace("REASONING:", "").strip()

    return result


async def get_comparison_feedback(
    input_image_bytes: bytes,
    rendered_png_bytes: bytes,
    iteration: int = 1,
) -> str:
    """
    Get only the feedback text for code refinement.

    Args:
        input_image_bytes: Original reference image bytes.
        rendered_png_bytes: Rendered SCAD preview PNG bytes.
        iteration: Current iteration number.

    Returns:
        Feedback string to pass to code model for refinement.
    """
    result = await compare_renders(input_image_bytes, rendered_png_bytes, iteration)
    
    if result["is_satisfied"]:
        return "Match approved! Model is sufficiently close to the original."
    
    return result["feedback"] or result["raw_response"]
