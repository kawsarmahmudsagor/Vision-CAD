from pydantic import BaseModel
from typing import Optional, List, Any


class ParameterModel(BaseModel):
    name:  str
    value: str | int | float | bool
    type:  str   # "number" | "boolean" | "string"


class GenerateRequest(BaseModel):
    """Text-only generation (no image)."""
    prompt:    str
    base_code: Optional[str] = None
    error:     Optional[str] = None


class GenerateResponse(BaseModel):
    title:          str
    scad_code:      str
    scad_file_path: str
    parameters:     List[ParameterModel] = []
    description:    str   # vision model output
    message:        str   # agent conversational reply
    # New: geometry context and validation info (None when no COCO provided)
    geometry_context:  Optional[dict] = None
    constraints:       Optional[List[dict]] = None
    validation_report: Optional[dict] = None
    iterations:        int = 1


class ParameterUpdate(BaseModel):
    name:  str
    value: str


class ApplyParametersRequest(BaseModel):
    scad_code: str
    updates:   List[ParameterUpdate]


class ApplyParametersResponse(BaseModel):
    scad_code:      str
    scad_file_path: str
    parameters:     List[ParameterModel] = []