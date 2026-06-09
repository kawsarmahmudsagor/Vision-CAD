# Iterative SCAD Refinement — Quick Start Guide

## What Changed?

Your Vision-CAD pipeline now supports **iterative refinement**:

```
Old: Image → Vision → Description → CodeGen → SCAD (final)

New: Image → Vision → Description → CodeGen → SCAD (v1)
                                               ↓
                                        [Feedback Loop]
                                        Render → Compare
                                        Refine → Repeat
                                               ↓
                                           SCAD (refined)
```

## Quick Start: 3 Steps

### Step 1: Generate Initial SCAD

Use the existing `/generate` endpoint (unchanged):

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -F "image=@ring.jpg" \
  -F "prompt=Create a ring matching this image"
```

Response includes `scad_code` and `scad_file_path`.

### Step 2: Refine with Feedback Loop

Use the NEW `/refine-iterative` endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/refine-iterative \
  -H "Content-Type: application/json" \
  -d '{
    "scad_code": "... from step 1 ...",
    "input_image_bytes": "base64-encoded-image",
    "vision_description": "A gold ring with...",
    "user_prompt": "Create a ring",
    "max_iterations": 10,
    "confidence_threshold": 0.75
  }'
```

### Step 3: Use the Refined SCAD

Response includes `final_scad_code` and `scad_file_path`.

Save and 3D print!

---

## API Endpoints

### Existing (Unchanged)
- `POST /api/v1/generate` — Image to SCAD (one-shot)
- `POST /api/v1/generate/text` — Text to SCAD
- `POST /api/v1/apply-parameters` — Patch parameters
- `GET /api/v1/download/{filename}` — Download .scad file

### New
- `POST /api/v1/refine-iterative` — Iterative refinement loop

---

## New Service Files

| File | Purpose |
|------|---------|
| `render_service.py` | SCAD → PNG rendering |
| `comparison_service.py` | Vision model comparison |
| `refinement_service.py` | Loop orchestration |

## Modified Service Files

| File | What Changed |
|------|--------------|
| `codegen_service.py` | Added `refine_scad_code()` function |
| `prompts.py` | Added 2 new system prompts |
| `schemas.py` | Added request/response types |
| `generate.py` | Added `/refine-iterative` endpoint |

---

## Configuration

### OpenSCAD Rendering

The system needs OpenSCAD installed:

```bash
# Linux
sudo apt-get install openscad

# macOS
brew install openscad

# Verify
openscad --version
```

The render service calls:
```bash
openscad -o output.png \
  --imgsize 800,600 \
  --camera 0,0,0,60,0,45,80 \
  --colorscheme DeepOcean \
  input.scad
```

### Environment Variables (Optional)

In `.env`:
```bash
# Rendering (defaults shown)
OPENSCAD_BIN=openscad
OPENSCAD_IMGSIZE=800,600
OPENSCAD_COLORSCHEME=DeepOcean

# Loop behavior
# (set in request, not env)
```

---

## Example: Full Workflow

### Python Client

```python
import requests
import base64
import json

# === STEP 1: Get initial SCAD ===
with open("reference_ring.jpg", "rb") as f:
    image_bytes = f.read()

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    files={"image": image_bytes},
    data={"prompt": "Create a ring matching this image"}
)

initial_result = response.json()
initial_scad = initial_result["scad_code"]
vision_desc = initial_result["description"]

print(f"Generated initial SCAD")
print(f"  Saved to: {initial_result['scad_file_path']}")

# === STEP 2: Refine with feedback loop ===
image_b64 = base64.b64encode(image_bytes).decode()

refinement_request = {
    "scad_code": initial_scad,
    "input_image_bytes": image_b64,
    "vision_description": vision_desc,
    "user_prompt": "Create a ring matching this image",
    "max_iterations": 10,
    "confidence_threshold": 0.75
}

response = requests.post(
    "http://localhost:8000/api/v1/refine-iterative",
    json=refinement_request
)

refine_result = response.json()

# === STEP 3: Analyze results ===
print(f"\nRefinement Complete:")
print(f"  Iterations: {refine_result['iterations']}")
print(f"  Satisfied: {refine_result['satisfied']}")
print(f"  Saved to: {refine_result['scad_file_path']}")

print(f"\nFeedback History:")
for feedback in refine_result["feedback_history"]:
    iter_num = feedback["iteration"]
    confidence = feedback.get("confidence", "N/A")
    is_sat = feedback.get("is_satisfied", False)
    feedback_text = feedback.get("feedback", "")
    
    print(f"  Iter {iter_num} (confidence={confidence}, satisfied={is_sat})")
    print(f"    → {feedback_text[:60]}...")

# === STEP 4: Save refined code ===
with open("ring_refined.scad", "w") as f:
    f.write(refine_result["final_scad_code"])

print(f"\nRefined SCAD saved to: ring_refined.scad")
```

