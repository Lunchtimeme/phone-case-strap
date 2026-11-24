/*
  Parametric TPU sliding strap / kickstand.
  Print material: TPU. Print orientation: grooved underside on build plate (z=0).
  Dimensions shared with strap_housing_negative.scad through strap_system_parameters.scad.

  This is an editable OpenSCAD reference for the original independently designed
  strap module. The adjacent tested STL/STEP are the reference print files.
*/
include <strap_system_parameters.scad>;

$fn = 48;

module rounded_rect_2d(w, h, r) {
    rr = min(r, min(w,h)/2 - 0.01);
    offset(r=rr) square([w-2*rr, h-2*rr], center=true);
}

module rounded_prism_at(cx, cy, w, h, z0, z1, r) {
    translate([cx,cy,z0]) linear_extrude(height=z1-z0) rounded_rect_2d(w,h,r);
}

module strap_band() {
    rounded_prism_at(0, strap_length/2, strap_band_width, strap_length,
                     0, strap_thickness, strap_corner_radius);
}

module strap_ears() {
    for (side = [-1,1]) {
        rounded_prism_at(side*strap_ear_center_x, strap_fixed_ear_length/2,
                         strap_ear_width, strap_fixed_ear_length,
                         0, strap_ear_thickness, strap_ear_corner_radius);
        rounded_prism_at(side*strap_ear_center_x,
                         strap_length-strap_moving_ear_length/2,
                         strap_ear_width, strap_moving_ear_length,
                         0, strap_ear_thickness, strap_ear_corner_radius);
    }
}

module moving_ear_detent_notches() {
    // Side-entry rounded recesses. Their Y position follows the same stow/travel
    // variables that define the spring position in the negative housing modifier.
    notch_x_center = track_outer_x - strap_detent_nose_depth/2 - strap_detent_lateral_clearance/2;
    notch_x_width = strap_detent_nose_depth + strap_detent_lateral_clearance + 0.10;
    for (side = [-1,1]) {
        rounded_prism_at(side*notch_x_center, strap_notch_y_stowed,
                         notch_x_width, strap_notch_length,
                         -0.05, strap_ear_thickness+0.05,
                         strap_notch_corner_radius);
    }
}

module one_flex_groove(yc) {
    half = strap_groove_mouth/2;
    // The 0.15 mm below-face overrun guarantees a clean opening at the print bed.
    // Map local profile (Y,Z) into global Y,Z and extrude across global X.
    multmatrix([[0,0,1,-(strap_band_width/2+0.10)],
                [1,0,0,0],
                [0,1,0,0],
                [0,0,0,1]])
        linear_extrude(height=strap_band_width+0.20, convexity=5)
            polygon([
                [yc-half, -strap_groove_cut_below_face],
                [yc+half, -strap_groove_cut_below_face],
                [yc+half, 0],
                [yc, strap_groove_depth],
                [yc-half, 0]
            ]);
}

module flex_grooves() {
    for (i=[0:strap_groove_count-1])
        one_flex_groove(strap_groove_first_y + i*strap_groove_pitch);
}

module strap_part() {
    difference() {
        union() {
            strap_band();
            strap_ears();
        }
        moving_ear_detent_notches();
        flex_grooves();
    }
}

strap_part();
