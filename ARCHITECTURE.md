# System Architecture — Iterative SCAD Refinement

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ITERATIVE REFINEMENT LOOP                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ Input Image  │  (user provides reference image)
└──────┬───────┘
       │
       ├─────────────────────────────────────────────────────────────┐
       │                                                               │
       ▼                                                               │
┌──────────────────┐                                                 │
│ Vision Model     │  (describe_image)                              │
│ (qwen3-vl)       │  Returns: image description                    │
└──────┬───────────┘                                                 │
       │                                                               │
       ▼                                                               │
┌──────────────────┐                                                 │
│ Code Model       │  (generate_scad_code)                          │
│ (gemma4)         │  Input: image description                      │
│                  │  Returns: initial SCAD code                    │
└──────┬───────────┘                                                 │
       │                                                               │
       ├─► scad_v1.scad                                              │
       │                                                               │
       ▼                                                               │
    ╔═══════════════════════════════════════════════════════════╗   │
    ║            ITERATIVE REFINEMENT LOOP START                ║   │
    ║  (refine_until_satisfied in refinement_service.py)        ║   │
    ╚═══════════════════════════════════════════════════════════╝   │
       │                                                               │
       │  iteration_count = 1                                        │
       │                                                               │
       ▼                                                               │
    ┌─────────────────────────────────────┐                        │
    │ STEP 1: Render SCAD to PNG          │                        │
    │ (render_service.render_scad_to_png) │                        │
    │                                      │                        │
    │ Input:  current SCAD code           │                        │
    │ Process: write → openscad → read    │                        │
    │ Output: PNG bytes                    │                        │
    └────────────┬────────────────────────┘                        │
                 │                                                   │
                 │ (render fails?)                                  │
                 ├──► Request syntax fix                             │
                 │    Refine code                                    │
                 │    Skip to step 1                                 │
                 │                                                   │
                 ▼ (render succeeds)                                 │
    ┌─────────────────────────────────────┐                        │
    │ STEP 2: Compare Renders             │                        │
    │ (comparison_service.compare_renders)│                        │
    │                                      │                        │
    │ Input:  input image + rendered PNG  │ ◄───────────────────────┘
    │ Vision: look at both, compare       │
    │ Output: is_satisfied, feedback      │
    └────────────┬────────────────────────┘                        
                 │                                                   
        ┌────────┴─────────┐                                        
        │                  │                                        
   YES  │ satisfied?       │ NO                                     
        │ (or high conf?)  │                                        
        │                  │                                        
        ▼                  ▼                                        
    ╔════════╗        ┌────────────────────────────┐               
    ║ RETURN ║        │ STEP 3: Refine SCAD Code   │               
    ║ RESULT ║        │ (codegen_service.refine_*) │               
    ╚════════╝        │                            │               
                      │ Input:  current code +     │               
                      │         visual feedback    │               
                      │ Process: call code model   │               
                      │ Output:  refined SCAD      │               
                      └────────────┬───────────────┘               
                                   │                               
                                   │ iteration_count++             
                                   │                               
                                   │ if iteration_count              
                                   │    < max_iterations:           
                                   │    goto STEP 1                 
                                   │                               
                                   ▼                               
                            ╔═══════════════╗                      
                            ║ MAX ITERS HIT ║                      
                            ║ RETURN RESULT ║ (satisfied=false)   
                            ╚═══════════════╝                      
```

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (generate.py)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POST /generate           POST /generate/text                   │
│         ↓                         ↓                              │
│    vision_service         (skip vision)                         │
│         ↓                         ↓                              │
│    agent_service          agent_service                         │
│         ↓                         ↓                              │
│    codegen_service       codegen_service                        │
│         ↓                         ↓                              │
│    file_service          file_service                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  POST /refine-iterative (NEW)                          │   │
│  │           ↓                                              │   │
│  │    refinement_service.refine_until_satisfied()         │   │
│  │           ↓                                              │   │
│  │    [LOOP: render → compare → refine → repeat]          │   │
│  │           ↓                                              │   │
│  │    file_service (save refined)                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Vision      │  │  Rendering   │  │  Comparison  │
│  Service     │  │  Service     │  │  Service     │
├──────────────┤  ├──────────────┤  ├──────────────┤
│ • Ollama     │  │ • OpenSCAD   │  │ • Vision     │
│ • HF API     │  │ • CLI render │  │   Model      │
│              │  │ • PNG output │  │ • Structured │
│              │  │              │  │   feedback   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ↓
                    ┌──────────────┐
                    │ Code Model   │
                    │ (Refinement) │
                    ├──────────────┤
                    │ • Ollama     │
                    │ • Modifies   │
                    │   existing   │
                    │   code       │
                    └──────────────┘
```

