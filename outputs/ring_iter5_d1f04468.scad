// Dimensional Parameters
inner_radius = 8.5;
outer_radius = 10.3;
band_width = 2.5;
stone_width = 7.357;
prong_radius = 0.441;
prong_height = 7.68;
prong_radial_distance = 3.943;
prong_count = 4;

// Visual Materials
metal_color = "#C0C0C0";
gem_color = "#E0FFFF";

// Derived Measurements
stone_radius = stone_width / 2;
band_thickness = outer_radius - inner_radius;
pavilion_height = prong_height * 0.65;
crown_height = prong_height * 0.25;
table_radius = stone_radius * 0.6;
prong_angles = [-90.1, -125.2, 126.2, 90.1];

complete_ring_assembly();

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([inner_radius, 0, 0])
    hull() {
        // Flat inner wall
        square([0.1, band_width], center = true);
        // Rounded outer wall (D-profile)
        translate([band_thickness, 0, 0])
        circle(r = band_width / 2, $fn = 24);
    }
}

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
        cylinder(r = table_radius, h = 0.2, $fn = 48);
    }
}

module claw_prong(angle) {
    rotate([0, 0, angle])
    translate([prong_radial_distance, 0, 0])
    color(metal_color)
    union() {
        // Prong shaft
        cylinder(r = prong_radius, h = prong_height, $fn = 16);
        // Round tip
        translate([0, 0, prong_height])
        sphere(r = prong_radius * 1.25, $fn = 20);
    }
}

module stone_setting_module() {
    union() {
        // Gallery Basket - structural base
        color(metal_color)
        cylinder(r1 = stone_radius * 1.1, r2 = stone_radius * 0.7, h = pavilion_height * 0.4, $fn = 48);
        
        // Center Stone
        stone_gem_module();
        
        // Prongs
        for (i = [0 : prong_count - 1]) {
            claw_prong(prong_angles[i]);
        }
    }
}

module complete_ring_assembly() {
    // Display orientation: upright
    rotate([90, 0, 0]) {
        // Main band
        ring_band();
        
        // Stone setting assembly
        // Positioned at the top of the band (Y = outer_radius)
        // Rotated so the setting tower points radially outward
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting_module();
    }
}