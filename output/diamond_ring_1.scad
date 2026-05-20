$fn = 128;

ring_outer_diameter = 22;
central_stone_diameter = ring_outer_diameter * 0.36;
band_height = ring_outer_diameter * 0.25;
prong_height = ring_outer_diameter * 0.12;
bead_diameter = ring_outer_diameter * 0.02;
side_stone_diameter = ring_outer_diameter * 0.05;
notch_size = ring_outer_diameter * 0.03;

bead_count = 60;
side_stone_count = 15;
notch_count = 12;

ring_color = "#C0C0C0";
stone_color = "#E0FFFF";

ring_radius = ring_outer_diameter / 2;
band_cross_section_radius = band_height / 2;
major_radius = ring_radius - band_cross_section_radius;

difference() {
    union() {
        // 1. Primary Body
        color(ring_color)
        rotate_extrude()
            translate([major_radius, 0, 0])
            circle(r = band_cross_section_radius);

        // 2. Secondary Components - Central Stone
        color(stone_color)
        translate([0, 0, major_radius + band_cross_section_radius])
        sphere(d = central_stone_diameter);

        // 2. Secondary Components - Prongs
        color(ring_color)
        for (i = [0 : 3]) {
            rotate([0, 0, i * 90])
            translate([central_stone_diameter / 2.2, 0, major_radius + band_cross_section_radius - 1])
            cylinder(h = prong_height, r = bead_diameter);
        }

        // 3. Repeating Details - Side Stones
        color(stone_color)
        for (i = [0 : side_stone_count - 1]) {
            rotate([0, 0, i * (180 / side_stone_count)])
            rotate([0, 0, 0])
            translate([major_radius + band_cross_section_radius * 0.5, 0, band_cross_section_radius])
            sphere(d = side_stone_diameter);
            
            rotate([0, 0, i * (180 / side_stone_count)])
            translate([major_radius + band_cross_section_radius * 0.8, 0, band_cross_section_radius])
            sphere(d = side_stone_diameter);
        }

        // 3. Repeating Details - Beads
        color(ring_color)
        for (i = [0 : bead_count - 1]) {
            rotate([0, 0, i * 360 / bead_count])
            translate([ring_radius, 0, band_cross_section_radius])
            sphere(d = bead_diameter);
            
            rotate([0, 0, i * 360 / bead_count])
            translate([ring_radius, 0, -band_cross_section_radius])
            sphere(d = bead_diameter);
        }
    }

    // 4. Boolean Ops - Inner Notches
    for (i = [0 : notch_count - 1]) {
        rotate([0, 0, i * 360 / notch_count])
        translate([major_radius - band_cross_section_radius, 0, 0])
        rotate([0, 90, 0])
        cylinder(h = notch_size, r1 = notch_size, r2 = 0, $fn = 3);
    }
}