## Service Dependencies

```
generate.py (API router)
    ├── vision_service
    │   ├── config.get_settings()
    │   └── prompts.VISION_DESCRIPTION_PROMPT
    │
    ├── agent_service
    │   └── openai (gpt-4o)
    │
    ├── codegen_service
    │   ├── config.get_settings()
    │   ├── prompts.STRICT_CODE_PROMPT
    │   ├── prompts.ITERATIVE_REFINEMENT_PROMPT (new)
    │   └── tools (strip_code_fences, etc.)
    │
    ├── file_service
    │   └── config.get_settings()
    │
    └── refinement_service (NEW)
        ├── render_service (NEW)
        │   ├── config.get_settings()
        │   └── subprocess (openscad)
        │
        ├── comparison_service (NEW)
        │   ├── config.get_settings()
        │   ├── prompts.ITERATIVE_COMPARISON_PROMPT (new)
        │   └── vision_service (reuses same model)
        │
        ├── codegen_service.refine_scad_code (new function)
        │
        └── file_service
```

## Request/Response Flow

### Single Pass Generation
```
POST /generate
├── Image + Prompt
└─ Vision → Description
  └─ CodeGen → SCAD
   └─ File → Path
    └─ Response 200 OK
```

### Iterative Refinement (NEW)
```
POST /refine-iterative
├── SCAD Code + Image
│
└─ Loop (1..N):
  ├─ Render SCAD → PNG
  ├─ Compare → Feedback
  ├─ Refine → New SCAD
  └─ Check Satisfaction
│
└─ File → Path
 └─ Response 200 OK
```

## Message Flow During Loop

```
Iteration 1:
┌─────────┬──────────┬──────────────┬──────────┐
│ Render  │ Compare  │ Feedback     │ Refine   │
├─────────┼──────────┼──────────────┼──────────┤
│ SCAD v1 │ Input ✓  │ "increase    │ SCAD v2  │
│   ↓     │ Render ✗ │  diameter    │   ↓      │
│ PNG 1   │   ↓      │  by 2mm"     │          │
│         │ confidence: 0.42        │          │
└─────────┴──────────┴──────────────┴──────────┘

Iteration 2:
┌─────────┬──────────┬──────────────┬──────────┐
│ Render  │ Compare  │ Feedback     │ Refine   │
├─────────┼──────────┼──────────────┼──────────┤
│ SCAD v2 │ Input ✓  │ "reduce wall │ SCAD v3  │
│   ↓     │ Render ✓ │  thickness   │   ↓      │
│ PNG 2   │   ↓      │  to 1.5mm"   │          │
│         │ confidence: 0.68        │          │
└─────────┴──────────┴──────────────┴──────────┘

Iteration 3:
┌─────────┬──────────┬──────────────┬──────────┐
│ Render  │ Compare  │ Feedback     │ [DONE]   │
├─────────┼──────────┼──────────────┼──────────┤
│ SCAD v3 │ Input ✓  │ "None,       │ Return   │
│   ↓     │ Render ✓ │  satisfied"  │ SCAD v3  │
│ PNG 3   │   ↓      │              │          │
│         │ confidence: 0.92        │          │
│         │ is_satisfied: true      │          │
└─────────┴──────────┴──────────────┴──────────┘
```

## File System Organization

