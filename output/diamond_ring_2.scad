ring_inner_radius = 10;
ring_band_thickness = 2.5;
ring_band_width = 6;
central_diamond_radius = 3.5;
small_diamond_radius = 0.6;
milgrain_radius = 0.3;
prong_radius = 0.5;
prong_height = 5;
prong_count = 6;

metal_color = "#C0C0C0";
diamond_color = "#E0FFFF";
milgrain_color = "#A9A9A9";

module ring_base() {
    color(metal_color)
    rotate([90, 0, 0])
    difference() {
        cylinder(h=ring_band_width, r=ring_inner_radius + ring_band_thickness, center=true, $fn=100);
        cylinder(h=ring_band_width + 1, r=ring_inner_radius, center=true, $fn=100);
    }
}

module central_stone() {
    translate([0, 0, ring_inner_radius + ring_band_thickness])
    color(diamond_color)
    sphere(r=central_diamond_radius, $fn=40);
}

module prongs() {
    for (i = [0 : prong_count - 1]) {
        rotate([0, 0, i * (360 / prong_count)])
        translate([central_diamond_radius * 0.9, 0, ring_inner_radius + ring_band_thickness - 1])
        color(metal_color)
        cylinder(r=prong_radius, h=prong_height, $fn=20);
    }
}

module diamond_row(offset_z, radius_offset, stone_size) {
    num_stones = floor(2 * PI * (ring_inner_radius + radius_offset) / (stone_size * 2.2));
    for (i = [0 : num_stones - 1]) {
        rotate([0, 0, i * (360 / num_stones)])
        translate([ring_inner_radius + radius_offset, 0, offset_z])
        color(diamond_color)
        sphere(r=stone_size, $fn=20);
    }
}

module milgrain_row(offset_z, radius_offset) {
    num_beads = floor(2 * PI * (ring_inner_radius + radius_offset) / (milgrain_radius * 2.5));
    for (i = [0 : num_beads - 1]) {
        rotate([0, 0, i * (360 / num_beads)])
        translate([ring_inner_radius + radius_offset, 0, offset_z])
        color(milgrain_color)
        sphere(r=milgrain_radius, $fn=12);
    }
}

union() {
    ring_base();
    central_stone();
    prongs();
    
    // Top Band Decorations
    // Center Row
    diamond_row(0, ring_band_thickness * 0.8, small_diamond_radius);
    
    // Outer Rows
    diamond_row(ring_band_width * 0.2, ring_band_thickness * 0.8, small_diamond_radius);
    diamond_row(-ring_band_width * 0.2, ring_band_thickness * 0.8, small_diamond_radius);
    
    // Milgrain Borders
    milgrain_row(ring_band_width * 0.3, ring_band_thickness * 0.9);
    milgrain_row(-ring_band_width * 0.3, ring_band_thickness * 0.9);
    milgrain_row(ring_band_width * 0.1, ring_band_thickness * 0.7);
    milgrain_row(-ring_band_width * 0.1, ring_band_thickness * 0.7);
}