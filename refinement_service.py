"""
Refinement service — orchestrates the iterative SCAD refinement loop.

Handles the main feedback loop:
  1. Render current SCAD to PNG
  2. Vision model compares PNG vs input image
  3. Code model refines SCAD based on feedback
  4. Repeat until satisfied

This module coordinates render_service, comparison_service, and codegen_service.
"""
import re
import base64
import httpx
from config import get_settings
from render_service import render_scad_to_png
from comparison_service import compare_renders, get_comparison_feedback
from codegen_service import refine_scad_code
from prompts import ITERATIVE_REFINEMENT_PROMPT


def validate_scad_syntax(code: str) -> tuple[bool, str]:
    """
    Basic SCAD syntax validation to catch common errors.

    Args:
        code: OpenSCAD code to validate.

    Returns:
        (is_valid, error_message) tuple
    """
    if not code or len(code) < 10:
        return False, "Code is too short or empty"

    # Unbalanced brackets are a strong signal of truncated/broken output.
    open_parens = code.count("(") - code.count(")")
    open_braces = code.count("{") - code.count("}")
    open_brackets = code.count("[") - code.count("]")

    if open_parens != 0:
        return False, f"Unbalanced parentheses: {open_parens} unclosed"
    if open_braces != 0:
        return False, f"Unbalanced braces: {open_braces} unclosed"
    if open_brackets != 0:
        return False, f"Unbalanced brackets: {open_brackets} unclosed"

    # Must contain at least one real OpenSCAD object/operation.
    has_object = re.search(
        r"\b(module|function|color|translate|rotate|scale|mirror|resize|"
        r"cube|sphere|cylinder|polyhedron|circle|square|polygon|text|"
        r"union|difference|intersection|hull|minkowski|offset|"
        r"linear_extrude|rotate_extrude|for|surface|import)\b",
        code,
    )
    if not has_object:
        return False, "No OpenSCAD objects or modules found"

    # NOTE: the previous "incomplete statement" check (line ending in an
    # operator) is intentionally removed. It false-flagged valid multi-line
    # expressions such as:
    #     x = a +
    #         b;
    # which are extremely common in generated OpenSCAD. Unbalanced-bracket
    # detection above already catches genuinely truncated output.
    return True, ""


