"""
semantic_recipe.py
──────────────────────────────────────────────────────────────────────────────
Translates each semantic style field into a concrete OpenSCAD *construction
recipe* — not just a label, but an explicit geometric prescription the LLM
can follow without guessing.

The key insight:
    prong_style = "claw"           ← label  (current state — LLM guesses)
    + RECIPE: "Claw prong geometry: ..." ← recipe (LLM knows exactly what to build)

This layer sits between geometry_extractor and codegen_service.
Call build_semantic_recipes(geo_ctx) → returns a string injected into the
GEOMETRY CONTEXT block just before the SPATIAL CONSTRAINTS section.

Pipeline position:
    geometry_extractor.build_geometry_context()
        ↓  geo_ctx
    semantic_recipe.build_semantic_recipes(geo_ctx)
        ↓  recipe_block  (string)
    codegen_service._format_geometry_block()   ← inject here
        ↓  full prompt section
    LLM (OpenSCAD codegen)
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Prong style recipes
# Each recipe gives the LLM:
#   • the geometric form in plain English
#   • the OpenSCAD primitive strategy (hull of spheres, cylinder+sphere, etc.)
#   • the critical proportions relative to stone_radius and prong_radius
#   • what "gripping the stone" looks like for this style
# ─────────────────────────────────────────────────────────────────────────────

_PRONG_RECIPES: dict[str, str] = {

    "claw": """\
Claw prong — a slender tapered wire that rises from the band base and curves inward
to hook over the stone girdle. This is the most common prong type.

VISUAL: thin wire, visible from side, hooks inward at tip like a bird talon.

CONNECTIVITY PATTERN (critical for correct assembly):
  Prongs do NOT float independently. They converge/merge at the stone base.
  The bottom of all prongs meet at a shared gallery basket or collar at the
  base of the stone, which itself sits on top of the band.
  Pattern:  band → gallery_basket → [prongs diverge outward] → stone girdle

COORDINATE SYSTEM: all Z values below are LOCAL to stone_setting_module().
  local Z = 0          → base of setting (where it attaches to band top)
  local Z = stone_h    → stone table (top of gem)
  local Z ≈ stone_h + 0.8 → prong tip (hooks over girdle)

CRITICAL PROPORTIONS (enforce regardless of input):
  prong_radius  = stone_radius * 0.10   // thin wire — max 0.12, never > 0.5mm abs
  prong_radius  = max(prong_radius, 0.25)
  radial_dist   = stone_radius * 0.95   // prong outside stone edge, touching girdle

OpenSCAD strategy — TWO hull() calls, then union() (NEVER one hull of all 3):
  shaft_top_z   = stone_h * 0.68        // local Z where shaft ends / hook begins
  tip_z         = stone_h + 0.8         // local Z of hook tip (above table)
  tip_inset     = prong_radius * 1.8    // radial inward pull of the hook

  module claw_prong(angle_deg) {
    rotate([0, 0, angle_deg])
    color(metal_color)
    union() {
      // Shaft: straight section from base up to near stone table
      hull() {
        translate([radial_dist, 0, 0])
          sphere(r = prong_radius, $fn = 16);
        translate([radial_dist, 0, shaft_top_z])
          sphere(r = prong_radius * 0.85, $fn = 16);
      }
      // Hook: curves inward over the girdle
      hull() {
        translate([radial_dist, 0, shaft_top_z])
          sphere(r = prong_radius * 0.85, $fn = 16);
        translate([radial_dist - tip_inset, 0, tip_z])
          sphere(r = prong_radius * 0.70, $fn = 16);
      }
    }
  }

  for (a = prong_angles) claw_prong(a);
  Result: thin wire with distinct inward hook — not a ball, not a column, not a fat blob.
""",

    "round_tip": """\
Round-tip prong — straight or gently tapered shaft ending in a polished ball.
OpenSCAD strategy:
  1. Shaft: cylinder(r = prong_radius, h = prong_height, $fn=16) at radial_distance.
     Taper optional: cylinder(r1 = prong_radius, r2 = prong_radius * 0.85, h = prong_height).
  2. Ball tip: sphere(r = prong_radius * 1.25, $fn=20) translated to the top of the shaft.
     The ball is slightly larger than the shaft radius to give the classic "beaded" tip look.
  3. Combine shaft + ball with union().
  4. No inward curve — the ball sits flush above the stone table, not over the girdle.
  5. Base of shaft starts at prong_base_z; tip centre at prong_base_z + prong_height.
  Key parameter: ball_radius = prong_radius * 1.25
