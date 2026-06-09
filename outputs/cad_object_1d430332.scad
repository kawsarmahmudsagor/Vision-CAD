// Dimensional Parameters
ring_inner_diameter = 16.5;
inner_band_width = 2.5;
outer_band_width = 6.5;
band_wall_thickness = 1.8;
center_stone_radius = 4.0;
setting_height = 3.5;
prong_thickness = 0.6;

// Detail Density Parameters
prong_count = 6;
pave_stone_count_per_row = 24;
milgrain_bead_count_per_row = 48;

// Visual Materials
metal_color = "#E5E4E2"; // Platinum/Silver
gem_color = "#F0F8FF";    // Diamond/Clear

// Derived Measurements
inner_radius = ring_inner_diameter / 2;
outer_radius = inner_radius + band_wall_thickness;
pave_row_offset = outer_band_width * 0.25;

complete_ring_assembly();

// --- Utility Modules ---

module faceted_gem(radius) {
    color(gem_color)
    union() {
        // Crown (top part)
        translate([0, 0, radius * 0.2])
        cylinder(r1 = radius * 0.8, r2 = radius, h = radius * 0.2, $fn = 32);
        
        // Table (flat top)
        translate([0, 0, radius * 0.4])
        cylinder(r = radius * 0.8, h = 0.2, $fn = 32);
        
        // Pavilion (bottom cone)
        translate([0, 0, radius * 0.2])
        cylinder(r1 = 0, r2 = radius * 0.8, h = radius * 0.8, center = true, $fn = 32);
    }
}

module small_pave_gem(radius) {
    color(gem_color)
    sphere(r = radius, $fn = 12);
}

module milgrain_bead(radius) {
    color(metal_color)
    sphere(r = radius, $fn = 12);
}

// --- Component Modules ---

module inner_band() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([inner_radius + 0.2, 0, 0])
    hull() {
        square([band_wall_thickness * 0.8, inner_band_width], center = true);
        translate([0, inner_band_width/2, 0]) circle(r = 0.3, $fn = 16);
        translate([0, -inner_band_width/2, 0]) circle(r = 0.3, $fn = 16);
    }
}

module outer_band() {
    color(metal_color)
    union() {
        // Main Band Body
        rotate_extrude($fn = 120)
        translate([inner_radius + 0.5, 0, 0])
        hull() {
            square([band_wall_thickness, outer_band_width], center = true);
            translate([band_wall_thickness/2, outer_band_width/2, 0]) circle(r = 0.5, $fn = 16);
            translate([band_wall_thickness/2, -outer_band_width/2, 0]) circle(r = 0.5, $fn = 16);
        }

        // Pavé and Milgrain details
        // We only place these on the top half of the ring (approx 180 degrees)
        for (row_idx = [-1, 1]) {
            z_pos = row_idx * pave_row_offset;
            
            // Pavé Stones
            for (i = [0 : pave_stone_count_per_row - 1]) {
                angle = i * (180 / (pave_stone_count_per_row - 1));
                rotate([0, 0, angle])
                translate([outer_radius + 0.2, 0, z_pos])
                small_pave_gem(0.5);
            }
            
            // Milgrain Borders (Inner and Outer of the row)
            for (border_offset = [-0.6, 0.6]) {
                for (j = [0 : milgrain_bead_count_per_row - 1]) {
                    angle = j * (180 / (milgrain_bead_count_per_row - 1));
                    rotate([0, 0, angle])
                    translate([outer_radius + 0.4, 0, z_pos + border_offset])
                    milgrain_bead(0.25);
                }
            }
        }
    }
}

module setting_basket() {
    color(metal_color)
    union() {
        // Base of the basket
        translate([0, outer_radius, 0])
        cylinder(r1 = outer_band_width * 0.6, r2 = center_stone_radius * 0.7, h = setting_height * 0.4, $fn = 32);
        
        // Prongs
        for (i = [0 : prong_count - 1]) {
            rotate([0, 0, i * (360 / prong_count)])
            translate([center_stone_radius * 0.7, outer_radius, 0])
            hull() {
                cylinder(r = prong_thickness, h = 1, $fn = 16);
                translate([0, 0, setting_height])
                cylinder(r = prong_thickness * 0.7, h = 1, $fn = 16);
            }
        }
    }
}

module center_stone_assembly() {
    translate([0, outer_radius, setting_height * 0.6])
    faceted_gem(center_stone_radius);
}

// --- Final Assembly ---

module complete_ring_assembly() {
    // Rotate to sit flat on the XZ plane for viewing
    rotate([90, 0, 0]) {
        inner_band();
        outer_band();
        setting_basket();
        center_stone_assembly();
    }
}