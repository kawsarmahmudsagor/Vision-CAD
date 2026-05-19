"""
Vision-CAD — FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from generate import router

app = FastAPI(
    title="Vision-CAD",
    description=(
        "Takes an image → vision model describes it → "
        "agent decides tool → code-gen model outputs OpenSCAD → saves .scad file."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
