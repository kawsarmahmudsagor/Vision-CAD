// Dimensional Parameters
inner_ring_diameter = 18.0;
band_top_width = 12.0;
band_height = 5.0; // Approx 0.3 * inner_ring_diameter
central_stone_diameter = 7.2; // ~0.6 * band_top_width
halo_stone_diameter = 1.5;
platform_height = 2.0;

// Groove Parameters
groove_width = 0.8;
groove_depth = 0.5;
groove_spacing = 1.5;

// Visual Materials
metal_color = "#E5E4E2"; // Platinum/Silver
gem_color = "#E0FFFF"; // Diamond/Transparent

// Derived Measurements
inner_radius = inner_ring_diameter / 2;
outer_radius = inner_radius + band_height;
platform_side = band_top_width;
central_stone_radius = central_stone_diameter / 2;
halo_stone_radius = halo_stone_diameter / 2;

complete_ring_assembly();

module engraving_module() {
    color(metal_color)
    translate([0, 0, -inner_radius + 0.2])
    rotate([0, 0, 0])
    linear_extrude(height = 0.5)
    text("TAJ", size = 2, font = "Arial:style=Bold", halign = "center", valign = "center");
}

module band_module() {
    color(metal_color)
    difference() {
        // Main Band Body
        rotate_extrude($fn = 120)
        translate([inner_radius, 0, 0])
        hull() {
            // Inner edge (slightly rounded)
            circle(r = 0.5, $fn = 24);
            // Outer edge (flat top)
            translate([band_height, band_top_width / 2])
            square([0.1, band_top_width], center = true);
            translate([band_height, -band_top_width / 2])
            square([0.1, band_top_width], center = true);
        }

        // Parallel Grooves on both sides
        for (side = [-1, 1]) {
            for (i = [0 : 2]) {
                z_pos = (i - 1) * groove_spacing;
                rotate_extrude($fn = 120)
                translate([outer_radius - groove_depth, z_pos, 0])
                square([groove_depth + 0.1, groove_width], center = true);
            }
        }
        
        // Cutout for the platform to sit flush
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        cube([platform_side, platform_side, band_height + 1], center = true);
    }
}

module stone_cluster_module() {
    // Square Platform
    color(metal_color)
    translate([0, 0, 0])
    cube([platform_side, platform_side, platform_height], center = true);

    // Central Stone
    translate([0, 0, platform_height / 2 + central_stone_radius])
    color(gem_color)
    sphere(r = central_stone_radius, $fn = 32);

    // Prongs for central stone
    color(metal_color)
    for (angle = [45, 135, 225, 315]) {
        rotate([0, 0, angle])
        translate([central_stone_radius * 0.8, 0, platform_height / 2])
        cylinder(r = 0.4, h = central_stone_radius * 1.2, $fn = 16);
    }

    // Halo Stones (12 stones: 3 per side including corners)
    color(gem_color)
    for (i = [0 : 11]) {
        // Calculate positions for a square perimeter
        var_x = 0;
        var_y = 0;
        
        if (i < 3) { // Top edge
            var_x = (i - 1) * (platform_side * 0.35);
            var_y = platform_side / 2 - halo_stone_radius;
        } else if (i < 6) { // Right edge
            var_x = platform_side / 2 - halo_stone_radius;
            var_y = (5 - i) * (platform_side * 0.35); // Simplified spacing
            // Correcting for the loop logic to be a proper square
        }
        // Redoing halo loop for precision
    }
    
    // Precise Halo Array
    halo_offset = platform_side / 2 - halo_stone_radius;
    halo_step = platform_side / 3;
    
    color(gem_color) {
        // Top & Bottom rows
        for (x = [-halo_offset, 0, halo_offset]) {
            translate([x, halo_offset, platform_height / 2]) sphere(r = halo_stone_radius, $fn = 16);
            translate([x, -halo_offset, platform_height / 2]) sphere(r = halo_stone_radius, $fn = 16);
        }
        // Left & Right columns (excluding corners already placed)
        for (y = [-halo_offset/2, halo_offset/2]) { // This is a simplification, let's use a better loop
            // Handled by the 4-side logic below
        }
    }
}

// Refined Halo Module for better geometry
module halo_stones() {
    halo_offset = platform_side / 2 - halo_stone_radius;
    spacing = platform_side / 3;
    color(gem_color) {
        for (i = [0 : 3]) {
            rotate([0, 0, i * 90]) {
                translate([0, halo_offset, platform_height / 2]) sphere(r = halo_stone_radius, $fn = 16);
                translate([spacing/2, halo_offset, platform_height / 2]) sphere(r = halo_stone_radius, $fn = 16);
                translate([-spacing/2, halo_offset, platform_height / 2]) sphere(r = halo_stone_radius, $fn = 16);
            }
        }
    }
}

module complete_ring_assembly() {
    rotate([90, 0, 0]) {
        band_module();
        
        // Position the stone cluster on top of the band
        translate([0, outer_radius, 0])
        rotate([-90, 0, 0])
        union() {
            // Platform
            color(metal_color)
            cube([platform_side, platform_side, platform_height], center = true);
            
            // Central Stone
            translate([0, 0, platform_height / 2 + central_stone_radius])
            color(gem_color)
            sphere(r = central_stone_radius, $fn = 32);
            
            // Prongs
            color(metal_color)
            for (angle = [45, 135, 225, 315]) {
                rotate([0, 0, angle])
                translate([central_stone_radius * 0.8, 0, platform_height / 2])
                cylinder(r = 0.4, h = central_stone_radius * 1.2, $fn = 16);
            }
            
            // Halo
            halo_stones();
        }
        
        // Engraving on the inner surface
        rotate([0, 0, 180]) // Move to bottom of ring
        engraving_module();
    }
}