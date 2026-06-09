"""
renderer.py
──────────────────────────────────────────────────────────────────────────────
Renders an OpenSCAD .scad file to PNG images (top and side views) using
xvfb-run + openscad --render.

The two camera presets produce axis-aligned orthographic projections that
map back to the same pixel space as the COCO annotations.

Public API:
    render_views(scad_path, output_dir) -> {"top": path, "side": path} | None
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# OpenSCAD camera string: "translateX,Y,Z,rotX,Y,Z,dist"
# For a ring lying in the XZ plane (bore along Y):
#   Top view  → looking straight down the Y axis
#   Side view → looking from a roughly front-on angle (standard side elevation)
_CAMERA_TOP  = "0,0,0,90,0,0,120"   # look down Y axis
_CAMERA_SIDE = "0,0,0,0,0,0,120"    # look along Z axis (side elevation)

_RENDER_SIZE  = "800,800"
_TIMEOUT_SECS = 120


def _run_openscad(scad_path: str, png_path: str, camera: str) -> bool:
    """Synchronous OpenSCAD render call. Returns True on success."""
    cmd = [
        "xvfb-run", "-a",
        "openscad",
        "--render",
        f"--camera={camera}",
        f"--imgsize={_RENDER_SIZE}",
        "--projection=o",          # orthographic
        "-o", png_path,
        scad_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECS,
        )
        if result.returncode != 0:
            logger.warning(f"OpenSCAD render failed: {result.stderr[:400]}")
            return False
        if not Path(png_path).exists():
            logger.warning(f"OpenSCAD completed but {png_path} was not created")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"OpenSCAD render timed out after {_TIMEOUT_SECS}s")
        return False
    except Exception as e:
        logger.error(f"OpenSCAD render error: {e}")
        return False


async def render_views(scad_path: str, output_dir: str) -> dict | None:
    """
    Render top and side PNG views of the given .scad file.

    Returns {"top": str, "side": str} paths on success, or None on failure.
    Runs blocking subprocess in an executor so it doesn't block the event loop.
    """
    scad_path = str(scad_path)
    stem      = Path(scad_path).stem
    top_png   = os.path.join(output_dir, f"{stem}_top.png")
    side_png  = os.path.join(output_dir, f"{stem}_side.png")

    loop = asyncio.get_event_loop()

    ok_top  = await loop.run_in_executor(None, _run_openscad, scad_path, top_png,  _CAMERA_TOP)
    ok_side = await loop.run_in_executor(None, _run_openscad, scad_path, side_png, _CAMERA_SIDE)

    if ok_top and ok_side:
        logger.info(f"Rendered views: {top_png}, {side_png}")
        return {"top": top_png, "side": side_png}
    if ok_top:
        logger.warning("Side view render failed; returning top only")
        return {"top": top_png, "side": None}
    if ok_side:
        logger.warning("Top view render failed; returning side only")
        return {"top": None, "side": side_png}

    logger.error("Both renders failed")
    return None