/*
  Shared dimensions for the sliding strap and its rigid-case negative modifier.
  Units: millimetres.

  IMPORTANT COUPLED DIMENSIONS:
  - strap_length, strap_moving_ear_length, strap_travel and track_hard_stop_overtravel
    define both the moving ear position and the lower end of its guide track.
  - strap_stow_notch_offset and strap_travel define the deployed detent/spring position.
  - track_center_spacing, track_width and ear_width define the lateral fit.
  Change these here once. Both strap_parametric.scad and
  strap_housing_negative.scad include this file.

  Reference dimensions reproduce the physically tested S25 Ultra strap geometry.
  For another phone, adapt these dimensions to its usable rear panel.
*/

// Main flexible band (print bed is z=0; band extends to +Z)
strap_length = 143.50;
strap_band_width = 16.60;
strap_thickness = 2.60;
strap_corner_radius = 2.00;

// Ears (two per end, one in each side track)
// The ear must overlap the band to stay attached, so the ear centres follow the
// band half-width: with a 16.60 band (half 8.30) and a 6.40 ear, the inner edge
// sits at 7.70, giving 0.60 mm of overlap.
strap_ear_width = 6.40;
strap_ear_center_spacing = 21.80;  // centres at +/-10.90 from band centre
strap_ear_thickness = 1.85;
strap_fixed_ear_length = 10.00;
strap_moving_ear_length = 15.80;
strap_ear_corner_radius = 1.20;
strap_fixed_socket_clearance = 0.35;

// Motion and locking: these values MUST stay coupled between strap and housing.
strap_travel = 33.00;
track_hard_stop_overtravel = 0.20;
strap_stow_notch_offset = 2.80;  // notch centre behind moving end in stowed position
strap_notch_length = 4.60;
strap_notch_corner_radius = 0.65;
strap_detent_lateral_clearance = 0.25;
strap_detent_nose_depth = 1.55;

// Flexure grooves in the TPU strap. Grooves are only across the flexible span.
strap_groove_pitch = 3.15;
// Groove count is derived from the available flexible span so changed strap lengths
// keep the same nominal pitch without crossing into either ear transition.
strap_groove_mouth = 1.80;
strap_groove_depth = 1.45;
strap_groove_cut_below_face = 0.15;
strap_groove_end_transition = 4.40;

// Negative modifier geometry for the rigid case.
// The lateral clearance is the gap between each side of the ear and its track.
// 0.80 mm = two 0.40 mm extrusion widths, so a slicer leaves it as a real void
// instead of filling a sub-line-width gap. Track spacing and width are derived
// from the ear so this can never drift out of step with the strap.
strap_track_lateral_clearance = 0.80;
track_center_spacing = strap_ear_center_spacing + strap_track_lateral_clearance;
track_width = strap_ear_width + strap_track_lateral_clearance;
track_floor_thickness = 0.60;
backplate_thickness = 2.65;
negative_cut_overrun = 0.55; // extend cut past top surface for robust boolean subtraction
strap_window_width = 17.20;
strap_window_end_clearance = 1.10;
strap_window_corner_radius = 2.50;

// Vertical clearance below the spring beam. The 0.20 mm default was tested by
// the project owner with a 0.20 mm layer profile and a 0.6 mm nozzle when the
// housing is applied as a slicer negative-volume modifier. Other printers and
// materials may need a larger value; inspect the actual bridge toolpath.
spring_air_gap = 0.20;
spring_body_width = 1.00;
spring_relief_width = 0.70;
spring_beam_half_length = 10.00;
spring_relief_half_length = 9.00; // leaves 1 mm anchored bridge at either end
spring_nose_half_length = 2.00;
spring_nose_samples = 24;

// Derived shared positions. Do not duplicate these formulas in a second file.
track_outer_x = track_center_spacing/2 + track_width/2;
track_inner_x = track_center_spacing/2 - track_width/2;
strap_band_half_width = strap_band_width/2;
strap_ear_center_x = strap_ear_center_spacing/2;

strap_fixed_ear_y0 = 0;
strap_fixed_ear_y1 = strap_fixed_ear_length;
strap_moving_ear_y0_stowed = strap_length - strap_moving_ear_length;
strap_moving_ear_y1_stowed = strap_length;

// Track range includes the entire moving ear at both end positions.
track_y_min = strap_length - strap_moving_ear_length - strap_travel - track_hard_stop_overtravel;
track_y_max = strap_length + 0.35;

// Detent engages after 33 mm travel; track hard stop is 0.20 mm farther on.
strap_notch_y_stowed = strap_length - strap_stow_notch_offset;
spring_detent_y = strap_notch_y_stowed - strap_travel;

// Flex grooves leave an ungrooved transition next to both ear groups.
strap_groove_min_center_y = strap_fixed_ear_length + strap_groove_end_transition + strap_groove_mouth/2;
strap_groove_max_center_y = strap_moving_ear_y0_stowed - strap_groove_end_transition - strap_groove_mouth/2;
strap_groove_count = max(2, floor((strap_groove_max_center_y-strap_groove_min_center_y)/strap_groove_pitch)+1);
// Centre the count * pitch array within the allowed bending span.
strap_groove_first_y = (strap_groove_min_center_y+strap_groove_max_center_y-(strap_groove_count-1)*strap_groove_pitch)/2;
strap_groove_last_y = strap_groove_first_y + (strap_groove_count-1)*strap_groove_pitch;

// Negative modifier apertures / sockets.
strap_window_length = strap_length + 2*strap_window_end_clearance;
strap_window_y0 = -strap_window_end_clearance;
strap_window_y1 = strap_length + strap_window_end_clearance;
track_fixed_socket_y0 = strap_fixed_ear_y0 - strap_fixed_socket_clearance;
track_fixed_socket_y1 = strap_fixed_ear_y1 + strap_fixed_socket_clearance;
