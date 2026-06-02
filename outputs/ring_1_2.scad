// Engagement Ring Parameters
engagement_band_width_base = 3.0;
engagement_band_width_top = 5.0;
ring_inner_radius = 8.5;
ring_height = 2.0;
diamond_radius = 4.0;
diamond_height = 6.0;
prong_count = 6;
prong_thickness = 0.6;
prong_height = 5.0;
head_lift_height = 2.0;
milgrain_bead_radius = 0.2;
milgrain_spacing = 0.8;
engagement_metal_color = "Silver";
diamond_color = "SkyBlue";

// Wedding Band Parameters
wedding_band_width = 4.5;
wedding_band_radius = ring_inner_radius;
wedding_metal_color = "Silver";
accent_diamond_radius = 0.6;

module milgrain_ring(radius, height, bead_r, spacing) {
    circumference = 2 * PI * radius;
    num_beads = floor(circumference / spacing);
    for (i = [0 : num_beads - 1]) {
        rotate([0, 0, i * (360 / num_beads)])
        translate([radius, 0, height / 2])
        sphere(r = bead_r, $fn = 8);
    }
}

module diamond_cut(r, h) {
    color(diamond_color)
    union() {
        cylinder(h = h * 0.3, r1 = r * 0.8, r2 = r, $fn = 32);
        translate([0, 0, h * 0.3])
        cylinder(h = h * 0.7, r1 = 0, r2 = r, $fn = 32);
    }
}

module engagement_ring() {
    color(engagement_metal_color)
    difference() {
        union() {
            // Tapered Band
            hull() {
                rotate_extrude(convexity = 10)
                translate([ring_inner_radius, 0, 0])
                square([engagement_band_width_base, ring_height]);
                
                rotate_extrude(convexity = 10)
                translate([ring_inner_radius, 0, 0])
                square([engagement_band_width_top, ring_height]);
            }
            
            // Raised Head/Setting
            translate([0, 0, ring_height + head_lift_height])
            cylinder(h = 1, r = diamond_radius * 0.8, $fn = 32);
            
            // Prongs
            for (i = [0 : prong_count - 1]) {
                rotate([0, 0, i * (360 / prong_count)])
                translate([diamond_radius * 0.9, 0, ring_height])
                cylinder(h = prong_height, r = prong_thickness, $fn = 12);
            }
            
            // Milgrain Edges
            milgrain_ring(ring_inner_radius + engagement_band_width_base, ring_height, milgrain_bead_radius, milgrain_spacing);
        }
        
        // Inner Bore
        rotate_extrude()
        translate([ring_inner_radius - 0.1, 0, 0])
        square([0.2, ring_height + 1]);
    }
    
    // Main Diamond
    translate([0, 0, ring_height + head_lift_height + 1])
    diamond_cut(diamond_radius, diamond_height);
}

module wedding_band() {
    color(wedding_metal_color)
    difference() {
        union() {
            // Main Band
            rotate_extrude()
            translate([wedding_band_radius, 0, 0])
            square([wedding_band_width, ring_height * 1.5]);
            
            // Milgrain
            milgrain_ring(wedding_band_radius + wedding_band_width, ring_height * 1.5, milgrain_bead_radius, milgrain_spacing);
        }
        
        // Inner Bore
        rotate_extrude()
        translate([wedding_band_radius - 0.1, 0, 0])
        square([0.2, ring_height * 1.5 + 1]);
        
        // Pavé Cutouts (simplified as holes for diamonds)
        for (i = [0 : 20]) {
            rotate([0, 0, i * 18])
            translate([wedding_band_radius + wedding_band_width/2, 0, ring_height * 0.75])
            sphere(r = accent_diamond_radius, $fn = 8);
        }
    }
}

// Assembly
translate([0, 0, 0])
engagement_ring();

translate([ring_inner_radius * 2.5, 0, 0])
wedding_band();