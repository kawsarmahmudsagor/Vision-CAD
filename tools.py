"""
Tool definitions (mirrored from index.ts) and OpenSCAD parameter parser.
"""
import re
from typing import Any

# ── OpenAI tool schemas ────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "build_parametric_model",
            "description": (
                "Generate or update an OpenSCAD model from user intent and context. "
                "Include parameters and ensure the model is manifold and 3D-printable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "User request for the model",
                    },
                    "base_code": {
                        "type": "string",
                        "description": "Existing OpenSCAD code to modify",
                    },
                    "error": {
                        "type": "string",
                        "description": "OpenSCAD error message to fix",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_parameter_changes",
            "description": (
                "Apply simple parameter updates to the current artifact "
                "without re-generating the whole model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["name", "value"],
                        },
                    }
                },
                "required": ["updates"],
            },
        },
    },
]

# ── Parameter parser (mirrors parseParameter.ts) ──────────────────────────────

_NUMBER_RE = re.compile(
    r"^\s*([\w_]+)\s*=\s*(-?\d+(?:\.\d+)?)\s*;",
    re.MULTILINE,
)
_BOOL_RE = re.compile(
    r"^\s*([\w_]+)\s*=\s*(true|false)\s*;",
    re.MULTILINE,
)
_STRING_RE = re.compile(
    r'^\s*([\w_]+)\s*=\s*"([^"]*)"\s*;',
    re.MULTILINE,
)


def parse_parameters(code: str) -> list[dict[str, Any]]:
    """Extract top-level variable declarations from OpenSCAD code."""
    params: list[dict[str, Any]] = []
    seen: set[str] = set()

    for match in _BOOL_RE.finditer(code):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            params.append(
                {"name": name, "value": match.group(2) == "true", "type": "boolean"}
            )

    for match in _NUMBER_RE.finditer(code):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            raw = match.group(2)
            params.append(
                {
                    "name": name,
                    "value": float(raw) if "." in raw else int(raw),
                    "type": "number",
                }
            )

    for match in _STRING_RE.finditer(code):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            params.append(
                {"name": name, "value": match.group(2), "type": "string"}
            )

    return params


def escape_regex(s: str) -> str:
    return re.escape(s)


def apply_parameter_patch(
    code: str, updates: list[dict[str, str]]
) -> str:
    """Deterministically patch parameter values in OpenSCAD code."""
    current_params = {p["name"]: p for p in parse_parameters(code)}
    patched = code

    for upd in updates:
        target = current_params.get(upd["name"])
        if target is None:
            continue

        # Coerce to correct Python type
        raw_value = upd["value"]
        if target["type"] == "number":
            coerced: Any = float(raw_value) if "." in raw_value else int(raw_value)
            replacement_str = str(coerced)
        elif target["type"] == "boolean":
            coerced = raw_value.lower() == "true"
            replacement_str = "true" if coerced else "false"
        else:
            coerced = raw_value
            replacement_str = f'"{coerced}"'

        pattern = re.compile(
            rf"^(\s*{re.escape(target['name'])}\s*=\s*)[^;]+;",
            re.MULTILINE,
        )
        patched = pattern.sub(rf"\g<1>{replacement_str};", patched)

    return patched


# ── OpenSCAD code extractor (fallback) ───────────────────────────────────────

def score_openscad_code(code: str) -> int:
    if not code or len(code) < 20:
        return 0
    score = 0
    patterns = [
        r"\b(cube|sphere|cylinder|polyhedron)\s*\(",
        r"\b(union|difference|intersection)\s*\(\s*\)",
        r"\b(translate|rotate|scale|mirror)\s*\(",
        r"\b(linear_extrude|rotate_extrude)\s*\(",
        r"\b(module|function)\s+\w+\s*\(",
        r"\$fn\s*=",
        r"\bfor\s*\(\s*\w+\s*=\s*\[",
        r';\s*$',
        r"//.*$",
    ]
    for pat in patterns:
        score += len(re.findall(pat, code, re.MULTILINE))
    var_decls = re.findall(r"^\s*\w+\s*=\s*[^;]+;", code, re.MULTILINE)
    score += min(len(var_decls), 5)
    return score


def extract_openscad_from_text(text: str) -> str | None:
    if not text:
        return None
    fence_re = re.compile(r"```(?:openscad)?\s*\n?([\s\S]*?)\n?```", re.MULTILINE)
    best_code = None
    best_score = 0
    for m in fence_re.finditer(text):
        code = m.group(1).strip()
        s = score_openscad_code(code)
        if s > best_score:
            best_score = s
            best_code = code
    if best_code and best_score >= 3:
        return best_code
    if score_openscad_code(text) >= 5:
        return text.strip()
    return None


def strip_code_fences(s: str) -> str:
    s = re.sub(r"^```(?:openscad)?\s*\n?", "", s)
    s = re.sub(r"\n?```\s*$", "", s)
    return s
