/*
  PARAMETRIC VERTICAL-CAPTURE PERIMETER SPLIT CUTTER
  =================================================

  PURPOSE
  -------
  Generate the complete 3D negative-volume cutter that splits a one-piece
  flexible phone case into a rigid central backplate and a TPU perimeter.
  This is NOT a straight vertical slit. The cutter follows the same stepped
  vertical-capture profile as the accepted S25 Ultra three-piece reference.

  In a section through a straight edge, the cutter path follows five segments:
    1. Inner vertical wall, from the exterior back to the upper step.
    2. Upper horizontal shoulder, moving outward.
    3. Middle vertical wall, descending to the lower step.
    4. Lower horizontal shoulder, moving outward again.
    5. Outer vertical wall, rising to the phone-facing backplate surface.

  After subtracting the cutter, the middle-height material sequence is:
    RIGID CORE | TPU TONGUE | RIGID RETAINING RAIL | TPU OUTER PERIMETER

  The TPU tongue remains connected to the outer TPU perimeter below the rail.
  The rigid retaining rail remains connected to the backplate above the tongue.
  The opposed vertical faces resist horizontal separation; the horizontal
  shoulders provide vertical capture. The resulting cut should separate the
  host case into two connected solids, provided no uncut bridges remain.

  MAIN INPUTS (millimetres)
  ------------------------
    split_boundary_width   - width of the visible outer backplate outline
    split_boundary_height  - height of that outline
    split_corner_chamfer   - chamfer leg length along each straight edge
    backplate_thickness    - thickness at the backplate/perimeter joint

  ADVANCED PROFILE PARAMETERS
  ---------------------------
  The default insets, step fractions and clearances reproduce the proportions
  of the accepted S25 Ultra joint. They are starting values, not universal
  dimensions. Inspect the wall thickness, camera/port/button clearances and
  actual section on every new case.

  OUTPUT MODES
  ------------
    "all"      - complete one-piece profiled cutter ring (recommended)
    "straight" - four straight-edge cutter pieces
    "corners"  - four chamfer-corner cutter pieces

  Use either "all", OR use "straight" + "corners" once each. Do not subtract
  the full cutter and its component exports together.
*/

// -------------------- MAIN CASE INPUTS --------------------
split_boundary_width  = 80.00;  // mm: outer width of visible backplate outline
split_boundary_height = 160.00; // mm: outer height of visible backplate outline
split_corner_chamfer  = 6.00;   // mm: chamfer leg measured along each straight edge
backplate_thickness   = 2.65;   // mm: Z thickness at the backplate/perimeter joint

// -------------------- PROFILE / FIT PARAMETERS --------------------
// Insets are measured inward from the visible backplate outline.
// Keep INNER > MIDDLE > OUTER. Defaults reproduce the accepted S25 profile.
joint_inner_inset  = 3.20;  // rigid core / TPU tongue boundary
joint_middle_inset = 1.65;  // TPU tongue / rigid retaining rail boundary
joint_outer_inset  = 0.35;  // rigid retaining rail / TPU outer frame boundary

// Step heights as fractions of backplate_thickness, from the exterior rear face.
// For T=2.65 mm these give 0.848 mm and 1.855 mm, matching the S25 reference.
joint_lower_step_fraction = 0.32;
joint_upper_step_fraction = 0.70;

// Clearances between the resulting mating surfaces.
joint_radial_clearance   = 0.15; // mm: total width of each vertical-face cut
joint_vertical_clearance = 0.08; // mm: total height of each horizontal-face cut
joint_boolean_overlap    = 0.03; // mm: local overlap only where cutter segments meet
cut_end_overrun           = 0.20; // mm: extends cutter beyond backplate top/bottom

// Placement: centre of the backplate outline and exterior-back Z datum.
split_center_x = 0.00;
split_center_y = 0.00;
base_z         = 0.00;

output_mode = "all"; // "all", "straight" or "corners"
$fn = 32;

// -------------------- DERIVED VALUES --------------------
step_lower_z = base_z + backplate_thickness*joint_lower_step_fraction;
step_upper_z = base_z + backplate_thickness*joint_upper_step_fraction;
profile_top_z = base_z + backplate_thickness;
max_inset = joint_inner_inset;
min_inset = joint_outer_inset;

// -------------------- INPUT VALIDATION --------------------
assert(split_boundary_width > 0 && split_boundary_height > 0,
       "Backplate width and height must be positive millimetre values.");
assert(split_corner_chamfer >= 0,
       "split_corner_chamfer cannot be negative.");
assert(split_boundary_width > 2*(max_inset + split_corner_chamfer + 1),
       "Backplate width too small for selected insets and chamfer.");
assert(split_boundary_height > 2*(max_inset + split_corner_chamfer + 1),
       "Backplate height too small for selected insets and chamfer.");
assert(joint_inner_inset > joint_middle_inset && joint_middle_inset > joint_outer_inset,
       "Insets must satisfy inner > middle > outer.");
assert(joint_outer_inset >= 0,
       "joint_outer_inset cannot be negative.");
assert(joint_lower_step_fraction > 0 && joint_upper_step_fraction < 1 &&
       joint_lower_step_fraction < joint_upper_step_fraction,
       "Step fractions must satisfy 0 < lower < upper < 1.");