```
Vision-CAD/
├── main.py                           (FastAPI app entry)
├── generate.py                       (API router)
│
├── Services:
├── vision_service.py                 (Vision model calls)
├── agent_service.py                  (Agent/tool selection)
├── codegen_service.py                (Code generation + NEW: refine)
├── file_service.py                   (Save SCAD files)
├── render_service.py                 (NEW: SCAD → PNG)
├── comparison_service.py             (NEW: Vision comparison)
├── refinement_service.py             (NEW: Loop orchestration)
│
├── Config:
├── config.py                         (Settings)
├── schemas.py                        (Pydantic models + NEW schemas)
├── prompts.py                        (System prompts + NEW prompts)
├── tools.py                          (Utilities)
├── agent_service.py                  (OpenAI agent)
│
├── Documentation:
├── ITERATIVE_REFINEMENT.md           (Detailed guide)
├── QUICK_START.md                    (Quick reference)
├── ARCHITECTURE.md                   (This file)
│
└── outputs/
    └── *.scad                        (Generated/refined SCAD files)
```

## Prompt Flow

```
┌──────────────────────┐
│   Input Image        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ VISION_DESCRIPTION_PROMPT            │
│ Vision Model analyzes image          │
│ Returns: text description            │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ STRICT_CODE_PROMPT                   │
│ Code Model generates initial SCAD    │
│ Returns: OpenSCAD code               │
└──────────┬───────────────────────────┘
           │
           ├─────────────────────────────┐
           │                             │
           ▼                             │
┌──────────────────────────────────────┐│
│ [LOOP]                               ││
│                                      ││
│ ITERATIVE_COMPARISON_PROMPT          ││
│ Vision Model compares images         ││
│ Returns: structured feedback         ││
│          (SATISFIED, CONFIDENCE,     ││
│           FEEDBACK, REASONING)       ││
└──────────┬───────────────────────────┘│
           │                             │
           ▼                             │
   ┌───────────────────┐               │
   │ Satisfied?        │               │
   │ (or high conf?)   │               │
   └───────┬───────────┘               │
           │                            │
       NO  ├──────────────────┐         │
           │                  │         │
           ▼                  ▼         │
┌──────────────────────────────────────┐│
│ ITERATIVE_REFINEMENT_PROMPT (NEW)    ││
│ Code Model refines SCAD              ││
│ Returns: modified OpenSCAD code      ││
└──────────┬───────────────────────────┘│
           │                            │
           └────────────────────────────┘
                      │
                     YES
                      │
                      ▼
                   [EXIT LOOP]
                   Return final SCAD
```

## Error Handling Flow

```
OpenSCAD Render Error
├─ Capture error message
├─ Add to feedback: "Syntax error: ..."
├─ Code Model refines for syntax
├─ Loop continues (iteration doesn't count)
└─ Try again

Vision Model Output Parse Error
├─ Use raw response as feedback
├─ Code Model does best effort
├─ Loop continues (may be suboptimal)
└─ Try again

Max Iterations Reached
├─ Return satisfied=false
├─ Return feedback_history
├─ Final SCAD is still valid
└─ User can retry with different params

Code Generation Error
├─ Retry once with simpler feedback
├─ If still fails, break loop
└─ Return current best SCAD
```

## Configuration Points

```
Environment (.env)
├── OLLAMA_BASE_URL
│   ├── render_service (not used, local openscad)
│   ├── comparison_service (vision model)
│   └── codegen_service (code model)
│
├── CODE_MODEL
│   └── codegen_service.refine_scad_code()
│
├── VISION_MODEL
│   └── comparison_service.compare_renders()
│
└── OUTPUT_DIR
    └── file_service, render_service

Request Parameters (/refine-iterative)
├── max_iterations (default 10)
├── confidence_threshold (default 0.75)
└── [scad_code, input_image_bytes required]

Prompt Parameters
├── Vision comparison temperature: 0.3
├── Code refine temperature: 0.2
└── [modifiable in prompts.py or services]

Render Parameters (render_service.py)
├── Image size: 800x600
├── Camera: isometric, distance=80
├── Color scheme: DeepOcean
└── [modifiable in render_service.py]
```

---

See `ITERATIVE_REFINEMENT.md` for detailed documentation and `QUICK_START.md` for usage examples.
