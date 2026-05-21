// Dimensional Parameters
ring_inner_diameter = 17.0;
band_thickness = 2.0;
band_width = 4.0;
decorative_section_height = 3.0;
stone_diameter = 1.0;
prong_height = 1.2;
prong_thickness = 0.4;

// Detail Density Parameters
stones_per_row = 8;
row_count = 3;

// Visual Materials
band_color = "#FFD700"; // Gold
stone_color = "#E0FFFF"; // Diamond/Silver

// Derived Measurements
inner_radius = ring_inner_diameter / 2;
outer_radius = inner_radius + band_thickness;
stone_radius = stone_diameter / 2;

complete_ring_assembly();

module stone_prong_assembly() {
    union() {
        // The Stone
        color(stone_color)
        sphere(r = stone_radius, $fn = 24);
        
        // Prongs (4 prongs around the stone)
        color(band_color)
        for (angle = [0, 90, 180, 270]) {
            rotate([0, 0, angle])
            translate([stone_radius * 0.8, 0, -prong_height/2])
            cylinder(r = prong_thickness/2, h = prong_height, $fn = 12);
        }
    }
}

module ring_band() {
    color(band_color)
    rotate_extrude($fn = 120)
    translate([inner_radius, 0, 0])
    hull() {
        // Flat inner wall
        square([0.1, band_width], center = true);
        // Rounded outer profile
        translate([band_thickness, band_width/2]) circle(r = 0.5, $fn = 24);
        translate([band_thickness, -band_width/2]) circle(r = 0.5, $fn = 24);
    }
}

module decorative_arc() {
    // Calculate spacing for 3 concentric rows
    row_spacing = decorative_section_height / (row_count - 1);
    
    for (row = [0 : row_count - 1]) {
        // Offset each row slightly in radius to create the "extending outward" effect
        current_row_radius = outer_radius + (row * 0.5);
        
        for (i = [0 : stones_per_row - 1]) {
            // Distribute stones across the upper 180 degrees
            angle = 180 - (i * (160 / (stones_per_row - 1))); 
            
            rotate([0, 0, angle])
            translate([current_row_radius, 0, 0])
            rotate([0, 90, 0]) // Orient stone to face outward
            stone_prong_assembly();
        }
    }
}

module complete_ring_assembly() {
    // Rotate to sit upright for display
    rotate([90, 0, 0]) {
        ring_band();
        decorative_arc();
    }
}