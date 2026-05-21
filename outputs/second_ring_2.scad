// Dimensional Parameters
ring_inner_diameter = 16.5;
central_diamond_diameter = 6.0;
band_width_base = central_diamond_diameter * 1.5;
band_thickness = band_width_base * 0.25;

// Detail Density Parameters
halo_diamond_count = 8;
pave_diamonds_per_row = 6;
central_prong_count = 8;

// Visual Materials
metal_color = "#B76E79"; // Rose Gold
diamond_color = "#E0FFFF"; // Light Cyan/Diamond

// Derived Measurements
inner_radius = ring_inner_diameter / 2;
outer_radius = inner_radius + band_thickness;
halo_diamond_diameter = central_diamond_diameter * 0.5;
pave_diamond_diameter = central_diamond_diameter * 0.3;
prong_diameter = 0.6;
central_stone_protrusion = central_diamond_diameter * 0.4;
halo_radius = (central_diamond_diameter / 2) + (halo_diamond_diameter / 2);

complete_ring_assembly();

module diamond_sphere(diameter) {
    color(diamond_color)
    sphere(d = diameter, $fn = 32);
}

module prong(height) {
    color(metal_color)
    cylinder(d = prong_diameter, h = height, $fn = 12);
}

module band_shank() {
    color(metal_color)
    rotate_extrude($fn = 120)
    translate([inner_radius, 0, 0])
    hull() {
        // Flat inner surface
        square([0.1, band_width_base], center = true);
        // Rounded outer profile
        translate([band_thickness, band_width_base/2 - 0.5])
            circle(r = 0.5, $fn = 24);
        translate([band_thickness, -band_width_base/2 + 0.5])
            circle(r = 0.5, $fn = 24);
        translate([band_thickness, 0])
            square([0.1, band_width_base * 0.6], center = true);
    }
}

module central_cluster() {
    // Central Diamond
    translate([0, 0, outer_radius + central_stone_protrusion/2])
    diamond_sphere(central_diamond_diameter);
    
    // Central Prongs
    for (i = [0 : central_prong_count - 1]) {
        rotate([0, 0, i * (360 / central_prong_count)])
        translate([central_diamond_diameter/2, 0, outer_radius])
        prong(central_stone_protrusion + 1);
    }
    
    // Halo Diamonds
    for (i = [0 : halo_diamond_count - 1]) {
        angle = i * (360 / halo_diamond_count);
        rotate([0, 0, angle])
        translate([halo_radius, 0, outer_radius + halo_diamond_diameter/4])
        diamond_sphere(halo_diamond_diameter);
        
        // Halo Prongs
        rotate([0, 0, angle])
        translate([halo_radius + halo_diamond_diameter/2, 0, outer_radius])
        prong(halo_diamond_diameter/2);
    }
}

module pave_rows() {
    row_offset = band_width_base * 0.25;
    pave_z_start = 20; // Degrees from center
    pave_z_end = 160;
    
    // Two rows on each side (Left and Right)
    for (side = [-1, 1]) {
        for (row = [-1, 1]) {
            for (i = [0 : pave_diamonds_per_row - 1]) {
                angle = (pave_z_start + (i * (pave_z_end - pave_z_start) / (pave_diamonds_per_row - 1))) * side;
                
                rotate([0, 0, angle])
                translate([outer_radius - 0.2, row * row_offset, 0])
                union() {
                    diamond_sphere(pave_diamond_diameter);
                    // Small prong for pave
                    translate([0, 0, -pave_diamond_diameter/2])
                    prong(pave_diamond_diameter);
                }
            }
        }
    }
}

module complete_ring_assembly() {
    // Orient for display
    rotate([90, 0, 0]) {
        band_shank();
        
        // Position the cluster at the top (Y axis)
        translate([0, 0, 0])
        rotate([0, 0, 0])
        central_cluster();
        
        // Pave diamonds along the band
        pave_rows();
        
        // Brand engraving (simplified as a cutout)
        translate([0, 0, -inner_radius])
        rotate([0, 0, 0])
        color("Black")
        text("AZARAI", size = 1.5, halign = "center", valign = "center", font = "Arial:style=Bold");
    }
}