""",

    "flat": """\
Flat / tab prong — a rectangular metal tab that holds the stone with a flat face.
OpenSCAD strategy:
  1. Use a rectangular box: cube([tab_width, tab_thickness, tab_height], center=false)
     where tab_width ≈ prong_radius * 3, tab_thickness ≈ prong_radius * 1.2.
  2. Orient so the wide face (tab_width × tab_height) is tangent to the stone girdle.
     Translate to radial_distance - tab_thickness/2 so the inner face kisses the stone.
  3. Add a small chamfer or fillet on the top edge using a 45° cut (difference with a
     rotated cube) to avoid sharp print artefacts.
  4. Rotate each tab so its wide axis is perpendicular to the radial direction (tangent to stone).
  Key parameters: tab_width = prong_radius * 3, tab_thickness = prong_radius * 1.2
""",

    "double_claw": """\
Double-claw (forked) prong — a single shaft that splits into two claw tips at the top,
straddling the stone edge for extra security.
OpenSCAD strategy:
  1. Lower shaft: hull() of base sphere at (radial_distance, 0, prong_base_z) and
     a middle sphere at (radial_distance, 0, stone_base_z + stone_height * 0.5).
  2. Fork split: from the middle point, create TWO tip branches offset ±fork_spread
     along the tangential axis (Y-axis before rotation).
     fork_spread ≈ prong_radius * 1.2
  3. Each fork tip: hull() of middle sphere + a small claw tip sphere at
     (radial_distance * 0.85, ±fork_spread, stone_top_z + tip_overlap).
  4. union() the shaft hull with the two fork hulls.
  5. Result: a Y-shaped prong viewed from the side, two hooks gripping the girdle.
  Key parameters: fork_spread = prong_radius * 1.2, tip_overlap = prong_radius * 0.8
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Stone cut recipes
# ─────────────────────────────────────────────────────────────────────────────

