// Dimensional Parameters
inner_radius = 8.5;
outer_radius = 10.3;
band_width = 2.5;
stone_width = 7.357;
prong_radius = 0.441;
prong_height = 7.68;
prong_radial_dist = 3.943;

// Detail Density Parameters
prong_count = 4;
stone_fn = 48;
band_fn = 120;
prong_fn = 16;

// Visual Materials
metal_color = "#C0C0C0";
gem_color = "#E0FFFF";

// Derived Measurements
stone_radius = stone_width / 2;
// Using a scaled version of the provided ground truth height to fit the physical scale of the prongs
stone_height_total = abs(-239.157 - 81.779) / 50; 
pavilion_height = stone_height_total * 0.6;
crown_height = stone_height_total * 0.4;
table_radius = stone_radius * 0.6;
basket_height = prong_height * 0.3;
prong_angles = [-90.1, -125.2, 126.2, 90.1];

complete_ring_assembly();

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = band_fn)
    translate([inner_radius, 0, 0])
    hull() {
        // Inner flat surface
        square([0.1, band_width], center = true);
        // Outer rounded surface (D-profile)
        translate([outer_radius - inner_radius, 0, 0])
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
        cylinder(r = table_radius, h = 0.3, $fn = stone_fn);
    }
}

module claw_prong(angle) {
    color(metal_color)
    rotate([0, 0, angle])
    translate([prong_radial_dist, 0, 0])
    union() {
        // Prong shaft
        cylinder(r = prong_radius, h = prong_height, $fn = prong_fn);
        // Round tip
        translate([0, 0, prong_height])
        sphere(r = prong_radius * 1.25, $fn = 20);
    }
}

module gallery_basket() {
    color(metal_color)
    difference() {
        // Outer basket shell
        cylinder(r1 = stone_radius * 1.2, r2 = stone_radius * 0.8, h = basket_height, $fn = stone_fn);
        // Inner hollow
        translate([0, 0, -0.1])
        cylinder(r1 = stone_radius * 0.7, r2 = stone_radius * 0.5, h = basket_height + 0.2, $fn = stone_fn);
    }
}

module stone_setting_module() {
    // 1. Gallery basket - structural base
    gallery_basket();
    
    // 2. Center stone - pavilion tip at local Z=0
    stone_gem_module();
    
    // 3. Prongs - rising from base to hold the stone
    for (i = [0 : prong_count - 1]) {
        claw_prong(prong_angles[i]);
    }
}

module complete_ring_assembly() {
    // Display orientation: upright
    rotate([90, 0, 0]) {
        // Main band
        ring_band();
        
        // Stone setting assembly
        // Positioned at the top of the band (Y = outer_radius)
        // Rotated so the setting tower points outward along the ring's local Y axis
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting_module();
    }
}