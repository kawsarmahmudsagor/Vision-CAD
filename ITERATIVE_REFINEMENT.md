# Iterative SCAD Refinement — Implementation Guide

## Overview

The Vision-CAD system now supports **iterative refinement** of OpenSCAD code based on visual feedback. Instead of generating SCAD once and calling it done, the system:

1. **Generates** initial SCAD from an image description
2. **Renders** the SCAD to a PNG preview
3. **Compares** the rendered PNG against the original input image using the vision model
4. **Refines** the SCAD code based on specific visual feedback
5. **Repeats** steps 2-4 until the model is satisfied

This creates a tight feedback loop where the generated CAD continuously improves until it matches the input image.

---

## Architecture

### Key Components

#### 1. **render_service.py**
Converts OpenSCAD code to PNG images using the OpenSCAD CLI.

```python
async def render_scad_to_png(scad_code: str) -> bytes:
    """Render SCAD to PNG and return image bytes."""
```

**How it works:**
- Writes SCAD code to a temp file
- Calls OpenSCAD with camera and rendering parameters
- Returns PNG bytes
- Cleans up temp files

**Camera Settings:**
```bash
--camera 0,0,0,60,0,45,80
# Format: tx,ty,tz,rx,ry,rz,distance
# Default: isometric view, 800x600
```

#### 2. **comparison_service.py**
Uses the vision model to compare the rendered PNG against the original input image.

```python
async def compare_renders(
    input_image_bytes: bytes,
    rendered_png_bytes: bytes,
    iteration: int
) -> dict:
    """
    Returns:
    {
        "is_satisfied": bool,
        "feedback": str,  # specific changes needed
        "confidence": float,  # 0-1
        "reasoning": str
    }
    """
```

**Vision Model Output Format:**
The vision model must return a structured response:
```
SATISFIED: yes
CONFIDENCE: 0.92
FEEDBACK: None
REASONING: The rendered model closely matches the original image...
```

Or if changes are needed:
```
SATISFIED: no
CONFIDENCE: 0.45
FEEDBACK: Increase wall thickness by 2mm, round top corners by 3mm
REASONING: The model is too thin and has sharp edges...
```

#### 3. **codegen_service.py**
Extended with a new function `refine_scad_code()` that modifies existing code based on visual feedback.

```python
async def refine_scad_code(
    current_code: str,
    visual_feedback: str,
    vision_description: str,
    user_prompt: str
) -> str:
    """Refine existing SCAD based on visual feedback."""
```

**Key Differences from generate_scad_code():**
- Takes current code as input (not just description)
- Uses `ITERATIVE_REFINEMENT_PROMPT` to guide modifications
- Lower temperature (0.2 vs 0.1) for more focused changes
- Expects the model to return modified code, not fresh generation

#### 4. **refinement_service.py**
Orchestrates the entire iterative loop.

```python
async def refine_until_satisfied(
    input_image_bytes: bytes,
    initial_scad_code: str,
    vision_description: str,
    user_prompt: str,
    max_iterations: int = 10,
    confidence_threshold: float = 0.75
) -> dict:
    """
    Main refinement loop.
    
    Returns:
    {
        "final_scad_code": str,
        "iterations": int,
        "satisfied": bool,
        "final_png_bytes": bytes,
        "feedback_history": list,
        "render_history": list
    }
    """
```

**Loop Algorithm:**
```
for iteration in range(1, max_iterations + 1):
    1. Render SCAD to PNG
       - If render fails: request code fix for syntax error
    2. Compare PNG vs input
       - Get: is_satisfied, confidence, feedback, reasoning
    3. Check satisfaction
       - If satisfied OR confidence >= threshold: return SUCCESS
    4. Refine code
       - Pass feedback to code model
       - Get: modified SCAD
    5. Continue loop
```

---

## API Usage

### Endpoint

```http
POST /api/v1/refine-iterative
Content-Type: application/json

{
  "scad_code": "...",
  "input_image_bytes": "base64-encoded-image",
  "max_iterations": 10,
  "confidence_threshold": 0.75,
  "vision_description": "optional description from vision model",
  "user_prompt": "original request from user"
}
```

### Response

