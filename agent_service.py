"""
Agent service — routes the user request to the correct tool without any
external LLM dependency.

Two tools:
  - apply_parameter_changes  → user wants to tweak a value in existing code
  - build_parametric_model   → everything else (new model or structural change)

The routing is rule-based:
  1. If there is no base_code, it must be a new build.
  2. If the prompt matches a "change X to Y" / "set X to N" pattern AND
     the named variable actually exists in the current code → apply patch.
  3. Otherwise → build.
"""
import re
from tools import parse_parameters

# Patterns that signal a simple parameter tweak
_PARAM_CHANGE_PATTERNS = [
    # "change height to 80", "set radius to 5.5", "update wall_thickness to 3"
    r"\b(?:change|set|update|make|adjust)\s+([\w_]+)\s+(?:to|=)\s*(-?[\d.]+)",
    # "height = 80", "radius=5.5"
    r"\b([\w_]+)\s*=\s*(-?[\d.]+)\b",
    # "increase/decrease height by 10", "height to 80"
    r"\b([\w_]+)\s+to\s+(-?[\d.]+)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PARAM_CHANGE_PATTERNS]


def _extract_param_updates(prompt: str, base_code: str) -> list[dict] | None:
    """
    Try to extract {name, value} pairs from the prompt.
    Only returns updates for variables that actually exist in base_code,
    so we don't accidentally route a build request to the patcher.
    """
    existing = {p["name"] for p in parse_parameters(base_code)}
    if not existing:
        return None

    updates = []
    for pattern in _COMPILED:
        for match in pattern.finditer(prompt):
            name = match.group(1)
            value = match.group(2)
            if name in existing:
                updates.append({"name": name, "value": value})

    # Deduplicate by name (last match wins)
    seen = {}
    for u in updates:
        seen[u["name"]] = u
    return list(seen.values()) if seen else None


async def run_agent(
    user_text: str,
    vision_description: str | None = None,
    base_code: str | None = None,
) -> dict:
    """
    Decide which tool to call based on the user's request.

    Returns:
      {
        "text":      <short reply for the UI>,
        "tool_name": "build_parametric_model" | "apply_parameter_changes",
        "tool_args": { ... }
      }
    """
    # ── Rule 1: no existing code → must be a fresh build ─────────────────────
    if not base_code:
        return {
            "text": f"Building a parametric model for: {user_text}",
            "tool_name": "build_parametric_model",
            "tool_args": {"text": user_text},
        }

    # ── Rule 2: prompt looks like a parameter tweak AND named var exists ──────
    updates = _extract_param_updates(user_text, base_code)
    if updates:
        names = ", ".join(u["name"] for u in updates)
        return {
            "text": f"Updating parameter(s): {names}.",
            "tool_name": "apply_parameter_changes",
            "tool_args": {"updates": updates},
        }

    # ── Rule 3: everything else is a build / structural change ────────────────
    return {
        "text": f"Modifying the model: {user_text}",
        "tool_name": "build_parametric_model",
        "tool_args": {"text": user_text, "base_code": base_code},
    }