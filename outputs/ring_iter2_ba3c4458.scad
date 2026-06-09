// Dimensional Parameters
ring_inner_radius = 8.5;
ring_outer_radius = 10.3;
band_width = 5.447; // Dimension along the finger axis
stone_diameter = 7.357;
stone_total_height = 6.18; // Derived from stone_top_z (16.48) - stone_base_z (10.3)
prong_count = 4;
prong_radius = 1.5;
prong_height = 7.18;
prong_radial_distance = 3.679;
prong_base_z_offset = -0.5; // Relative to band top (9.8 - 10.3)

// Visual Materials
metal_color = "#E5E4E2"; // Platinum/White Gold
gem_color = "#E0FFFF"; // Diamond clear

// Derived Measurements
stone_radius = stone_diameter / 2;
wall_thickness = ring_outer_radius - ring_inner_radius;
pavilion_height = stone_total_height * 0.55;
crown_height = stone_total_height * 0.45;
table_radius = stone_radius * 0.56;
tip_overlap = prong_radius * 0.8;

complete_ring_assembly();

module diamond_gem() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = pavilion_height, $fn = 48);
        
        // Crown (frustum between girdle and table)
        translate([0, 0, pavilion_height])
        cylinder(r1 = stone_radius, r2 = table_radius, h = crown_height, $fn = 48);
        
        // Table (flat top)
        translate([0, 0, pavilion_height + crown_height])
        cylinder(r = table_radius, h = 0.3, $fn = 48);
    }
}

module claw_prong() {
    color(metal_color)
    hull() {
        // Base sphere
        translate([prong_radial_distance, 0, prong_base_z_offset])
        sphere(r = prong_radius, $fn = 24);
        
        // Shaft sphere (mid-point)
        translate([prong_radial_distance * 1.05, 0, stone_total_height * 0.75])
        sphere(r = prong_radius * 0.9, $fn = 24);
        
        // Tip sphere (curving inward over the girdle)
        translate([prong_radial_distance * 0.85, 0, stone_total_height + tip_overlap])
        sphere(r = prong_radius * 0.8, $fn = 24);
    }
}

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([ring_inner_radius, 0, 0])
    hull() {
        // Create a rounded rectangle profile for the band cross-section
        translate([0, band_width / 2, 0])
            circle(r = 0.5, $fn = 24);
        translate([0, -band_width / 2, 0])
            circle(r = 0.5, $fn = 24);
        translate([wall_thickness, band_width / 2, 0])
            circle(r = 0.5, $fn = 24);
        translate([wall_thickness, -band_width / 2, 0])
            circle(r = 0.5, $fn = 24);
    }
}

module solitaire_setting() {
    // Center Stone
    diamond_gem();
    
    // Prongs distributed symmetrically
    for (i = [0 : prong_count - 1]) {
        rotate([0, 0, i * (360 / prong_count)])
        claw_prong();
    }
}

module complete_ring_assembly() {
    // Rotate to upright display orientation
    rotate([90, 0, 0]) {
        // The main band
        ring_band();
        
        // Position the setting on top of the band
        // In the rotate_extrude space, the top of the ring is at Y = ring_outer_radius
        translate([0, ring_outer_radius, 0])
        rotate([-90, 0, 0])
        solitaire_setting();
    }
}