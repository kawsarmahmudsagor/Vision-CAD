// Dimensional Parameters
inner_radius = 8.5;
outer_radius = 10.3;
band_width = 2.5;
stone_width = 7.357;
prong_radius = 0.441;
prong_height = 7.68;
prong_radial_dist = 3.943;
prong_count = 4;

// Detail Density Parameters
prong_angles = [-90.1, -125.2, 126.2, 90.1];
band_resolution = 120;
stone_resolution = 48;
prong_resolution = 24;

// Visual Materials
metal_color = "#C0C0C0";
gem_color = "#E0FFFF";

// Derived Measurements
stone_radius = stone_width / 2;
band_thickness_total = outer_radius - inner_radius;
band_thickness_flat = band_thickness_total - (band_width / 2);
pavilion_height = prong_height * 0.65;
crown_height = prong_height * 0.35;
table_radius = stone_radius * 0.55;
basket_height = pavilion_height * 0.8;

complete_ring_assembly();

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = band_resolution)
    translate([inner_radius, 0, 0])
    hull() {
        // Flat inner part of the D-profile
        square([0.1, band_width], center = true);
        // Rounded outer part of the D-profile
        translate([band_thickness_flat, 0, 0])
        circle(r = band_width / 2, $fn = prong_resolution);
    }
}

module stone_gem_module() {
    color(gem_color)
    union() {
        // Pavilion (bottom cone)
        cylinder(r1 = 0, r2 = stone_radius, h = pavilion_height, $fn = stone_resolution);
        // Crown (frustum)
        translate([0, 0, pavilion_height])
        cylinder(r1 = stone_radius, r2 = table_radius, h = crown_height, $fn = stone_resolution);
        // Table (flat top)
        translate([0, 0, pavilion_height + crown_height])
        cylinder(r = table_radius, h = 0.3, $fn = stone_resolution);
    }
}

module claw_prong() {
    color(metal_color)
    union() {
        // Prong shaft
        cylinder(r = prong_radius, h = prong_height, $fn = prong_resolution);
        // Rounded tip
        translate([0, 0, prong_height])
        sphere(r = prong_radius * 1.25, $fn = prong_resolution);
    }
}

module gallery_basket() {
    color(metal_color)
    difference() {
        // Outer basket shell
        cylinder(r1 = stone_radius * 1.2, r2 = stone_radius * 0.8, h = basket_height, $fn = stone