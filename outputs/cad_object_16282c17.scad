// Dimensional Parameters
ring_inner_diameter = 16.5;
band_width_bottom = 2.2;
band_width_top = 3.8;
band_thickness = 1.8;
center_stone_radius = 3.5;
setting_height = 5.5;
accent_stone_radius = 0.6;

// Detail Density Parameters
prong_count = 4;
band_stone_count = 14; // per side
basket_stone_count = 10;

// Visual Materials
metal_color = "#E5E4E2"; // Platinum/White Gold
gem_color = "#F0F8FF";    // Diamond/Clear

// Derived Measurements
inner_radius = ring_inner_diameter / 2;
outer_radius = inner_radius + band_thickness;
band_center_radius = inner_radius + band_thickness / 2;

complete_ring_assembly();

module gemstone(radius, height, is_center = true) {
    color(gem_color)
    union() {
        // Crown (top part)
        cylinder(r1 = radius * 0.6, r2 = radius, h = height * 0.3, center = true, $fn = 32);
        // Pavilion (bottom part)
        translate([0, 0, -height * 0.1])
        cylinder(r1 = 0, r2 = radius * 0.6, h = height * 0.7, center = true, $fn = 32);
    }
}

module accent_gem(radius) {
    color(gem_color)
    sphere(r = radius, $fn = 12);
}

module tapered_band() {
    color(metal_color)
    union() {
        // We build the band using segments to achieve a smooth taper in width
        for (angle = [0 : 5 : 355]) {
            // Width varies from band_width_bottom at 180deg to band_width_top at 0deg
            current_width = band_width_bottom + (band_width_top - band_width_bottom) * (0.5 + 0.5 * cos(angle));
            
            rotate([0, 0, angle])
            translate([band_center_radius, 0, 0])
            rotate([0, 90, 0])
            cylinder(h = current_width, r = band_thickness / 2, center = true, $fn = 16);
        }
    }
}

module band_pavé() {
    // Place stones on the top half of the band
    for (side = [-1, 1]) {
        for (i = [1 : band_stone_count]) {
            angle = side * (i * (90 / band_stone_count));
            // Calculate width at this specific angle for placement
            current_width = band_width_bottom + (band_width_top - band_width_bottom) * (0.5 + 0.5 * cos(angle));
            
            rotate([0, 0, angle])
            translate([outer_radius - 0.2, 0, 0])
            accent_gem(accent_stone_radius);
        }
    }
}

module setting_head() {
    color(metal_color)
    union() {
        // Basket base
        difference() {
            cylinder(r = center_stone_radius * 0.85, h = setting_height * 0.4, $fn = 48);
            translate([0, 0, -1])
            cylinder(r = center_stone_radius * 0.7, h = setting_height * 0.4 + 2, $fn = 48);
        }
        
        // Basket pavé stones
        for (i = [0 : basket_stone_count - 1]) {
            rotate([0, 0, i * (360 / basket_stone_count)])
            translate([center_stone_radius * 0.85, 0, setting_height * 0.2])
            accent_gem(accent_stone_radius * 0.8);
        }
        
        // Prongs
        for (i = [0 : prong_count - 1]) {
            rotate([0, 0, i * (360 / prong_count)])
            translate([center_stone_radius * 0.7, 0, 0])
            hull() {
                sphere(r = band_thickness / 3, $fn = 12);
                translate([0, 0, setting_height * 0.8])
                sphere(r = band_thickness / 4, $fn = 12);
            }
        }
    }
}

module complete_ring_assembly() {
    // Orient the ring to sit upright for display
    rotate([90, 0, 0]) {
        tapered_band();
        band_pavé();
        
        // Position the head on top of the band
        translate([band_center_radius, 0, 0]) {
            // The head is shifted so the stone sits above the band
            translate([0, 0, -setting_height * 0.1]) {
                setting_head();
                translate([0, 0, setting_height * 0.3])
                gemstone(center_stone_radius, setting_height);
            }
        }
    }
}