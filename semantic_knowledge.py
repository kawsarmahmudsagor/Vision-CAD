"""
semantic_knowledge.py
──────────────────────────────────────────────────────────────────────────────
Visual recognition knowledge base for ring semantic extraction.

PURPOSE
-------
This file contains ONLY visual/semantic knowledge — how to *identify* ring
components from a photograph.  It does NOT contain OpenSCAD construction
instructions; those live in semantic_recipe.py (the CAD layer).

ARCHITECTURE
------------
Image
  ↓
VLM  +  semantic_knowledge.py   ← (this file)
  ↓
Semantic Classification
  ↓
cad_recipes.py / semantic_recipe.py
  ↓
OpenSCAD Generator

USAGE
-----
    from semantic_knowledge import (
        build_prong_semantics_block,
        build_stone_cut_semantics_block,
        build_setting_semantics_block,
        build_shank_semantics_block,
        build_ring_style_semantics_block,
        build_full_semantics_block,
    )

    # Inject into the VLM semantic-extraction prompt:
    prompt = f\"\"\"
    You are a jewelry expert. Analyse the ring image.

    {build_full_semantics_block()}

    Return a JSON object with: stone_cut, prong_style, setting_type,
    shank_style, ring_style, confidence.
    \"\"\"
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Prong style visual knowledge
# ─────────────────────────────────────────────────────────────────────────────

PRONG_SEMANTICS: dict[str, dict] = {

    "claw": {
        "visual_signature": (
            "Elegant tapered prong terminating in a sharp inward-curving hook. "
            "The tip visibly crosses over the stone girdle and resembles a bird claw."
        ),
        "top_view": (
            "Thin metal profile. Minimal visible metal around the stone. "
            "Prongs appear narrow at the contact point."
        ),
        "side_view": (
            "Prong rises vertically then bends inward near the tip."
        ),
        "distinguishing_features": [
            "Sharp hooked tip",
            "Strong taper from base to tip",
            "Minimal metal coverage over the stone",
            "Maximum stone visibility — light enters freely",
        ],
        "common_confusions": {
            "round_tip": "Ends with a polished ball, not a hook. No inward curve.",
            "flat": "Rectangular profile with a wide contact area — no taper.",
        },
        "style_associations": [
            "Luxury solitaire rings",
            "Oval, pear, and marquise center stones",
            "Modern high-end engagement rings",
        ],
        "image_cues": [
            "thin pointed metal tips crossing over stone edge",
            "hook-like appearance at prong tips",
            "each prong visibly bends inward at the top",
            "minimal metal obscuring stone table",
        ],
    },

    "round_tip": {
        "visual_signature": (
            "Straight or gently tapered shaft ending in a distinct polished ball. "
            "The ball tip is visibly wider than the shaft."
        ),
        "top_view": (
            "Small circular dots visible at each prong position. "
            "The ball cap stands out against the stone."
        ),
        "side_view": (
            "Shaft rises straight; a spherical bead sits on top with no inward curve."
        ),
        "distinguishing_features": [
            "Ball-shaped tip — clearly rounder than the shaft",
            "No hooked or inward-curving tip",
            "Classic 'beaded' or 'ball-end' appearance",
        ],
        "common_confusions": {
            "claw": "Claw tip curves inward; round_tip does not. No hook visible.",
        },
        "style_associations": [
            "Traditional solitaire rings",
            "Classic and vintage-inspired designs",
            "Yellow and rose gold settings",
        ],
        "image_cues": [
            "small polished ball visible at tip of each prong",
            "prong tip wider than the shaft below it",
            "no inward curve at the prong tip",
            "beaded or pearl-like appearance at contact point",
        ],
    },

    "flat": {
        "visual_signature": (
            "A wide rectangular metal tab holding the stone with a broad flat face. "
            "The contact surface is a rectangle, not a rounded wire."
        ),
        "top_view": (
            "Wide flat band of metal visible at each corner. "
            "Tab width noticeably greater than its thickness."
        ),
        "side_view": (
            "Rectangular cross-section visible. No taper, no curve."
        ),
        "distinguishing_features": [
            "Flat rectangular face against the stone",
            "Wide, tab-like appearance",
            "No tapering, no ball, no hook",
        ],
        "common_confusions": {
            "claw": "Claw is a thin wire with a hook; flat is a wide plate.",
        },
        "style_associations": [
            "Vintage and art deco styles",
            "Emerald cut stones",
            "Princess cut stones",
        ],
        "image_cues": [
            "flat rectangular metal visible at stone corners",
            "tab-like prong covering corner of stone",
            "wide metal surface at contact point",
        ],
    },

    "double_claw": {
        "visual_signature": (
            "Each corner appears secured by two very thin claws rather than one larger prong. "
            "Viewed from above, the tips form a V-shape. "
            "The two branches share a single lower shaft — it is NOT two separate prongs."
        ),
        "top_view": (
            "Forked or Y-shaped appearance at each prong position. "
            "Two contact points visible per corner."
        ),
        "side_view": (
            "Single shaft rises upward and splits into two tips near the stone girdle."
        ),
        "distinguishing_features": [
            "Split occurs near the tip — base is shared",
            "Twin claw appearance per corner",
            "Forked, Y-shaped profile",
            "Vintage or custom aesthetic",
        ],
        "common_confusions": {
            "claw": "Single claw has one tip per prong. Double claw has two tips from one shaft.",
        },
        "style_associations": [
            "Vintage and antique-inspired rings",
            "Pear, oval, and marquise cuts",
            "High-end custom settings",
        ],
        "image_cues": [
            "V-shaped or forked tip visible at each prong",
            "two thin claw tips meeting at each corner",
            "Y-shaped metal at the stone contact point",
            "double-pointed appearance per prong",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Stone cut visual knowledge
# ─────────────────────────────────────────────────────────────────────────────

STONE_CUT_SEMANTICS: dict[str, dict] = {

    "round": {
        "visual_signature": (
            "Perfect circular outline with complete rotational symmetry. "
            "Facets form a star and kite pattern radiating from the centre."
        ),
        "top_view": "Circular perimeter. No corners, no elongated axis.",
        "side_view": "Conical pavilion, flat table, tapered crown.",
        "distinguishing_features": [
            "Perfectly circular silhouette",
            "Highest symmetry of all cuts",
            "No pointed corners or elongated axis",
        ],
        "common_confusions": {
            "oval": "Oval has a longer major axis; round is perfectly symmetric.",
        },
        "style_associations": [
            "Most common engagement ring center stone",
            "Solitaire and halo settings",
        ],
        "image_cues": [
            "perfectly circular stone outline",
            "radiating facet pattern from centre",
            "no corners or elongated axis visible",
        ],
    },

    "cushion": {
        "visual_signature": (
            "Square or slightly rectangular gemstone with soft rounded corners. "
            "Resembles a pillow or cushion."
        ),
        "top_view": "Rounded corners. Soft curved edges between sides.",
        "side_view": "Similar depth profile to a round brilliant.",
        "distinguishing_features": [
            "Pillow shape with rounded corners",
            "Softer, gentler geometry than princess cut",
        ],
        "common_confusions": {
            "princess": "Princess has sharp 90° corners; cushion has soft rounded corners.",
            "radiant": "Radiant has clipped (chamfered) corners, not rounded ones.",
        },
        "style_associations": [
            "Vintage and romantic designs",
            "Halo settings",
        ],
        "image_cues": [
            "square stone with rounded corners",
            "pillow-like soft corner geometry",
            "gentle curved transitions at each corner",
        ],
    },

    "princess": {
        "visual_signature": (
            "Square brilliant cut with perfectly sharp geometric corners."
        ),
        "top_view": "Perfect square with straight edges and sharp 90° corners.",
        "side_view": "Deep pavilion with angular profile.",
        "distinguishing_features": [
            "Sharp corners — no rounding, no clipping",
            "Square outline",
            "Modern geometric appearance",
        ],
        "common_confusions": {
            "cushion": "Cushion has rounded corners; princess has sharp corners.",
            "radiant": "Radiant has clipped corners (45° chamfer); princess has full 90° corners.",
        },
        "style_associations": [
            "Contemporary engagement rings",
            "Cathedral and solitaire settings",
        ],
        "image_cues": [
            "square stone with perfectly sharp corners",
            "no rounding or clipping at corners",
            "crisp geometric outline",
        ],
    },

    "oval": {
        "visual_signature": (
            "Elliptical outline — elongated version of the round brilliant. "
            "Clear long axis and short axis."
        ),
        "top_view": "Ellipse with a major axis clearly longer than the minor axis.",
        "side_view": "Similar depth to round brilliant.",
        "distinguishing_features": [
            "Elongated elliptical silhouette",
            "Brilliant facet pattern like a round",
            "No corners",
        ],
        "common_confusions": {
            "round": "Round is perfectly circular; oval has a distinct long axis.",
            "marquise": "Marquise has two pointed tips; oval has fully rounded ends.",
        },
        "style_associations": [
            "Finger-elongating settings",
            "East-west orientation trends",
        ],
        "image_cues": [
            "elliptical stone outline",
            "longer in one direction than the other",
            "both ends fully rounded — no points",
        ],
    },

    "pear": {
        "visual_signature": (
            "Teardrop shape — pointed at one end, fully rounded at the other."
        ),
        "top_view": "One pointed tip and one rounded lobe.",
        "side_view": "Similar to round brilliant depth.",
        "distinguishing_features": [
            "Single pointed tip (vs marquise which has two)",
            "Asymmetric along the long axis",
        ],
        "common_confusions": {
            "marquise": "Marquise has two pointed tips; pear has only one.",
            "oval": "Oval has two rounded ends; pear has one point.",
        },
        "style_associations": [
            "East-facing and north-south orientations",
            "Romantic and vintage styles",
        ],
        "image_cues": [
            "teardrop-shaped stone",
            "one pointed end and one round end",
            "asymmetric along the length",
        ],
    },

    "marquise": {
        "visual_signature": (
            "Eye-shaped (navette) stone with two pointed tips at opposite ends "
            "and maximum width in the middle."
        ),
        "top_view": "Two points at each end of the long axis, full curve at the waist.",
        "side_view": "Similar depth to round brilliant.",
        "distinguishing_features": [
            "Two pointed tips — distinguishes it from pear (one tip)",
            "Elongated eye or football shape",
        ],
        "common_confusions": {
            "pear": "Pear has one pointed end and one round end; marquise has two points.",
            "oval": "Oval has no points; marquise has two sharp tips.",
        },
        "style_associations": [
            "Finger-elongating styles",
            "Vintage and art deco rings",
        ],
        "image_cues": [
            "pointed at both ends",
            "eye or football silhouette",
            "two symmetric pointed tips on the long axis",
        ],
    },

    "emerald": {
        "visual_signature": (
            "Rectangular stone with visibly clipped corners (45° chamfers) "
            "and a large, open flat table. Hall-of-mirrors reflection pattern."
        ),
        "top_view": "Long rectangle with four cut corners forming an octagon.",
        "side_view": "Shallower crown than brilliant cuts. Large flat table.",
        "distinguishing_features": [
            "Large open table — reflections appear as broad flashes",
            "Step-cut facets — parallel lines rather than radiating sparkle",
            "Clipped (not sharp, not rounded) corners",
        ],
        "common_confusions": {
            "radiant": "Radiant has crushed-ice sparkle; emerald has large mirror-like flashes.",
            "princess": "Princess has sharp corners; emerald has clipped corners.",
        },
        "style_associations": [
            "Art deco and architectural designs",
            "Three-stone and east-west settings",
        ],
        "image_cues": [
            "large broad reflections visible inside stone",
            "rectangular outline with clipped corners",
            "step-cut parallel facets visible on crown",
            "hall-of-mirrors appearance",
        ],
    },

    "radiant": {
        "visual_signature": (
            "Rectangular or square stone with clipped corners (like emerald cut) "
            "but with brilliant-style faceting — high sparkle density, crushed-ice appearance."
        ),
        "top_view": "Rectangle with clipped corners. Many small fragmented reflections.",
        "side_view": "Brilliant-cut depth profile.",
        "distinguishing_features": [
            "Clipped corners like emerald, but much more sparkle",
            "Crushed-ice or shattered-light appearance",
            "Many small reflections (not the large flashes of emerald)",
        ],
        "common_confusions": {
            "emerald": "Emerald shows large broad flashes; radiant shows many tiny sparkles.",
            "cushion": "Cushion has rounded corners; radiant has clipped corners.",
        },
        "style_associations": [
            "Modern luxury engagement rings",
            "Halo and hidden halo designs",
        ],
        "image_cues": [
            "rectangular stone with clipped corners",
            "intense sparkle and many small reflections",
            "crushed-ice look inside the stone",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Setting type visual knowledge
# ─────────────────────────────────────────────────────────────────────────────

SETTING_SEMANTICS: dict[str, dict] = {

    "Prong": {
        "visual_signature": (
            "Stone held by individual metal wires (prongs). "
            "Open space visible beneath and around the stone — light enters freely."
        ),
        "top_view": "Metal prongs visible at stone corners or equidistant around the girdle.",
        "side_view": "Open basket or tulip frame below the stone. Air visible around girdle.",
        "distinguishing_features": [
            "Individual wire-like metal posts",
            "Open gallery — no solid metal wall surrounding stone",
            "Maximum light entry",
        ],
        "common_confusions": {
            "Bezel": "Bezel is a continuous solid metal wall. Prong has separate wires.",
        },
        "image_cues": [
            "individual metal posts holding stone",
            "open space visible beneath the stone",
            "light entering from sides of stone",
            "discrete prong wires at 2, 4, 6, 8 o'clock positions",
        ],
    },

    "Bezel": {
        "visual_signature": (
            "Stone completely encircled by a continuous metal rim or wall. "
            "No prongs visible."
        ),
        "top_view": "Solid metal ring surrounds the entire stone perimeter.",
        "side_view": "Continuous metal wall rising around the stone from the band.",
        "distinguishing_features": [
            "Solid continuous metal border — no gaps",
            "No individual prongs",
            "Stone appears to sit inside the metal wall",
        ],
        "common_confusions": {
            "Prong": "Prong has individual wires; bezel has a continuous wall.",
        },
        "image_cues": [
            "continuous metal rim encircling the stone",
            "no individual prongs visible",
            "metal wall surrounds entire stone perimeter",
        ],
    },

    "Tension": {
        "visual_signature": (
            "Stone appears to float between two opposing open band ends. "
            "No prongs, no bezel — only the compressed band ends grip the stone."
        ),
        "top_view": "Band has a gap; stone bridges the gap with no visible holder.",
        "side_view": "Stone floats with no visible support above or below.",
        "distinguishing_features": [
            "No prongs, no bezel visible",
            "Band is open (C-shape) with the stone bridging the gap",
            "Stone appears suspended",
        ],
        "image_cues": [
            "stone appearing to float or levitate",
            "open band with gap where stone sits",
            "no metal visible above or around the stone",
        ],
    },

    "Channel": {
        "visual_signature": (
            "A row of small stones set between two parallel metal rails along the shoulder."
        ),
        "top_view": "Two metal rails with evenly spaced small stones between them.",
        "side_view": "Rail lips grip the stone girdles. Stones flush with rail tops.",
        "distinguishing_features": [
            "Always a row of stones (not a single stone)",
            "Two parallel metal rails visible",
            "Stones aligned in a channel",
        ],
        "image_cues": [
            "row of small stones between two metal rails",
            "channel of stones running along band shoulder",
            "evenly spaced stones in a groove",
        ],
    },

    "Pave": {
        "visual_signature": (
            "Surface of the band densely covered with tiny stones. "
            "Metal nearly invisible — only small bead-like prongs between stones."
        ),
        "top_view": "Surface appears to be entirely made of tiny sparkling stones.",
        "side_view": "Band surface textured with closely packed tiny stones.",
        "distinguishing_features": [
            "High density of very small stones",
            "Very little metal visible on covered surfaces",
            "All-over sparkle texture",
        ],
        "image_cues": [
            "dense small stones covering band surface",
            "almost no visible metal between stones",
            "glittering texture across the band",
        ],
    },

    "Flush": {
        "visual_signature": (
            "Stone is set completely level with the metal surface. "
            "No stone protrudes above the metal — table and metal surface are co-planar."
        ),
        "top_view": "Stone appears inset into the metal. Only stone table visible, no setting walls.",
        "side_view": "Stone top is flush with the metal surface.",
        "distinguishing_features": [
            "No prongs, no bezel wall rising above metal",
            "Stone sunk into the surface",
            "Very sleek, minimal appearance",
        ],
        "image_cues": [
            "stone sitting level with the metal surface",
            "no raised prongs or bezel",
            "stone appears inset or sunk into band",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Shank style visual knowledge
# ─────────────────────────────────────────────────────────────────────────────

SHANK_SEMANTICS: dict[str, dict] = {

    "Plain": {
        "visual_signature": "Uniform, smooth, undecorated circular band.",
        "top_view": "Smooth ring with no stones or texture on the band.",
        "side_view": "Uniform width and thickness around the full circumference.",
        "distinguishing_features": [
            "No stones on the band",
            "No split, no taper, no bypass",
            "Simple, clean metal surface",
        ],
        "image_cues": [
            "smooth undecorated band",
            "no stones visible on ring shank",
            "uniform band width all around",
        ],
    },

    "Pave": {
        "visual_signature": (
            "Band surface covered with tiny stones (see Pave setting). "
            "The band itself is the decorated element."
        ),
        "image_cues": [
            "small stones covering the band surface",
            "sparkling texture on the shank",
        ],
    },

    "Split-Shank": {
        "visual_signature": (
            "The band physically divides into two separate rails as it approaches the center stone. "
            "A visible gap between the rails near the head."
        ),
        "top_view": "Y-shaped transition from single band to two rails. Negative space between rails.",
        "side_view": "Two shoulder rails visible supporting the stone setting.",
        "distinguishing_features": [
            "Physical gap between two rail shoulders near the head",
            "Dual rail structure near setting",
            "Wider visual footprint at the head",
        ],
        "common_confusions": {
            "Cathedral": "Cathedral has a single rising shoulder arch; split-shank has an actual gap.",
        },
        "image_cues": [
            "band splits into two rails near center stone",
            "visible gap between the two shoulder rails",
            "Y-shaped band transition near the head",
        ],
    },

    "Tapered": {
        "visual_signature": (
            "Band is visibly wider at the shoulder (near the stone) "
            "and narrows toward the back of the finger."
        ),
        "image_cues": [
            "band width decreases from front to back",
            "wider near the stone setting, narrower at the back",
        ],
    },

    "Bypass": {
        "visual_signature": (
            "Two band ends sweep past each other like a spiral, without meeting. "
            "Each end carries a stone or decorative terminus."
        ),
        "top_view": "Two band ends crossing or passing each other near the top.",
        "side_view": "Spiral or overlapping band ends at different Z heights.",
        "image_cues": [
            "two band ends passing each other",
            "spiral or crossover band design",
            "no single shared head — two separate ends",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Ring style visual knowledge
# ─────────────────────────────────────────────────────────────────────────────

RING_STYLE_SEMANTICS: dict[str, dict] = {

    "Solitaire": {
        "visual_signature": (
            "Single center stone on a plain or near-plain band. "
            "No side stones, no additional accent stones."
        ),
        "top_view": "One stone dominates. No surrounding or flanking stones.",
        "side_view": "Head with one stone only. Simple band.",
        "distinguishing_features": [
            "Only one stone visible",
            "No halo, no side stones, no cluster",
        ],
        "image_cues": [
            "single center stone",
            "no surrounding accent stones",
            "clean simple band",
        ],
    },

    "Halo": {
        "visual_signature": (
            "Center stone completely surrounded by a ring of smaller accent stones. "
            "The halo stones form a continuous circle or shape around the center stone."
        ),
        "top_view": (
            "Concentric structure:\n"
            "  ○ ○ ○ ○ ○   ← halo stones\n"
            "      ●       ← dominant center stone\n"
            "The center stone is clearly dominant and larger than the halo stones."
        ),
        "side_view": "Halo platform at or slightly below the center stone table height.",
        "distinguishing_features": [
            "One clearly dominant center stone",
            "Continuous perimeter ring of smaller accent stones",
            "The center stone appears visually larger due to the halo",
        ],
        "common_confusions": {
            "Cluster": "Cluster has multiple primary stones of similar size; halo has ONE dominant center stone.",
        },
        "image_cues": [
            "ring of small stones surrounding the center stone",
            "continuous border of accent stones around center",
            "center stone visibly larger than surrounding stones",
            "halo stones at the same level as center stone",
        ],
    },

    "Three-Stone": {
        "visual_signature": (
            "One center stone flanked by exactly two accent stones on each side. "
            "All three stones are visible in the top view."
        ),
        "top_view": "Left stone — center stone — right stone, in a horizontal or arced arrangement.",
        "distinguishing_features": [
            "Exactly three stones visible from above",
            "Side stones smaller than the center stone (typically 60–70% width)",
            "Symmetric left-right arrangement",
        ],
        "image_cues": [
            "three stones visible from above",
            "two smaller flanking stones beside the center",
            "symmetric left and right accent stones",
        ],
    },

    "Cathedral": {
        "visual_signature": (
            "Center stone elevated above the band by sweeping arches rising from the shoulders. "
            "The band visually flows up into the stone setting like a gothic arch."
        ),
        "top_view": "Shoulders converge toward the center stone.",
        "side_view": (
            "Distinct gothic-arch silhouette. Visible open space beneath the setting. "
            "The metal shoulder rises in a curve to meet the base of the head."
        ),
        "distinguishing_features": [
            "Elevated center stone — clearly sits above the band level",
            "Arching shoulders — the band rises toward the stone",
            "High gallery with visible air beneath the stone",
        ],
        "common_confusions": {
            "Solitaire": "Plain solitaire head sits independently. Cathedral has arching shoulders.",
            "Split-Shank": "Split-shank has a gap between rails; cathedral has a single arch.",
        },
        "image_cues": [
            "stone elevated above the band",
            "arching metal shoulders rising toward the stone",
            "visible open space beneath the stone setting",
            "gothic arch profile on the side view",
        ],
    },

    "Bypass": {
        "visual_signature": (
            "Two band sweeps pass each other, each carrying a stone. "
            "No shared center head — two separate termini."
        ),
        "image_cues": [
            "two band ends crossing or bypassing each other",
            "each band end has its own stone",
            "spiral or overlapping band design",
        ],
    },

    "Cluster": {
        "visual_signature": (
            "Multiple stones grouped together without a single clearly dominant center stone. "
            "Stones arranged in a dense geometric or floral pattern."
        ),
        "top_view": "Dense grouping of multiple stones of similar or mixed sizes.",
        "distinguishing_features": [
            "No single dominant center stone",
            "Multiple stones of similar visual weight",
            "Geometric, floral, or organic cluster arrangement",
        ],
        "common_confusions": {
            "Halo": "Halo has ONE dominant center stone; cluster has multiple equal stones.",
        },
        "image_cues": [
            "multiple stones of similar size grouped together",
            "no single clearly dominant stone",
            "dense stone arrangement forming a pattern",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Prompt block builders
# ─────────────────────────────────────────────────────────────────────────────

def _format_entry(name: str, data: dict) -> str:
    """Format a single semantic entry for prompt injection."""
    lines = [f"  [{name}]"]
    lines.append(f"    Visual: {data['visual_signature']}")
    if "image_cues" in data:
        cues = " | ".join(data["image_cues"])
        lines.append(f"    Image cues: {cues}")
    if "common_confusions" in data:
        for other, note in data["common_confusions"].items():
            lines.append(f"    ≠ {other}: {note}")
    return "\n".join(lines)


def build_prong_semantics_block() -> str:
    """Return a formatted block describing all prong styles for VLM prompting."""
    lines = ["PRONG STYLES — identify by visual appearance:"]
    for name, data in PRONG_SEMANTICS.items():
        lines.append(_format_entry(name, data))
    return "\n".join(lines)


def build_stone_cut_semantics_block() -> str:
    """Return a formatted block describing all stone cuts for VLM prompting."""
    lines = ["STONE CUTS — identify by silhouette and facet pattern:"]
    for name, data in STONE_CUT_SEMANTICS.items():
        lines.append(_format_entry(name, data))
    return "\n".join(lines)


def build_setting_semantics_block() -> str:
    """Return a formatted block describing all setting types for VLM prompting."""
    lines = ["SETTING TYPES — identify by how the stone is held:"]
    for name, data in SETTING_SEMANTICS.items():
        lines.append(_format_entry(name, data))
    return "\n".join(lines)


def build_shank_semantics_block() -> str:
    """Return a formatted block describing all shank styles for VLM prompting."""
    lines = ["SHANK STYLES — identify by band geometry:"]
    for name, data in SHANK_SEMANTICS.items():
        lines.append(_format_entry(name, data))
    return "\n".join(lines)


def build_ring_style_semantics_block() -> str:
    """Return a formatted block describing all ring styles for VLM prompting."""
    lines = ["RING STYLES — identify by overall stone composition:"]
    for name, data in RING_STYLE_SEMANTICS.items():
        lines.append(_format_entry(name, data))
    return "\n".join(lines)


def build_full_semantics_block() -> str:
    """
    Return the complete visual knowledge block for injection into the
    VLM semantic extraction prompt.

    This covers all five classification axes:
        stone_cut | prong_style | setting_type | shank_style | ring_style
    """
    sections = [
        "═══════════════════════════════════════════════════",
        "VISUAL IDENTIFICATION GUIDE — use these descriptions to classify the ring image.",
        "Match what you SEE in the photograph to the image_cues and visual descriptions below.",
        "═══════════════════════════════════════════════════",
        "",
        build_ring_style_semantics_block(),
        "",
        build_stone_cut_semantics_block(),
        "",
        build_setting_semantics_block(),
        "",
        build_prong_semantics_block(),
        "",
        build_shank_semantics_block(),
        "",
        "═══════════════════════════════════════════════════",
    ]
    return "\n".join(sections)