```json
{
  "final_scad_code": "... refined OpenSCAD code ...",
  "scad_file_path": "/path/to/outputs/refined_model_abc123.scad",
  "iterations": 5,
  "satisfied": true,
  "final_png_bytes": "base64-encoded-png-or-null",
  "feedback_history": [
    {
      "iteration": 1,
      "is_satisfied": false,
      "confidence": 0.42,
      "feedback": "Make the ring thinner, decrease by 1mm",
      "reasoning": "Current thickness is too large compared to reference"
    },
    ...
  ],
  "render_history": [
    {
      "iteration": 1,
      "png_bytes_len": 125480
    },
    ...
  ]
}
```

### Example Request (Python)

```python
import requests
import base64

# Prepare image
with open("reference_ring.png", "rb") as f:
    image_bytes = f.read()

image_b64 = base64.b64encode(image_bytes).decode()

# Initial SCAD code
scad_code = """
outer_radius = 10;
inner_radius = 8;
band_height = 3;

rotate_extrude($fn = 120)
translate([inner_radius, 0])
square([outer_radius - inner_radius, band_height]);
"""

# Request refinement
response = requests.post(
    "http://localhost:8000/api/v1/refine-iterative",
    json={
        "scad_code": scad_code,
        "input_image_bytes": image_b64,
        "max_iterations": 10,
        "confidence_threshold": 0.75,
        "vision_description": "A simple gold ring with a smooth band",
        "user_prompt": "Create a ring matching this image"
    }
)

result = response.json()
print(f"Satisfied: {result['satisfied']}")
print(f"Iterations: {result['iterations']}")
print(f"Final code:\n{result['final_scad_code']}")

# Save refined code
with open("refined_ring.scad", "w") as f:
    f.write(result["final_scad_code"])
```

---

## Prompt Engineering

### ITERATIVE_COMPARISON_PROMPT
Guides the vision model to compare images and provide structured feedback.

**Key points:**
- Both images are provided (input + rendered)
- Output format is strict (SATISFIED, CONFIDENCE, FEEDBACK, REASONING)
- SATISFIED = "yes" only if >90% similar
- FEEDBACK must be specific and actionable
- No code suggestions, only visual changes

**Example feedback:**
- ❌ "Make it better" (too vague)
- ✅ "Increase inner diameter by 2mm, reduce band thickness to 2mm"

### ITERATIVE_REFINEMENT_PROMPT
Guides the code model to make targeted, minimal changes.

**Key points:**
- PRESERVE overall structure and modules
- Only modify what the feedback mentions
- Keep parameter names consistent
- Return ONLY raw OpenSCAD code, no explanation
- No markdown blocks, no comments about changes

**Example flow:**
```
Feedback: "Increase wall thickness by 1mm, round top corners"

Code model should:
  1. Find the wall_thickness parameter
  2. Increase it by 1mm
  3. Find the top corner definition
  4. Add offset() or hull() to round it
  5. Return the modified code
```

---

## Configuration & Tuning

### Environment Variables
In `.env`:
```bash
# Render settings (optional, uses OpenSCAD defaults if not set)
OPENSCAD_BIN=/path/to/openscad
OPENSCAD_IMGSIZE=800,600
OPENSCAD_COLORSCHEME=DeepOcean

# Refinement loop settings
MAX_ITERATIONS=10  # Recommended
CONFIDENCE_THRESHOLD=0.75  # 0-1, higher = stricter matching
```

### Model Temperatures
- **Vision model** (comparison): `temperature=0.3` (consistent evaluation)
- **Code model** (generation): `temperature=0.1` (precise code)
- **Code model** (refinement): `temperature=0.2` (focused modifications)

### Iteration Limits
- Default `max_iterations=10`
- Recommended: 5-15 depending on complexity
- Higher = more accurate but slower
- Lower = faster but less refined

### Confidence Threshold
- Default `confidence_threshold=0.75`
- `0.5-0.7`: Lenient (accepts partial matches)
- `0.75-0.85`: Standard (good match)
- `0.9+`: Strict (must be nearly identical)

---

## Error Handling