assert(joint_radial_clearance > 0 && joint_vertical_clearance > 0,
       "Joint clearances must be positive.");
assert(joint_boolean_overlap >= 0 && cut_end_overrun > 0,
       "Boolean overlap must be non-negative and cut_end_overrun must be positive.");
assert(joint_radial_clearance < 2*min(joint_inner_inset-joint_middle_inset,
                                      joint_middle_inset-joint_outer_inset),
       "Radial clearance is too large for the selected hook widths.");
assert(backplate_thickness > 1.5,
       "Backplate thickness is too small for this two-step profile.");

// -------------------- 2D OUTLINE HELPERS --------------------
// inset=0 is the visible outer outline; positive inset moves toward the centre.
module chamfered_outline(inset=0) {
    w = split_boundary_width - 2*inset;
    h = split_boundary_height - 2*inset;
    c = min(split_corner_chamfer, min(w,h)/2 - 0.01);
    polygon([
        [-w/2+c, -h/2], [ w/2-c, -h/2],
        [ w/2, -h/2+c], [ w/2,  h/2-c],
        [ w/2-c, h/2], [-w/2+c, h/2],
        [-w/2, h/2-c], [-w/2, -h/2+c]
    ]);
}

// Ring-shaped channel around one contour: a vertical profile face.
module vertical_profile_channel(inset, z0, z1) {
    translate([0,0,z0])
        linear_extrude(height=max(0.001,z1-z0), convexity=6)
            difference() {
                offset(delta=joint_radial_clearance/2)
                    chamfered_outline(inset);
                offset(delta=-joint_radial_clearance/2)
                    chamfered_outline(inset);
            }
}

// Horizontal shoulder channel between two nested contours.
// outer_inset is smaller because that contour lies farther toward the case edge.
module horizontal_profile_channel(inner_inset, outer_inset, zcenter) {
    translate([0,0,zcenter-joint_vertical_clearance/2])
        linear_extrude(height=joint_vertical_clearance, convexity=6)
            difference() {
                offset(delta=joint_boolean_overlap)
                    chamfered_outline(outer_inset);
                offset(delta=-joint_boolean_overlap)
                    chamfered_outline(inner_inset);
            }
}

// Complete five-segment profile, carried around the chamfered-rectangle plan path.
module complete_profile_cutter() {
    union() {
        // 1. Inner wall: exterior-back face up to the upper shoulder.
        vertical_profile_channel(
            joint_inner_inset,
            base_z-cut_end_overrun,
            step_upper_z+joint_vertical_clearance/2+joint_boolean_overlap
        );

        // 2. Upper shoulder: inner contour outward to the middle contour.
        horizontal_profile_channel(
            joint_inner_inset, joint_middle_inset, step_upper_z
        );

        // 3. Middle vertical wall: between upper and lower shoulders.
        vertical_profile_channel(
            joint_middle_inset,
            step_lower_z-joint_vertical_clearance/2-joint_boolean_overlap,
            step_upper_z+joint_vertical_clearance/2+joint_boolean_overlap
        );

        // 4. Lower shoulder: middle contour outward to the outer contour.
        horizontal_profile_channel(
            joint_middle_inset, joint_outer_inset, step_lower_z
        );

        // 5. Outer wall: lower shoulder up through the backplate top face.
        vertical_profile_channel(
            joint_outer_inset,
            step_lower_z-joint_vertical_clearance/2-joint_boolean_overlap,
            profile_top_z+cut_end_overrun
        );
    }
}

// Masks that separate long straight edge runs from the four corner/chamfer runs.
// The straight masks stop at the innermost contour's chamfer start. The remaining
// cutter volume is classified as the four corner pieces.
module straight_edge_mask_2d() {
    half_x = split_boundary_width/2 - split_corner_chamfer - max_inset - 0.02;
    half_y = split_boundary_height/2 - split_corner_chamfer - max_inset - 0.02;
    radial_span = max_inset-min_inset + joint_radial_clearance + 2*joint_boolean_overlap + 0.04;
    radial_mid = (max_inset+min_inset)/2;
    union() {
        translate([0, split_boundary_height/2-radial_mid, 0])
            square([2*half_x, radial_span], center=true);
        translate([0,-split_boundary_height/2+radial_mid, 0])
            square([2*half_x, radial_span], center=true);
        translate([ split_boundary_width/2-radial_mid, 0, 0])
            square([radial_span, 2*half_y], center=true);
        translate([-split_boundary_width/2+radial_mid, 0, 0])
            square([radial_span, 2*half_y], center=true);
    }
}

module straight_mask_3d() {
    translate([0,0,base_z-cut_end_overrun-0.01])
        linear_extrude(height=backplate_thickness+2*cut_end_overrun+0.02)
            straight_edge_mask_2d();
}

module selected_profile_cutter() {
    if (output_mode == "all") {
        complete_profile_cutter();
    } else if (output_mode == "straight") {
        intersection() {
            complete_profile_cutter();
            straight_mask_3d();
        }
    } else if (output_mode == "corners") {
        difference() {
            complete_profile_cutter();
            intersection() {
                complete_profile_cutter();
                straight_mask_3d();
            }
        }
    } else {
        assert(false, "output_mode must be all, straight or corners");
    }
}

translate([split_center_x,split_center_y,0])
    selected_profile_cutter();
