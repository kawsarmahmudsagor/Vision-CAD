$fn = 128;

// ── Parameters ──────────────────────────────────────────────
largest_dimension    = 20.0;
ring_inner_diameter  = 18.0;
band_width           = largest_dimension * 0.2;
band_thickness       = 2.0;
stone_diameter       = largest_dimension * 0.3;
stone_height         = stone_diameter * 0.6;
prong_height         = largest_dimension * 0.1;
prong_diameter       = 0.8;
pave_stone_diameter  = largest_dimension * 0.05;
milgrain_bead_diameter = largest_dimension * 0.025;
pave_stone_count     = 25;
milgrain_bead_count  = 60;

band_color           = "Silver";
stone_color          = "#E8F4FC";
prong_color          = "Silver";

ring_radius          = ring_inner_diameter / 2;

// ── 1. PRIMARY BODY — the band ───────────────────────────────
color(band_color)
rotate_extrude()
    translate([ring_radius + band_thickness / 2, 0, 0])
    square([band_thickness, band_width], center = true);

// ── 2. SECONDARY — central stone ─────────────────────────────
color(stone_color)
translate([0, 0, band_width / 2 + prong_height * 0.5])
scale([1, 1, stone_height / stone_diameter])
sphere(d = stone_diameter);

// ── 3. REPEATING — prongs ───────────────────────────────────
color(prong_color)
for (i = [0 : 3]) {
    rotate([0, 0, i * 90])
    translate([stone_diameter * 0.4, 0, band_width / 2])
    cylinder(h = prong_height, d1 = prong_diameter * 1.5, d2 = prong_diameter);
}

// ── 3. REPEATING — pavé stones ───────────────────────────────
color(stone_color)
for (row = [-1, 1]) {
    for (i = [0 : pave_stone_count - 1]) {
        angle = i * 360 / pave_stone_count;
        rotate([0, 0, angle])
        translate([ring_radius + band_thickness / 2, 0, row * (band_width * 0.2)])
        sphere(d = pave_stone_diameter);
    }
}

// ── 3. REPEATING — milgrain edging ──────────────────────────
color(band_color)
for (row = [-1, 1]) {
    // Top and bottom edges of the pavé area
    for (edge = [-1, 1]) {
        z_offset = (row * 0.3 + edge * 0.2) * band_width;
        for (i = [0 : milgrain_bead_count - 1]) {
            angle = i * 360 / milgrain_bead_count;
            rotate([0, 0, angle])
            translate([ring_radius + band_thickness / 2, 0, z_offset])
            sphere(d = milgrain_bead_diameter);
        }
    }
}