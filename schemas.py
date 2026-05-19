from pydantic import BaseModel
from typing import Optional, List


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