---

## How the Loop Works

1. **Render**: SCAD → PNG (OpenSCAD CLI)
2. **Compare**: Vision model looks at both images, returns structured feedback
3. **Refine**: Code model reads feedback, modifies SCAD
4. **Repeat** until satisfied or max iterations reached

### Vision Model Output Example

**First iteration (not satisfied):**
```
SATISFIED: no
CONFIDENCE: 0.42
FEEDBACK: Increase inner diameter by 1mm, reduce band thickness to 2mm
REASONING: The ring is too thick and the inner diameter is too small...
```

**Later iteration (satisfied):**
```
SATISFIED: yes
CONFIDENCE: 0.88
FEEDBACK: None
REASONING: The rendered model closely matches the reference image...
```

---

## Feedback Interpretation

| Confidence | What It Means |
|------------|---------------|
| 0.0 - 0.5 | Poor match, significant changes needed |
| 0.5 - 0.75 | Partial match, refinement helpful |
| 0.75 - 0.9 | Good match, minor tweaks remaining |
| 0.9 - 1.0 | Excellent match, nearly identical |

---

## Troubleshooting

### "OpenSCAD rendering failed"
- Ensure OpenSCAD is installed: `openscad --version`
- Check SCAD code for syntax errors
- Try rendering the file manually: `openscad -o test.png input.scad`

### "Max iterations reached but not satisfied"
- Try lowering `confidence_threshold` to 0.6-0.7
- Review `feedback_history` to see what's changing
- The SCAD is still valid, just not fully matched

### "No feedback from vision model"
- Check if `input_image_bytes` is valid base64
- Verify the image quality (should be clear and well-lit)
- Try providing a better `vision_description`

### Slow iterations
- Reduce OpenSCAD `$fn` values (affects render speed)
- Lower `max_iterations` to stop earlier
- Use simpler geometry in initial SCAD

---

## Response Structure

```json
{
  "final_scad_code": "... refined OpenSCAD code ...",
  "scad_file_path": "/path/to/outputs/refined_model_xyz.scad",
  "iterations": 5,
  "satisfied": true,
  "final_png_bytes": "base64-encoded-png-or-null",
  "feedback_history": [
    {
      "iteration": 1,
      "is_satisfied": false,
      "confidence": 0.42,
      "feedback": "...",
      "reasoning": "..."
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

---

## Parameters

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scad_code` | str | required | Current OpenSCAD code |
| `input_image_bytes` | str | required | Base64-encoded reference image |
| `max_iterations` | int | 10 | Max refinement loops |
| `confidence_threshold` | float | 0.75 | Satisfaction threshold (0-1) |
| `vision_description` | str | "" | Optional image description |
| `user_prompt` | str | "" | Original user request |

### Tuning Recommendations

- **Fast mode**: `max_iterations=5`, `confidence_threshold=0.65`
- **Balanced**: `max_iterations=10`, `confidence_threshold=0.75`
- **Precise**: `max_iterations=15`, `confidence_threshold=0.85`

---

## Next Steps

1. Test with a sample image and SCAD
2. Review `feedback_history` to understand refinement
3. Adjust `confidence_threshold` if needed
4. Integrate into your workflow
5. Monitor iteration counts and convergence

See `ITERATIVE_REFINEMENT.md` for detailed documentation.
