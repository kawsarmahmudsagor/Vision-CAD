// Dimensional Parameters
inner_radius = 8.5;
band_thickness_base = 10.3 - 8.5;
band_thickness_delta = 2.131;
band_width = 2.5;

stone_width = 7.357;
stone_height = 7.68; // Using prong_height as proxy for realistic stone height

prong_count = 4;
prong_radius = 0.441;
prong_height = 7.68;
prong_radial_dist = 3.943;
prong_angles = [-90.1, -125.2, 126.2, 90.1];

// Visual Materials
metal_color = "#C0C0C0";
gem_color = "#E0FFFF";

// Derived Measurements
band_thickness = band_thickness_base + band_thickness_delta;
outer_radius = inner_radius + band_thickness;
stone_radius = stone_width / 2;

complete_ring_assembly();

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([inner_radius, 0, 0])
    hull() {
        // Flat inner surface
        square([0.1, band_width], center = true);
        // Rounded outer surface (D-profile)
        translate([band_thickness, 0, 0])
        circle(r = band_width / 2, $fn = 32);
    }
}

module stone_gem_module() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = stone_height * 0.6, $fn = 48);
        
        // Crown (frustum)
        translate([0, 0, stone_height * 0.6])
        cylinder(r1 = stone_radius, r2 = stone_radius * 0.6, h = stone_height * 0.3, $fn = 48);
        
        // Table (flat top)
        translate([0, 0, stone_height * 0.9])
        cylinder(r = stone_radius * 0.6, h = 0.1, $fn = 48);
    }
}

module gallery_basket() {
    color(metal_color)
    difference() {
        // Outer basket shell
        cylinder(r1 = stone_radius * 1.2, r2 = stone_radius * 0.8, h = stone_height * 0.3, $fn = 48);
        // Inner hollow for stone pavilion
        translate([0, 0, -0.1])
        cylinder(r1 = stone_radius * 0.7, r2 = stone_radius * 0.5, h = stone_height * 0.3 + 0.2, $fn = 48);
    }
}

module claw_prong(angle) {
    color(metal_color)
    rotate([0, 0, angle])
    translate([prong_radial_dist, 0, 0])
    union() {
        // Prong shaft
        cylinder(r = prong_radius, h = prong_height, $fn = 16);
        // Round tip
        translate([0, 0, prong_height])
        sphere(r = prong_radius * 1.25, $fn = 20);
    }
}

module stone_setting_module() {
    // 1. Gallery basket - structural base
    gallery_basket();
    
    // 2. Center stone - pavilion tip at local Z=0
    stone_gem_module();
    
    // 3. Prongs - rising from base to hook over girdle
    for (a = prong_angles) {
        claw_prong(a);
    }
}

module complete_ring_assembly() {
    // Display orientation: upright
    rotate([90, 0, 0]) {
        // Main band
        ring_band();
        
        // Stone setting assembly
        // Positioned at the top of the band (Y = outer_radius)
        // Rotated so the setting tower points radially outward (+Y)
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting_module();
    }
}