async def refine_until_satisfied(
    input_image_bytes: bytes,
    initial_scad_code: str,
    vision_description: str,
    user_prompt: str,
    max_iterations: int = 10,
    confidence_threshold: float = 0.75,
) -> dict:
    """
    Run the iterative refinement loop until the model is satisfied with the match.

    Args:
        input_image_bytes: Original reference image (bytes).
        initial_scad_code: Initial SCAD code to refine.
        vision_description: Description of the input image from vision model.
        user_prompt: Original user prompt/request.
        max_iterations: Maximum number of refinement iterations.
        confidence_threshold: Minimum confidence to accept as satisfied.

    Returns:
        dict with keys:
            - "final_scad_code": str — final OpenSCAD code
            - "iterations": int — number of iterations performed
            - "satisfied": bool — whether final model was approved
            - "final_png_bytes": bytes — final rendered PNG
            - "feedback_history": list — all feedback from each iteration
            - "render_history": list — all rendered PNG paths (for debugging)
    """
    settings = get_settings()
    current_scad = initial_scad_code
    iteration = 0
    feedback_history = []
    render_history = []

    while iteration < max_iterations:
        iteration += 1

        # --- Pre-render validation ---
        is_valid, syntax_error = validate_scad_syntax(current_scad)
        if not is_valid:
            feedback_history.append({
                "iteration": iteration,
                "error": f"Syntax validation failed: {syntax_error}",
            })
            # Request a code fix for the syntax error — but never let a refiner
            # failure abort the whole loop. If it can't help, stop and return
            # the best code we already have.
            error_feedback = f"SCAD syntax error: {syntax_error}\nFix the code and try again."
            try:
                new_scad = await refine_scad_code(
                    current_scad,
                    error_feedback,
                    vision_description,
                    user_prompt,
                )
            except Exception as e:
                feedback_history.append({
                    "iteration": iteration,
                    "error": f"Refiner could not fix syntax: {e}",
                })
                break
            if new_scad == current_scad:
                # Refiner made no change — it can't fix this; stop looping.
                break
            current_scad = new_scad
            continue

        # --- Step 1: Render current SCAD to PNG ---
        try:
            rendered_png_bytes = await render_scad_to_png(current_scad)
        except RuntimeError as e:
            feedback_history.append({
                "iteration": iteration,
                "error": f"Render failed: {str(e)}",
            })
            # Request a code fix for the render error, guarded the same way.
            error_feedback = f"OpenSCAD rendering failed: {str(e)}\nFix the syntax error and try again."
            try:
                new_scad = await refine_scad_code(
                    current_scad,
                    error_feedback,
                    vision_description,
                    user_prompt,
                )
            except Exception as ce:
                feedback_history.append({
                    "iteration": iteration,
                    "error": f"Refiner could not fix render error: {ce}",
                })
                break
            if new_scad == current_scad:
                break
            current_scad = new_scad
            continue

        # Store render
        render_history.append({"iteration": iteration, "png_bytes_len": len(rendered_png_bytes)})

        # --- Step 2: Vision model compares renders ---
        comparison = await compare_renders(
            input_image_bytes,
            rendered_png_bytes,
            iteration=iteration,
        )

        feedback_history.append({
            "iteration": iteration,
            "is_satisfied": comparison["is_satisfied"],
            "confidence": comparison["confidence"],
            "feedback": comparison["feedback"],
            "reasoning": comparison["reasoning"],
        })

        # --- Step 3: Check if satisfied ---
        if comparison["is_satisfied"] or comparison["confidence"] >= confidence_threshold:
            return {
                "final_scad_code": current_scad,
                "iterations": iteration,
                "satisfied": True,
                "final_png_bytes": rendered_png_bytes,
                "feedback_history": feedback_history,
                "render_history": render_history,
            }

        # --- Step 4: Code model refines based on feedback ---
        feedback = comparison["feedback"] or comparison["raw_response"]

        try:
            new_scad = await refine_scad_code(
                current_scad,
                feedback,
                vision_description,
                user_prompt,
            )
        except Exception as e:
            feedback_history.append({
                "iteration": iteration,
                "error": f"Code generation failed: {str(e)}",
            })
            # Try one more time with a simpler request.
            try:
                new_scad = await refine_scad_code(
                    current_scad,
                    "Make a small adjustment: " + feedback[:100],
                    vision_description,
                    user_prompt,
                )
            except Exception:
                break

        if new_scad == current_scad:
            # Refiner returned the code unchanged — no further progress possible.
            break
        current_scad = new_scad

    # Max iterations reached (or loop stopped early). Return the best attempt.
    return {
        "final_scad_code": current_scad,
        "iterations": iteration,
        "satisfied": False,
        "final_png_bytes": rendered_png_bytes if 'rendered_png_bytes' in locals() else b'',
        "feedback_history": feedback_history,
        "render_history": render_history,
    }


async def single_refinement_step(
    current_scad_code: str,
    input_image_bytes: bytes,
    rendered_png_bytes: bytes,
    vision_description: str,
    user_prompt: str,
) -> dict:
    """
    Run a single refinement iteration (for debugging/manual control).

    Args:
        current_scad_code: Current SCAD code.
        input_image_bytes: Original reference image.
        rendered_png_bytes: Current rendered PNG.
        vision_description: Image description.
        user_prompt: Original request.

    Returns:
        dict with:
            - "comparison": comparison result
            - "refined_scad": refined code (if feedback given)
            - "feedback": the feedback message
    """
    comparison = await compare_renders(input_image_bytes, rendered_png_bytes)

    refined_scad = None
    if not comparison["is_satisfied"]:
        feedback = comparison["feedback"] or comparison["raw_response"]
        refined_scad = await refine_scad_code(
            current_scad_code,
            feedback,
            vision_description,
            user_prompt,
        )

    return {
        "comparison": comparison,
        "refined_scad": refined_scad,
        "feedback": comparison["feedback"],
        "is_satisfied": comparison["is_satisfied"],
    }