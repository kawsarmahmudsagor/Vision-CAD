// Dimensional Parameters
ring_inner_diameter = 16.5;
band_thickness = 2.0;
band_height = 3.0;
decorative_arc_angle = 180;
gem_major_axis = 1.8;
gem_minor_axis = 1.2;
prong_thickness = 0.6;
gem_row_count = 4;
decorative_arc_height = band_height * 1.5;

// Visual Materials
gold_color = "#FFD700";
gem_color = "#C0C0C0";

// Derived Measurements
inner_radius = ring_inner_diameter / 2;
outer_radius = inner_radius + band_thickness;

complete_ring_assembly();

module gem_ellipsoid(major, minor) {
    color(gem_color)
    scale([1, minor/major, 1])
    sphere(r = major, $fn = 32);
}

module prong_cylinder(height) {
    color(gold_color)
    cylinder(r = prong_thickness / 2, h = height, $fn = 12);
}

module band_profile() {
    hull() {
        circle(r = 0.5, $fn = 24);
        translate([band_thickness, 0]) circle(r = 0.5, $fn = 24);
        square([band_thickness, band_height], center = true);
    }
}

module ring_band() {
    color(gold_color)
    rotate_extrude($fn = 120)
    translate([inner_radius + 0.5, 0, 0])
    band_profile();
}

module decorative_arc() {
    // Row configurations: [gem_count, radial_offset, vertical_offset]
    // Bottom row is widest (most gems), top row is narrowest
    row_configs = [
        [16, 0.2, -band_height * 0.4], // Row 0 (Bottom)
        [14, 0.5, -band_height * 0.1], // Row 1
        [12, 0.8,  band_height * 0.2], // Row 2
        [10, 1.1,  band_height * 0.5]  // Row 3 (Top)
    ];

    for (row_idx = [0 : gem_row_count - 1]) {
        let(
            config = row_configs[row_idx],
            gem_count = config[0],
            radial_off = config[1],
            vert_off = config[2]
        ) {
            for (i = [0 : gem_count - 1]) {
                angle = (decorative_arc_angle / 2) - (i * (decorative_arc_angle / (gem_count - 1)));
                
                rotate([0, 0, angle])
                translate([outer_radius + radial_off, 0, vert_off]) {
                    // The Gem
                    gem_ellipsoid(gem_major_axis, gem_minor_axis);
                    
                    // Prongs (4 per gem)
                    for (p = [0 : 3]) {
                        rotate([0, 0, p * 90])
                        translate([gem_major_axis * 0.8, 0, 0])
                        rotate([0, 90, 0])
                        prong_cylinder(decorative_arc_height * 0.4);
                    }
                }
            }
        }
    }
}

module complete_ring_assembly() {
    // Orient for display
    rotate([90, 0, 0]) {
        ring_band();
        decorative_arc();
    }
}