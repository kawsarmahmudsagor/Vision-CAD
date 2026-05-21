// Dimensional Parameters
inner_diameter = 16.5;
shank_width = 2.2;
head_width = 5.5;
shank_thickness = 1.8;
center_stone_diameter = 6.0;
small_stone_diameter = 1.8;
prong_diameter = 0.5;
head_height = center_stone_diameter * 1.5;

// Detail Density Parameters
halo_stone_count = 8;
pave_stones_per_row = 6;
pave_row_count = 2;

// Visual Materials
metal_color = "#B76E79"; // Rose Gold
gem_color = "#E0FFFF";   // Diamond/Clear

// Derived Measurements
inner_radius = inner_diameter / 2;
center_stone_radius = center_stone_diameter / 2;
small_stone_radius = small_stone_diameter / 2;
outer_radius_base = inner_radius + shank_thickness;
halo_orbit_radius = center_stone_radius + small_stone_radius * 1.1;

complete_ring_assembly();

module diamond_gem(radius) {
    color(gem_color)
    union() {
        // Top cone/cylinder
        translate([0, 0, radius * 0.3])
            cylinder(r1 = 0, r2 = radius, h = radius * 0.8, $fn = 32);
        // Table top
        translate([0, 0, radius * 1.1])
            cylinder(r = radius, h = radius * 0.05, $fn = 32);
        // Pavilion
        translate([0, 0, radius * 1.15])
            cylinder(r1 = radius, r2 = radius * 0.55, h = radius * 0.35, $fn = 32);
    }
}

module small_gem(radius) {
    color(gem_color)
    sphere(r = radius, $fn = 16);
}

module prong(pos_radius, height, angle) {
    color(metal_color)
    rotate([0, 0, angle])
    translate([pos_radius, 0, 0])
    cylinder(r = prong_diameter / 2, h = height, $fn = 12);
}

module tapered_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([inner_radius, 0, 0])
    hull() {
        // Inner wall
        square([0.1, shank_width], center = true);
        // Outer wall with taper logic
        // We use a simple hull of two shapes to simulate the taper 
        // since rotate_extrude uses a 2D profile. 
        // To achieve a true taper along the circumference, 
        // we'd need a more complex approach, but for a ring, 
        // we define the profile as the "average" or use a 
        // conditional in a loop. Here we use the head_width 
        // as the primary profile and subtract/cut later, 
        // or use a variable profile.
        // For this specific request, we'll use the head_width 
        // and create the "taper" by modifying the profile 
        // based on the angle if we were using a loop, 
        // but rotate_extrude is constant. 
        // Instead, we'll create the band and then 
        // the head is a separate union.
        translate([shank_thickness, 0])
            square([0.1, shank_width], center = true);
    }
}

module ring_head_structure() {
    color(metal_color)
    translate([0, outer_radius_base, 0])
    rotate([-90, 0, 0])
    union() {
        // Base plate for the head
        cylinder(r = head_width / 2, h = shank_thickness, $fn = 64);
        // Support tower
        cylinder(r1 = head_width / 3, r2 = center_stone_radius * 0.8, h = head_height * 0.4, $fn = 64);
    }
}

module center_stone_assembly() {
    translate([0, outer_radius_base, 0])
    rotate([-90, 0, 0])
    translate([0, 0, head_height * 0.4])
    union() {
        diamond_gem(center_stone_radius);
        // 4 Main Prongs
        for (i = [0, 90, 180, 270]) {
            rotate([0, 0, i])
            translate([center_stone_radius * 0.8, 0, 0])
            cylinder(r = prong_diameter / 2, h = center_stone_radius * 1.2, $fn = 12);
        }
    }
}

module halo_assembly() {
    translate([0, outer_radius_base, 0])
    rotate([-90, 0, 0])
    translate([0, 0, head_height * 0.4])
    union() {
        for (i = [0 : halo_stone_count - 1]) {
            angle = i * (360 / halo_stone_count);
            rotate([0, 0, angle])
            translate([halo_orbit_radius, 0, 0])
            union() {
                small_gem(small_stone_radius);
                // Tiny prongs for halo
                rotate([0, 0, 45])
                translate([small_stone_radius * 0.5, 0, 0])
                cylinder(r = prong_diameter / 4, h = small_stone_radius * 1.5, $fn = 8);
            }
        }
    }
}

module pave_shoulders() {
    // Two sides of the ring
    for (side = [-1, 1]) {
        for (row = [0 : pave_row_count - 1]) {
            row_offset = (row - (pave_row_count - 1) / 2) * small_stone_diameter * 1.2;
            for (i = [0 : pave_stones_per_row - 1]) {
                // Angle from the top (90 deg) outwards
                angle = 90 + (side * (15 + i * 12));
                rotate([0, 0, angle])
                translate([outer_radius_base - 0.2, 0, row_offset])
                union() {
                    small_gem(small_stone_radius * 0.8);
                    // Tiny prong
                    translate([0, 0, small_stone_radius * 0.8])
                    cylinder(r = prong_diameter / 4, h = 0.5, $fn = 8);
                }
            }
        }
    }
}

module complete_ring_assembly() {
    rotate([90, 0, 0]) {
        tapered_band();
        ring_head_structure();
        center_stone_assembly();
        halo_assembly();
        pave_shoulders();
    }
}