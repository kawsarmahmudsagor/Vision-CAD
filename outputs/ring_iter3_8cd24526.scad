// Dimensional Parameters
inner_radius = 8.5;
outer_radius = 10.3;
band_width = 2.5;
stone_width = 7.357;
prong_radius = 0.441;
prong_height = 7.68;
prong_radial_dist = 3.943;
stone_height = 5.5; // Estimated based on prong height and width

// Visual Materials
metal_color = "#C0C0C0"; // Platinum/White Gold
gem_color = "#F0F8FF";   // Diamond

// Derived Measurements
band_thickness = outer_radius - inner_radius;
stone_radius = stone_width / 2;
pavilion_h = stone_height * 0.6;
crown_h = stone_height * 0.3;
table_h = 0.2;
gallery_h = stone_height * 0.4;
prong_angles = [-90.1, -125.2, 126.2, 90.1];

complete_ring_assembly();

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([inner_radius + band_thickness / 2, 0, 0])
    hull() {
        // Flat inner part of the D-profile
        square([band_thickness, band_width], center = true);
        // Rounded outer part of the D-profile
        translate([band_thickness / 2, 0, 0])
        circle(r = band_width / 2, $fn = 48);
    }
}

module stone_gem_module() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = pavilion_h, $fn = 48);
        // Crown (frustum)
        translate([0, 0, pavilion_h])
        cylinder(r1 = stone_radius, r2 = stone_radius * 0.6, h = crown_h, $fn = 48);
        // Table (flat top)
        translate([0, 0, pavilion_h + crown_h])
        cylinder(r = stone_radius * 0.6, h = table_h, $fn = 48);
    }
}

module gallery_basket() {
    color(metal_color)
    difference() {
        // Outer shell of the basket
        cylinder(r1 = stone_radius * 1.25, r2 = stone_radius * 0.85, h = gallery_h, $fn = 48);
        // Inner hollow to seat the stone
        translate([0, 0, -0.1])
        cylinder(r1 = stone_radius * 0.85, r2 = stone_radius * 0.55, h = gallery_h + 0.2, $fn = 48);
    }
}

module prong_claws() {
    color(metal_color)
    for (angle = prong_angles) {
        rotate([0, 0, angle])
        translate([prong_radial_dist, 0, 0])
        union() {
            // Prong shaft
            cylinder(r = prong_radius, h = prong_height, $fn = 24);
            // Round tip
            translate([0, 0, prong_height])
            sphere(r = prong_radius * 1.25, $fn = 24);
        }
    }
}

module stone_setting_module() {
    // Local Z = 0 is the base where it attaches to the band
    gallery_basket();
    stone_gem_module();
    prong_claws();
}

module complete_ring_assembly() {
    // Display orientation: upright
    rotate([90, 0, 0]) {
        ring_band();
        
        // Place the stone setting on top of the band
        // translate([0, outer_radius, 0]) moves it to the top of the band
        // rotate([-90, 0, 0]) aligns the stone's local Z axis with the ring's Y axis
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        stone_setting_module();
    }
}