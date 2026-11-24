/*
  NEGATIVE VOLUME for a rigid phone-case back panel.

  Subtract this shape from the PHONE/INNER side of a rigid rear panel. It creates:
    - a through-window for the visible TPU strap band;
    - two phone-side-open ear tracks and the fixed-end ear sockets;
    - the spring relief pockets and spring_air_gap clearance below each spring beam.

  The spring beams themselves are NOT removed: the difference() at the end
  preserves their material, so they remain attached at their end bridges.

  IMPORTANT SLICER NOTE:
  The shared parameter file defaults spring_air_gap to 0.20 mm. The project owner
  verified this value in their 0.20 mm layer / 0.6 mm nozzle slicer workflow after
  regenerating the negative-volume STL. Automatic variable layer height does not
  inspect features that exist only in a negative modifier, so do not rely on it to
  create a layer boundary in this gap. Inspect the generated bridge paths. Increase
  the parameter and regenerate the STL if your printer/material/profile fuses the
  beam to the floor. A 0.40 mm setting is a more conservative two-layer option.

  The phone closes the tracks after insertion. Do not add a roof on the phone side.
*/
include <strap_system_parameters.scad>;

$fn = 48;

module rounded_rect_2d(w,h,r) {
    rr = min(r,min(w,h)/2-0.01);
    offset(r=rr) square([w-2*rr,h-2*rr],center=true);
}

module rounded_box_at(cx,cy,w,h,z0,z1,r) {
    translate([cx,cy,z0]) linear_extrude(height=z1-z0)
        rounded_rect_2d(w,h,r);
}

module box_at(cx,cy,w,h,z0,z1) {
    translate([cx-w/2,cy-h/2,z0]) cube([w,h,z1-z0],center=false);
}

module central_strap_window() {
    // Slightly larger than the strap band; through-cut plus a small vertical overrun.
    rounded_box_at(0,strap_length/2,strap_window_width,strap_window_length,
                   -0.20,backplate_thickness+negative_cut_overrun,
                   strap_window_corner_radius);
}

module fixed_ear_sockets() {
    for (side=[-1,1])
        box_at(side*track_center_spacing/2,
               (track_fixed_socket_y0+track_fixed_socket_y1)/2,
               track_width,
               track_fixed_socket_y1-track_fixed_socket_y0,
               track_floor_thickness,backplate_thickness+negative_cut_overrun);
}

module moving_ear_tracks() {
    for (side=[-1,1])
        box_at(side*track_center_spacing/2,
               (track_y_min+track_y_max)/2,
               track_width,track_y_max-track_y_min,
               track_floor_thickness,backplate_thickness+negative_cut_overrun);
}

module spring_relief_cavities() {
    for (side=[-1,1]) {
        // Outer-side cavity beside spring body. End bridges remain for anchoring.
        box_at(side*(track_outer_x+spring_body_width+spring_relief_width/2),
               spring_detent_y,
               spring_relief_width,2*spring_relief_half_length,
               track_floor_thickness,backplate_thickness+negative_cut_overrun);
        // spring_air_gap separation under the moving beam span. The spring begins at
        // track_floor_thickness + spring_air_gap and does not touch the floor.
        box_at(side*(track_outer_x+spring_body_width/2),
               spring_detent_y,
               spring_body_width,2*spring_relief_half_length,
               track_floor_thickness,track_floor_thickness+spring_air_gap);
    }
}

module left_spring_profile_2d() {
    y0=spring_detent_y-spring_beam_half_length;
    y1=spring_detent_y+spring_beam_half_length;
    n0=spring_detent_y-spring_nose_half_length;
    n1=spring_detent_y+spring_nose_half_length;
    boundary=-track_outer_x;
    outer=boundary-spring_body_width;
    pts = concat(
        [[outer,y0],[boundary,y0],[boundary,n0]],
        [for(i=[0:spring_nose_samples]) let(y=n0+(n1-n0)*i/spring_nose_samples)
            [boundary+strap_detent_nose_depth*pow(cos(90*(y-spring_detent_y)/spring_nose_half_length),2),y]],
        [[boundary,y1],[outer,y1]]
    );
    polygon(pts);
}

module spring_keepout_material() {
    // Protect spring material from the union of negative cavities. The cosine
    // nose is the only part protruding into the track path.
    translate([0,0,track_floor_thickness+spring_air_gap])
        linear_extrude(height=3.15-(track_floor_thickness+spring_air_gap)) {
            left_spring_profile_2d();
            mirror([1,0,0]) left_spring_profile_2d();
        }
}

module strap_housing_negative() {
    difference() {
        union() {
            central_strap_window();
            fixed_ear_sockets();
            moving_ear_tracks();
            spring_relief_cavities();
        }
        spring_keepout_material();
    }
}

strap_housing_negative();
