$fn = 128;

// Scale Anchor and Parameters
ring_outer_diameter = 22;
band_cross_section = ring_outer_diameter * 0.4;
band_height = ring_outer_diameter * 0.3;
setting_size = ring_outer_diameter * 0.4;
central_stone_diameter = ring_outer_diameter * 0.2;
small_stone_diameter = ring_outer_diameter * 0.05;
groove_width = ring_outer_diameter * 0.03;
groove_depth = ring_outer_diameter * 0.05;
small_stone_count = 12;
groove_count_per_side = 3;

ring_color = "Silver";
stone_color = "DiamondWhite";
setting_color = "Silver";

// Derived dimensions
ring_radius = ring_outer_diameter / 2;
inner_radius = ring_radius - band_cross_section;

module ring_body() {
    color(ring_color)
    difference() {
        // Main Torus-like band
        rotate_extrude()
        translate([ring_radius - band_cross_section/2, 0, 0])
        circle(d=band_cross_section);
        
        // Inner bore for finger
        cylinder(h=ring_outer_diameter, r=inner_radius, center=true);
        
        // Side Grooves
        for(side = [0, 180]) {
            rotate([0, 0, side])
            for(i = [0 : groove_count_per_side - 1]) {
                translate([ring_radius - groove_depth, (i - 1) * (band_cross_section/3), 0])
                rotate([0, 90, 0])
                cylinder(h=groove_width * 2, r=groove_width/2, center=true);
            }
        }
    }
}

module square_setting() {
    // Positioned at the top of the ring body
    translate([0, 0, ring_radius - (band_cross_section/2)])
    color(setting_color)
    cube([setting_size, setting_size, setting_size * 0.5], center=true);
}

module central_stone() {
    // Positioned above the setting
    translate([0, 0, ring_radius - (band_cross_section/2) + (setting_size * 0.25) + (central_stone_diameter * 0.1)])
    color(stone_color)
    sphere(d=central_stone_diameter);
}

module small_stones() {
    // Circular array on top of the square setting
    translate([0, 0, ring_radius - (band_cross_section/2) + (setting_size * 0.25)])
    for(i = [0 : small_stone_count - 1]) {
        rotate([0, 0, i * (360 / small_stone_count)])
        translate([setting_size * 0.3, 0, 0])
        color(stone_color)
        sphere(d=small_stone_diameter);
    }
}

// Assembly
union() {
    ring_body();
    square_setting();
    central_stone();
    small_stones();
}