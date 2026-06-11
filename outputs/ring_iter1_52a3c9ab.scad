// Dimensional Parameters
ring_inner_radius = 8.5;
ring_outer_radius = 10.3;
ring_thickness = 1.8;
ring_width = 2.5;

stone_width = 7.357;
stone_height = 6.18;
setting_total_height = 7.68;

prong_count = 4;
prong_radius = 0.441;
prong_radial_distance = 3.943;

// Visual Materials
metal_color = "#C0C0C0";
gem_color = "#F0F8FF";

// Derived Measurements
stone_radius = stone_width / 2;
pavilion_height = stone_height * 0.55;
crown_height = stone_height * 0.45 - 0.3;
table_radius = stone_radius * 0.56;
basket_height = stone_height * 0.40;
prong_angles = [0, 90, 180, 270];

complete_ring_assembly();

module stone_gem_module() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = pavilion_height, $fn = 48);
        
        // Crown (frustum)
        translate([0, 0, pavilion_height])
        cylinder(r1 = stone_radius, r2 = table_radius, h = crown_height, $fn = 48);
        
        // Table (flat top)
        translate([0, 0, pavilion_height + crown_height])
        cylinder(r = table_radius, h = 0.3, $fn = 48);
    }
}

module claw_prong(angle) {
    color(metal_color)
    rotate([0, 0, angle])
    translate([prong_radial_distance, 0, 0])
    union() {
        // Prong shaft
        cylinder(r = prong_radius, h = setting_total_height, $fn = 16);
        
        // Round tip
        translate([0, 0, setting_total_height])
        sphere(r = prong_radius * 1.25, $fn = 20);
    }
}

module stone_setting_module() {
    // 1. Gallery Basket
    color(metal_color)
    difference() {
        cylinder(r1 = stone_radius * 1.25, r2 = stone_radius * 0.85, h = basket_height, $fn = 48);
        translate([0, 0, -0.1])
        cylinder(r1 = stone_radius * 0.85, r2 = stone_radius * 0.55, h = basket_height + 0.2, $fn = 48);
    }

    // 2. Center Stone
    translate([0, 0, 0])
    stone_gem_module();

    // 3. Prongs
    for (angle = prong_angles) {
        claw_prong(angle);
    }
}

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([ring_inner_radius, 0, 0])
    hull() {
        // Inner flat wall
        square([0.1, ring_width], center = true);
        // Outer rounded profile
        translate([ring_thickness, 0, 0])
        circle(r = ring_width / 2, $fn = 24);
    }
}

module complete_ring_assembly() {
    rotate([90, 0, 0]) {
        ring_band();
        
        // Position setting at the top of the band
        translate([0, ring_outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting_module();
    }
}