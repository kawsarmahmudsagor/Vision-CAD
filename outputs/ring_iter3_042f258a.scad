// Classic Solitaire Engagement Ring

// Dimensional Parameters
ring_inner_radius = 8.5;
ring_outer_radius = 10.3;
band_width = 2.5;
stone_diameter = 7.357;
stone_total_height = 6.18; // Derived from 16.48 - 10.3
prong_count = 4;
prong_radius = 1.5;
prong_height = 7.18;
prong_radial_distance = 3.679;
prong_base_z = 9.8;
stone_base_z = 10.3;
stone_top_z = 16.48;

// Visual Materials
metal_color = "#E5E4E2"; // Platinum/White Gold
gem_color = "#F0F8FF";   // Diamond

// Derived Measurements
stone_radius = stone_diameter / 2;
band_wall_thickness = ring_outer_radius - ring_inner_radius;
pavilion_height = stone_total_height * 0.55;
crown_height = stone_total_height * 0.45;
table_radius = stone_radius * 0.56;
tip_overlap = prong_radius * 0.8;
prong_angles = [-90.1, -125.2, 126.2, 90.1];

complete_ring_assembly();

module diamond_gem() {
    color(gem_color)
    translate([0, 0, stone_base_z]) {
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
    translate([0, 0, prong_base_z])
    rotate([0, 0, angle])
    hull() {
        // Base of the prong
        translate([prong_radial_distance, 0, 0])
        sphere(r = prong_radius, $fn = 24);
        
        // Shaft of the prong
        translate([prong_radial_distance * 1.05, 0, stone_top_z * 0.75 - prong_base_z])
        sphere(r = prong_radius * 0.9, $fn = 24);
        
        // Claw tip curving inward
        translate([prong_radial_distance * 0.85, 0, stone_top_z + tip_overlap - prong_base_z])
        sphere(r = prong_radius * 0.8, $fn = 24);
    }
}

module ring_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([ring_inner_radius, 0, 0])
    hull() {
        // Create a rounded rectangle profile for the band
        translate([0, band_width / 2 - 0.5]) circle(r = 0.5, $fn = 24);
        translate([0, -band_width / 2 + 0.5]) circle(r = 0.5, $fn = 24);
        translate([band_wall_thickness - 1, band_width / 2 - 0.5]) circle(r = 0.5, $fn = 24);
        translate([band_wall_thickness - 1, -band_width / 2 + 0.5]) circle(r = 0.5, $fn = 24);
    }
}

module complete_ring_assembly() {
    // Orient the ring to sit upright for display
    rotate([90, 0, 0]) {
        union() {
            ring_band();
            diamond_gem();
            
            // Place the 4 prongs at the specified angles
            for (i = [0 : prong_count - 1]) {
                claw_prong(prong_angles[i]);
            }
        }
    }
}