_STONE_CUT_RECIPES: dict[str, str] = {

    "round": """\
Round brilliant cut — rotationally symmetric, built with rotate_extrude or stacked cylinders.
OpenSCAD strategy:
  1. Pavilion (bottom cone): cylinder(r1=0, r2=stone_radius, h=pavilion_h, $fn=48)
     where pavilion_h ≈ stone_height * 0.55.
  2. Table flat top: cylinder(r=table_r, h=0.3, $fn=48)
     where table_r ≈ stone_radius * 0.56.
  3. Crown (frustum between girdle and table):
     cylinder(r1=stone_radius, r2=table_r, h=crown_h, $fn=48)
     where crown_h ≈ stone_height * 0.45.
  4. Stack: pavilion at base_z, then crown on top, table caps the crown.
  5. Color with gem_color; embed in a difference() seat cut from the setting metal.
""",

    "cushion": """\
Cushion cut — square outline with rounded corners; use a Minkowski sum approach.
OpenSCAD strategy:
  1. Base square outline: square([stone_width*0.9, stone_length*0.9], center=true)
     rounded with minkowski() { square(...); circle(r=stone_width*0.07, $fn=32); }
     in a linear_extrude.
  2. Pavilion: scale the rounded square profile from full size at girdle to a point,
     using a hull() between the full-size base and a tiny central sphere.
  3. Crown: similar hull from full girdle profile to a slightly smaller table square.
  4. The "cushion" feel comes entirely from the rounded corner radius (≈7% of width).
""",

    "princess": """\
Princess cut — square outline, sharp corners; use box geometry.
OpenSCAD strategy:
  1. Pavilion: hull() { cube([stone_width, stone_length, 0.01], center=true);
                        translate([0,0,-pavilion_h]) cylinder(r=0.5, h=0.01, $fn=4); }
     This tapers the square base to a near-point.
  2. Crown: cube([stone_width, stone_length, crown_h], center=true) at girdle level
     with a small difference() to create the table facet.
  3. All corners are sharp — no minkowski rounding.
""",

    "oval": """\
Oval cut — elliptical outline; scale a round brilliant along one axis.
OpenSCAD strategy:
  1. Build the round brilliant geometry (see round recipe) with radius = stone_width/2.
  2. Wrap the entire stone in: scale([1, stone_length/stone_width, 1]) round_stone();
     This stretches the circle into an ellipse while preserving height.
  3. stone_length > stone_width for a standard oval.
""",

    "pear": """\
Pear (teardrop) cut — pointed at one end, rounded at the other.
OpenSCAD strategy:
  1. Create a 2D pear outline: hull() { circle(r=stone_width/2, $fn=48);  // round end
                                         translate([0, stone_length*0.45]) circle(r=stone_width*0.12, $fn=32); }
  2. Pavilion: linear_extrude with scale([0.01,0.01]) to taper to a point downward.
     Or use hull() between the full 2D outline and a small sphere at pavilion depth.
  3. Crown: linear_extrude the pear profile to crown_h, then cut table facet.
  4. Orient so the point faces away from the prong cluster (0° / 180° in the setting).
""",

    "marquise": """\
Marquise cut — pointed at both ends, widest in the middle (eye-shaped / navette).
OpenSCAD strategy:
  1. 2D outline: hull() { translate([0,  stone_length/2]) circle(r=0.5, $fn=16);
                           translate([0, -stone_length/2]) circle(r=0.5, $fn=16);
                           circle(r=stone_width/2, $fn=48); }
  2. Pavilion & crown: same linear_extrude-with-scale strategy as pear.
  3. Align the long axis along Y; prongs grip the two pointed tips + two side points.
""",

    "emerald": """\
Emerald cut — rectangular with heavily chamfered corners (step cut).
OpenSCAD strategy:
  1. Outline: use a polygon() with 8 points — a rectangle where each corner is
     replaced by a 45° chamfer cut of size chamfer ≈ stone_width * 0.12.
  2. Extrude the polygon to crown_h; taper to pavilion point with hull().
  3. The distinctive look is the flat table and multiple step facets — approximate
     with two concentric difference() rectangles cut into the crown top.
""",

    "radiant": """\
Radiant cut — rectangular outline with cut corners, but brilliant-style faceting (more sparkle than emerald).
OpenSCAD strategy: identical corner-chamfer approach to emerald cut, but
  add more internal detail facets on the crown. The silhouette is the same 8-sided
  polygon; the visual difference is captured in color and the table facet detail.
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Setting type recipes
# ─────────────────────────────────────────────────────────────────────────────

_SETTING_RECIPES: dict[str, str] = {

    "Prong": """\
Prong setting — stone held by individual metal wires rising from a shared base.

CONNECTIVITY (how everything connects — follow this structure exactly):
  band  →  gallery_basket  →  prongs diverge outward  →  stone girdle
  The gallery basket is the SHARED ROOT of all prongs.
  Without it, prongs float and the stone has no structural base.

ALL Z values below are LOCAL (0 = base of stone_setting_module(), stone sits above):

  module stone_setting_module() {
    stone_radius  = stone_width / 2;
    basket_h      = stone_height * 0.40;   // gallery height (local Z 0 → basket_h)
    prong_r       = stone_radius * 0.10;   // thin wire radius

    // 1. Gallery basket — connects prongs to band, gives setting structural base
    //    Tapered frustum: wide at bottom (matches band), narrow at top (wraps stone)
    color(metal_color)
    difference() {
      cylinder(r1 = stone_radius * 1.25, r2 = stone_radius * 0.85,
               h = basket_h, $fn = 48);
      translate([0, 0, -0.1])
      cylinder(r1 = stone_radius * 0.85, r2 = stone_radius * 0.55,
               h = basket_h + 0.2, $fn = 48);
    }

    // 2. Stone — pavilion tip at local Z=0, table at local Z=stone_height
    translate([0, 0, 0])
    stone_gem_module();

    // 3. Prongs — base at local Z=0, tips hook over girdle at local Z≈stone_height+0.8
    for (a = prong_angles) claw_prong(a);
  }

  Place this module at: translate([0, outer_radius, 0]) rotate([-90,0,0]) stone_setting_module();
""",

    "Bezel": """\
Bezel setting — stone surrounded by a continuous metal rim.
OpenSCAD strategy:
  1. Outer wall: rotate_extrude() of a thin rectangle profile at stone_radius + wall_t.
     wall_t ≈ 0.8 mm typically.
  2. Inner bore: difference() to remove the stone volume — stone sits inside the bezel.
  3. Bezel height ≈ stone_height * 0.40 (covers girdle and lower crown, not the table).
  4. Top edge: add a small rolled lip with hull() circle profile in rotate_extrude.
  NO prongs are present in a bezel setting.
""",

    "Tension": """\
Tension setting — stone appears to float, gripped only by compression from the band ends.
OpenSCAD strategy:
  1. The band has two opposing open ends (a C-shape or gap) with the stone bridging the gap.
  2. Gap width ≈ stone_width * 1.05 (stone fits snugly in the slot).
  3. Each band end has a small curved groove: cylinder(r=stone_radius+0.1, ...) cut as
     a difference() into the inner face of the band end.
  4. No prongs, no bezel, no visible metal over the stone.
""",

    "Channel": """\
Channel setting — a row of small stones set between two parallel metal rails.
OpenSCAD strategy:
  1. Two parallel rails: rectangular bars running along the band shoulder.
  2. Stones sit between the rails, held at the girdle by the rail lips.
  3. Rail height ≈ small_stone_height * 0.6; rail separation ≈ stone_width * 0.9.
  4. Use a for() loop to place evenly-spaced stones between the rails.
  5. Each rail has a small inward lip (difference() chamfer) to grip the stone girdles.
""",

    "Pave": """\
Pavé setting — surface densely set with tiny stones, metal nearly invisible.
OpenSCAD strategy:
  1. Small stones: place on the band surface using spherical_surface_distribution or
     a regular for(angle) for(z_row) loop covering the outer surface.
  2. Each stone: diamond_gem(pave_stone_r) at (outer_radius - 0.2) translated radially.
  3. Stone size ≈ 0.4–0.8 mm radius; spacing ≈ stone_diameter + 0.2 mm gap.
  4. Use an if() guard to skip the zone under the center stone setting.
  5. Metal shows only as tiny bead-like prongs or shared walls between stones (approximate
     with the metal background color showing through).
""",

    "Flush": """\
Flush (gypsy) setting — stone sits level with the metal surface, completely inset.
OpenSCAD strategy:
  1. Drill a conical bore into the band metal: cylinder(r1=stone_radius*1.05, r2=stone_radius*0.7,
     h=stone_height) as a difference() into the band outer surface.
  2. Stone sits in the bore; its table is flush with the metal surface.
  3. No protruding prongs or bezel walls — the stone top is at the same Z as the metal.
  4. A small burnished edge lip ≈ 0.3 mm inward from the stone girdle is the only
     visible metal (model as a thin ring at the bore opening).
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Shank style recipes
# ─────────────────────────────────────────────────────────────────────────────

_SHANK_RECIPES: dict[str, str] = {

    "Plain": """\
Plain shank — uniform circular band, no texture or tapering.
OpenSCAD: rotate_extrude($fn=120) of a rectangular 2D profile.
The cross-section is a simple rect [thickness, width]; use hull() with rounded
corners only if the real ring shows a rounded cross-section.
""",

    "Pave": """\
Pavé shank — band surface set with small diamonds (see Pavé setting recipe).
The band itself is the same rotate_extrude structure as Plain, but
the codegen must include the stone placement loop on the outer surface.
""",

    "Split-Shank": """\
Split-shank — band splits into two separate rails as it approaches the setting.
OpenSCAD strategy:
  1. Lower band (away from setting): standard rotate_extrude tube.
  2. Split zone: the band separates into two arcs. Approximate with two hull() shapes
     that diverge from the single band to two separate wires at the head.
  3. Each rail: a smaller tube (cylinder or thin hull extrusion) ending at the gallery base.
  4. Gap between rails ≈ stone_width * 0.5 at the head, closing to 0 at the opposite side.
""",

    "Tapered": """\
Tapered shank — band is wider at the shoulder (near the setting) and narrows at the back.
OpenSCAD strategy:
  1. Use a 2D profile that varies in width: wider trapezoid cross-section at 0°/180°
     (near setting), narrower rectangle at 90°/270° (back of ring).
  2. Approximate with two rotate_extrude calls — wide cross-section and narrow —
     blended with hull() or a smooth loft via intermediate cross-sections.
  3. Taper ratio: shoulder_width / back_width ≈ 1.4–1.8 typically.
""",

    "Bypass": """\
Bypass shank — two band ends sweep past each other without meeting, like a spiral.
OpenSCAD strategy:
  1. Two tube sweeps rotating from ~-150° to +150° with opposite handedness.
  2. Use rotate_extrude with angle parameter (OpenSCAD 2021+) or split the band
     into two half-arcs offset in Z and rotated.
  3. Each sweep ends near the head, carrying a stone or decorative terminus.
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Ring style recipes
# ─────────────────────────────────────────────────────────────────────────────

_RING_STYLE_RECIPES: dict[str, str] = {

    "Solitaire": """\
Solitaire — single center stone, plain or near-plain band, no side stones.
Head contains only: gallery/basket, prongs, center stone.
Band has no pave, no channel stones, no bypass.
""",

    "Halo": """\
Halo — ring of small stones surrounds the center stone at the same Z level.
The halo stone orbit radius is already in geo_ctx[halo][radial_distance_mm].
Build: a thin platform disk (difference of two cylinders) + for() loop of small gems.
""",

    "Three-Stone": """\
Three-stone — center stone flanked by two smaller accent stones.
Side stones are ~60–70% of center stone width, placed at ±side_offset_mm on the X-axis.
Each side stone needs its own mini-setting (small prongs or bezel).
""",

    "Cathedral": """\
Cathedral — high arching gallery supports raising the stone above the band.
The arch is formed by two sweeping metal ribs rising from the band shoulders to the
base of the setting, framing the stone like a gothic arch.
Build the arches as hull() curves from (band_outer_r at band_top_z) to (setting_base at stone_base_z).
""",

    "Bypass": """\
Bypass — two band sweeps pass each other, each carrying a stone.
No single shared head; each sweep terminates in its own mini stone setting.
""",

    "Cluster": """\
Cluster — multiple stones grouped together without a single dominant center stone.
Arrange stones in a dense pattern (floral, geometric) on a shared platform disk.
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_semantic_recipes(geo_ctx: dict) -> str:
    """
    Given a fully-built GeometryContext (from geometry_extractor), return a
    multi-line string containing the relevant construction recipes.

    This string is injected into the GEOMETRY CONTEXT prompt block, right
    after the STYLE section and before the SPATIAL CONSTRAINTS section.

    Parameters
    ----------
    geo_ctx : dict
        Output of geometry_extractor.build_geometry_context().

    Returns
    -------
    str
        Formatted recipe block ready for LLM prompt injection.
    """
    style   = geo_ctx.get("style", {})
    prongs  = geo_ctx.get("prongs", {})

    ring_style   = style.get("ring_style",   "Solitaire")
    setting_type = style.get("setting_type", "Prong")
    stone_cut    = geo_ctx.get("center_stone", {}).get("cut", "round").lower().capitalize()
    shank_style  = style.get("shank_style",  "Plain")
    prong_style  = style.get("prong_style",  "claw") if prongs else None

    lines = [
        "",
        "═══════════════════════════════════════════════════",
        "CONSTRUCTION RECIPES (OpenSCAD geometry prescriptions per semantic field)",
        "Each recipe below tells you EXACTLY how to build each component.",
        "Follow these instead of guessing from the style label alone.",
        "═══════════════════════════════════════════════════",
    ]

    # Ring style
    recipe = _RING_STYLE_RECIPES.get(ring_style)
    if recipe:
        lines += [f"\n▶ RING STYLE: {ring_style}", recipe.strip()]

    # Shank
    recipe = _SHANK_RECIPES.get(shank_style)
    if recipe:
        lines += [f"\n▶ SHANK STYLE: {shank_style}", recipe.strip()]

    # Setting type
    recipe = _SETTING_RECIPES.get(setting_type)
    if recipe:
        lines += [f"\n▶ SETTING TYPE: {setting_type}", recipe.strip()]

    # Prong style (only when prongs are present)
    if prong_style:
        recipe = _PRONG_RECIPES.get(prong_style.lower())
        if recipe:
            lines += [f"\n▶ PRONG STYLE: {prong_style}", recipe.strip()]

    # Stone cut
    recipe = _STONE_CUT_RECIPES.get(stone_cut.lower())
    if recipe:
        lines += [f"\n▶ CENTER STONE CUT: {stone_cut}", recipe.strip()]

    lines.append("\n═══════════════════════════════════════════════════\n")
    return "\n".join(lines)


def annotate_geo_ctx_with_recipes(geo_ctx: dict) -> dict:
    """
    Convenience: attach the recipe block string directly onto geo_ctx
    under the key '_recipes' so codegen_service can pick it up without
    changing its function signature.

    Usage in codegen_service._format_geometry_block():
        recipe_block = geo_ctx.get('_recipes', '')
        # insert recipe_block after the STYLE section
    """
    geo_ctx["_recipes"] = build_semantic_recipes(geo_ctx)
    return geo_ctx