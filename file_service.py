"""
File service — saves generated OpenSCAD code to disk.
"""
import os
import re
import uuid
from pathlib import Path
from config import get_settings


def _safe_slug(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug or "model"


def save_scad_file(code: str, title: str = "model") -> str:
    """
    Write `code` to <OUTPUT_DIR>/<slug>_<uuid>.scad and return the file path.
    """
    settings = get_settings()
    out_dir = Path(settings.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = _safe_slug(title)
    uid = uuid.uuid4().hex[:8]
    filename = f"{slug}_{uid}.scad"
    file_path = out_dir / filename

    file_path.write_text(code, encoding="utf-8")
    return str(file_path)
