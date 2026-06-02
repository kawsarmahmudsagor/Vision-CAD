from pydantic import BaseModel
from typing import Optional, List, Literal


class ParameterModel(BaseModel):
    name: str
    value: str | int | float | bool
    type: str  # "number" | "boolean" | "string"


class ArtifactModel(BaseModel):
    title: str
    version: str = "v1"
    code: str
    parameters: List[ParameterModel] = []


class GenerateRequest(BaseModel):
    """Request body for text-only generation (no image)."""
    prompt: str
    base_code: Optional[str] = None
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    title: str
    scad_code: str
    scad_file_path: str
    parameters: List[ParameterModel] = []
    description: str  # vision model output
    message: str      # agent conversational reply
    image_key: Optional[str] = None
    initial_scad_code: Optional[str] = None
    refined: bool = False
    refinement_iterations: Optional[int] = None
    refinement_satisfied: Optional[bool] = None
    refinement_feedback_history: Optional[List[dict]] = None
    refinement_render_history: Optional[List[dict]] = None
    final_png_base64: Optional[str] = None


class ParameterUpdate(BaseModel):
    name: str
    value: str


class ApplyParametersRequest(BaseModel):
    scad_code: str
    updates: List[ParameterUpdate]


class ApplyParametersResponse(BaseModel):
    scad_code: str
    scad_file_path: str
    parameters: List[ParameterModel] = []


class IterativeRefinementRequest(BaseModel):
    """Request for iterative SCAD refinement based on visual comparison."""
    prompt: str | None = None
    image_key: Optional[str] = None
    input_image_bytes: Optional[str] = None  # base64 encoded image
    scad_code: Optional[str] = None
    max_iterations: int = 10
    confidence_threshold: float = 0.75
    vision_description: str = ""  # Optional description of input image


class IterativeFeedback(BaseModel):
    """Single feedback iteration result."""
    iteration: int
    is_satisfied: bool
    confidence: float
    feedback: str
    reasoning: str


class IterativeRefinementResponse(BaseModel):
    """Response from iterative refinement loop."""
    final_scad_code: str
    scad_file_path: str
    iterations: int
    satisfied: bool
    final_png_bytes: Optional[bytes] = None  # base64 or binary?
    feedback_history: List[dict]
    render_history: List[dict]