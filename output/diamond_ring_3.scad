$fn = 128;

// Ring Scale Parameters
outer_diameter = 22;
scale_factor = outer_diameter;
band_height = scale_factor * 0.25;
center_stone_diameter = scale_factor * 0.36;
prong_height = scale_factor * 0.12;
side_stone_diameter = scale_factor * 0.05;
millegrain_bead_diameter = scale_factor * 0.02;
inner_cutout_size = scale_factor * 0.03;

// Colors
metal_color = "Silver";
gem_color = "Diamond";
bead_color = "LightGray";

// Derived dimensions
ring_radius = outer_diameter / 2;
inner_radius = ring_radius - (band_height / 2);

module ring_body() {
    color(metal_color)
    difference() {
        // Main Torus-like band
        rotate_extrude()
        translate([inner_radius, 0, 0])
        circle(d = band_height);

        // Inner cutouts
        for (i = [0 : 11]) {
            rotate([0, 0, i * 30])
            translate([inner_radius, 0, 0])
            cube([inner_radius * 2, inner_cutout_size, inner_cutout_size], center = true);
        }
    }
}

module center_stone_assembly() {
    // Center Gem
    color(gem_color)
    translate([0, 0, band_height/2 + center_stone_diameter/4])
    sphere(d = center_stone_diameter);

    // Prongs
    color(metal_color)
    for (i = [0 : 3]) {
        rotate([0, 0, i * 90 + 45])
        translate([center_stone_diameter/2.2, 0, band_height/2])
        cylinder(h = prong_height, d = millegrain_bead_diameter * 2);
    }
}

module side_stones() {
    // Two parallel rows of side stones
    color(gem_color)
    for (row = [0 : 1]) {
        let (offset_y = row == 0 ? -side_stone_diameter/2 : side_stone_diameter/2) {
            for (i = [0 : 39]) {
                rotate([0, 0, i * 9])
                translate([ring_radius - band_height/4, offset_y, 0])
                sphere(d = side_stone_diameter);
            }
        }
    }
}

module millegrain_edging() {
    // Top and bottom beads
    color(bead_color)
    for (edge = [0 : 1]) {
        let (z_offset = edge == 0 ? band_height/2 : -band_height/2) {
            for (i = [0 : 71]) {
                rotate([0, 0, i * 5])
                translate([ring_radius, 0, z_offset])
                sphere(d = millegrain_bead_diameter);
            }
        }
    }
}

// Final Assembly
union() {
    ring_body();
    center_stone_assembly();
    side_stones();
    millegrain_edging();
}