// Dimensional Parameters
band_inner_radius = 8.5;
band_outer_radius = 10.3;
band_width = 2.5;
stone_diameter = 7.357;
stone_height = 6.18;
prong_count = 4;
prong_radius = 1.5;
prong_height = 7.18;
prong_radial_dist = 3.679;
prong_base_z = 9.8;

// Detail Density Parameters
band_resolution = 120;
stone_resolution = 48;
prong_resolution = 24;

// Visual Materials
metal_color = "#E5E4E2"; // Platinum/White Gold
gem_color = "#E0FFFF";   // Diamond

// Derived Measurements
band_thickness = band_outer_radius - band_inner_radius;
stone_radius = stone_diameter / 2;
pavilion_h = stone_height * 0.55;
crown_h = stone_height * 0.45;
table_r = stone_radius * 0.56;
tip_overlap = prong_radius * 0.8;
prong_base_relative_z = prong_base_z - band_outer_radius;

complete_ring_assembly();

module diamond_gem() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = pavilion_h, $fn = stone_resolution);
        
        // Crown (frustum)
        translate([0, 0, pavilion_h])
        cylinder(r1 = stone_radius, r2 = table_r, h = crown_h, $fn = stone_resolution);
        
        // Table (flat top)
        translate([0, 0, pavilion_h + crown_h])
        cylinder(r = table_r, h = 0.3, $fn = stone_resolution);
    }
}

module claw_prong() {
    color(metal_color)
    hull() {
        // Base sphere
        translate([prong_radial_dist, 0, prong_base_relative_z])
        sphere(r = prong_radius, $fn = prong_resolution);
        
        // Mid sphere (shaft)
        translate([prong_radial_dist * 1.05, 0, stone_height * 0.75])
        sphere(r = prong_radius * 0.9, $fn = prong_resolution);
        
        // Tip sphere (claw hook)
        translate([prong_radial_dist * 0.85, 0, stone_height + tip_overlap])
        sphere(r = prong_radius * 0.8, $fn = prong_resolution);
    }
}

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = band_resolution)
    translate([band_inner_radius, 0, 0])
    offset(r = 0.4)
    square([band_thickness - 0.8, band_width - 0.8], center = true);
}

module stone_setting() {
    // The diamond rests at the origin of this module
    diamond_gem();
    
    // Symmetrically placed prongs
    for (i = [0 : prong_count - 1]) {
        rotate([0, 0, i * (360 / prong_count)])
        claw_prong();
    }
}

module complete_ring_assembly() {
    // Rotate for display: ring sits upright
    rotate([90, 0, 0]) {
        ring_band();
        
        // Position the stone setting on top of the band
        // In the bore-along-Z space, the top of the band is at Y = band_outer_radius
        translate([0, band_outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting();
    }
}