### Render Failures
If OpenSCAD rendering fails:
1. Error message is captured
2. Feedback asks code model to fix syntax
3. Loop continues (doesn't count against satisfaction)
4. Prevents infinite loops with syntax errors

### Missing Feedback
If vision model doesn't return expected format:
1. System uses raw response text as feedback
2. Code model does its best with unstructured feedback
3. Loop continues (may produce suboptimal results)

### Max Iterations Reached
If the loop doesn't converge:
1. Loop exits after max_iterations
2. Returns `"satisfied": false`
3. Returns all feedback history for analysis
4. Final SCAD is still usable (just not fully refined)

---

## Workflow: From Image to Refined SCAD

### Traditional (Before)
```
Image → Vision Model → Description → Code Model → SCAD (v1)
                                                      ↓
                                                   Done
```

### Iterative (After)
```
Image → Vision Model → Description → Code Model → SCAD (v1)
                                                      ↓
                    ┌─────────────────────────────────┤
                    ↓                                  ↑
            Render to PNG                        Refine SCAD
                    ↓                                  ↑
            Compare vs Input                   (feedback loop)
                    ↓                                  ↑
            Satisfied? ─ NO ──────────────────────────┤
                    ↓
                   YES
                    ↓
            Return SCAD (refined)
```

---

## Best Practices

### 1. Initial SCAD Quality Matters
- Better initial code = fewer refinement iterations
- Use `STRICT_CODE_PROMPT` with good vision descriptions
- Start with parametric, well-structured code

### 2. Image Quality
- Use clear, well-lit reference images
- Show the object from a standard viewing angle
- Include scale reference if possible (e.g., next to a coin)

### 3. Feedback Interpretation
- Review `feedback_history` to understand what changed
- If `confidence` is low but `is_satisfied=true`, it may be a vision model quirk
- Check if specific features (holes, details) are present in feedback

### 4. Parameter Naming
- Use descriptive names: `band_thickness`, `inner_diameter`, etc.
- Avoid single letters unless necessary
- These names appear in feedback, so clarity matters

### 5. Debug Iteration Failures
```python
# If refinement doesn't converge, examine:
for feedback in result["feedback_history"]:
    print(f"Iter {feedback['iteration']}: confidence={feedback['confidence']}")
    print(f"  Feedback: {feedback['feedback']}")
    print(f"  Reasoning: {feedback['reasoning']}")
```

---

## Future Improvements

1. **Streaming responses** — progressively send updates during loop
2. **Multi-view rendering** — compare from multiple angles
3. **Feature detection** — identify specific parts (holes, prongs, etc.)
4. **Parametric guides** — suggest parameter changes instead of code changes
5. **Human-in-the-loop** — pause loop, ask user for feedback between iterations
6. **Render caching** — skip re-render if code hasn't changed

---

## Testing

### Unit Test Example
```python
import pytest
from comparison_service import compare_renders

@pytest.mark.asyncio
async def test_comparison_satisfied():
    # Load images
    input_img = open("test_ring.png", "rb").read()
    render_img = open("test_ring_render.png", "rb").read()
    
    result = await compare_renders(input_img, render_img, iteration=1)
    
    assert "is_satisfied" in result
    assert "confidence" in result
    assert isinstance(result["confidence"], float)
    assert 0 <= result["confidence"] <= 1
```

### Integration Test Example
```python
@pytest.mark.asyncio
async def test_full_refinement_loop():
    scad = "... simple ring code ..."
    img = open("reference_ring.png", "rb").read()
    
    result = await refine_until_satisfied(
        input_image_bytes=img,
        initial_scad_code=scad,
        vision_description="A gold ring",
        user_prompt="Create a ring",
        max_iterations=5,
        confidence_threshold=0.8
    )
    
    assert result["iterations"] <= 5
    assert len(result["feedback_history"]) > 0
    assert result["final_scad_code"] is not None
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Loop always maxes out iterations | Code changes aren't converging | Lower confidence_threshold, review feedback |
| "OpenSCAD rendering failed" | SCAD syntax error | Check initial code, test locally with OpenSCAD |
| Feedback doesn't improve model | Vision model misunderstanding | Provide clearer input image |
| Very slow iterations | Large SCAD or complex rendering | Reduce `$fn` values, simplify geometry |
| PNG bytes are empty | Render succeeded but no data | Check OpenSCAD installation, camera params |

---

## Related Files

- `render_service.py` — Rendering logic
- `comparison_service.py` — Vision comparison logic
- `refinement_service.py` — Loop orchestration
- `codegen_service.py::refine_scad_code()` — Code refinement
- `prompts.py::ITERATIVE_COMPARISON_PROMPT` — Vision guidance
- `prompts.py::ITERATIVE_REFINEMENT_PROMPT` — Code guidance
- `generate.py::refine_iterative()` — API endpoint

---

## Contact & Support

For issues or improvements, refer to the GitHub issues or internal documentation.
