// Solitaire Diamond Ring with D-Profile Band

// Dimensional Parameters
inner_radius = 8.5;
band_thickness = 3.931;
band_width = 2.5;
stone_width = 7.357;
prong_radius = 0.441;
prong_height = 7.68;
prong_radial_dist = 3.943;

// Detail Density Parameters
prong_count = 4;
stone_fn = 48;
band_fn = 120;
prong_fn = 24;

// Visual Materials
metal_color = "#C0C0C0"; // Platinum/White Gold
gem_color = "#E0FFFF";   // Diamond

// Derived Measurements
outer_radius = inner_radius + band_thickness;
stone_radius = stone_width / 2;
stone_height = 5.5; // Derived realistic height for brilliant cut
pavilion_height = stone_height * 0.55;
crown_height = stone_height * 0.45;
table_radius = stone_radius * 0.6;
basket_height = pavilion_height * 0.7;
prong_angles = [-90.1, -125.2, 126.2, 90.1];

// Top-level Assembly
complete_ring_assembly();

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = band_fn)
    translate([inner_radius, 0, 0])
    hull() {
        // Flat inner wall
        square([0.1, band_width], center = true);
        // Rounded outer wall (D-profile)
        translate([band_thickness, 0, 0])
        circle(r = band_width / 2, $fn = 32);
    }
}

module stone_gem_module() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = pavilion_height, $fn = stone_fn);
        // Crown (frustum)
        translate([0, 0, pavilion_height])
        cylinder(r1 = stone_radius, r2 = table_radius, h = crown_height, $fn = stone_fn);
        // Table (flat top)
        translate([0, 0, pavilion_height + crown_height])
        cylinder(r = table_radius, h = 0.2, $fn = stone_fn);
    }
}

module prong_claws() {
    color(metal_color)
    for (a = prong_angles) {
        rotate([0, 0, a])
        translate([prong_radial_dist, 0, 0])
        union() {
            // Prong shaft
            cylinder(r = prong_radius, h = prong_height, $fn = prong_fn);
            // Round tip
            translate([0, 0, prong_height])
            sphere(r = prong_radius * 1.25, $fn = prong_fn);
        }
    }
}

module gallery_basket() {
    color(metal_color)
    difference() {
        // Outer structural shell
        cylinder(r1 = band_width, r2 = stone_radius, h = basket_height, $fn = stone_fn);
        // Inner hollow for stone pavilion
        translate([0, 0, -0.1])
        cylinder(r = stone_radius * 0.7, h = basket_height + 0.2, $fn = stone_fn);
    }
}

module stone_setting_module() {
    // 1. Gallery Basket (Base)
    gallery_basket();
    
    // 2. Center Stone (Pavilion tip at local Z=0)
    stone_gem_module();
    
    // 3. Prongs (Base at local Z=0)
    prong_claws();
}

module complete_ring_assembly() {
    // Display orientation: Ring stands upright
    rotate([90, 0, 0]) {
        // Main Band
        ring_band();
        
        // Stone Setting
        // Positioned at the top of the band (Y = outer_radius)
        // Rotated so the setting tower points radially outward
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting_module();
    }
}