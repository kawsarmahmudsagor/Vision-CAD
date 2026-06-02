"""
Render service — converts OpenSCAD code to PNG preview images.

Calls the openscad binary to render SCAD files to PNG format.
Used in the iterative refinement loop to visualize model changes.
Handles headless rendering via Xvfb (X virtual framebuffer).
"""
import os
import subprocess
import tempfile
from pathlib import Path
from config import get_settings


def _get_openscad_command(scad_path: str, output_png_path: str) -> tuple[list[str], dict]:
    """
    Build the OpenSCAD command and environment for rendering.
    
    Returns:
        (command_list, environment_dict) tuple
    """
    env = os.environ.copy()
    
    # Base OpenSCAD command
    cmd = [
        "openscad",
        "-o", output_png_path,
        "--imgsize", "800,600",
        "--camera", "0,0,0,60,0,45,80",
        "--colorscheme", "DeepOcean",
        scad_path,
    ]
    
    # Check if xvfb-run is available (standard for headless rendering)
    try:
        result = subprocess.run(["which", "xvfb-run"], capture_output=True, text=True)
        if result.returncode == 0:
            # xvfb-run is available; use it
            cmd = ["xvfb-run", "-a"] + cmd
            return cmd, env
    except Exception:
        pass
    
    # Fallback: use Mesa software renderer if no display
    if "DISPLAY" not in env:
        env["LIBGL_ALWAYS_INDIRECT"] = "1"  # Force indirect rendering
        env["GALLIUM_DRIVER"] = "llvmpipe"   # Use Mesa software rasterizer
        env["LIBGL_DEBUG"] = "verbose"       # Help debug rendering issues
    
    return cmd, env


async def render_scad_to_png(scad_code: str, output_png_path: str | None = None) -> bytes:
    """
    Render OpenSCAD code to PNG and return the image bytes.

    Args:
        scad_code: Raw OpenSCAD code to render.
        output_png_path: Optional path to save the PNG. If None, uses a temp file.

    Returns:
        PNG image bytes.

    Raises:
        RuntimeError: If OpenSCAD rendering fails.
    """
    settings = get_settings()

    # Write SCAD code to a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".scad",
        delete=False,
        encoding="utf-8"
    ) as scad_file:
        scad_file.write(scad_code)
        scad_path = scad_file.name

    try:
        # Determine output PNG path
        if output_png_path is None:
            png_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            output_png_path = png_file.name
            png_file.close()

        # Get command and environment for rendering
        cmd, env = _get_openscad_command(scad_path, output_png_path)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"OpenSCAD rendering failed:\n{result.stderr}"
            )

        # Read and return PNG bytes
        png_path = Path(output_png_path)
        if not png_path.exists():
            raise RuntimeError(f"OpenSCAD did not produce output file: {output_png_path}")

        png_bytes = png_path.read_bytes()
        return png_bytes

    finally:
        # Clean up temporary SCAD file
        try:
            Path(scad_path).unlink()
        except OSError:
            pass


async def render_scad_to_png_file(
    scad_code: str,
    output_dir: str | None = None
) -> str:
    """
    Render OpenSCAD code to PNG and save to disk.

    Args:
        scad_code: Raw OpenSCAD code to render.
        output_dir: Directory to save PNG. If None, uses OUTPUT_DIR from config.

    Returns:
        Path to the saved PNG file.
    """
    settings = get_settings()
    out_dir = Path(output_dir or settings.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    import uuid
    png_filename = f"render_{uuid.uuid4().hex[:8]}.png"
    png_path = str(out_dir / png_filename)

    await render_scad_to_png(scad_code, png_path)
    return png_path
