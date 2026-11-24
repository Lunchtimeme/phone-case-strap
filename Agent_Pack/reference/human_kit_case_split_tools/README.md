# Flexible-case split tool: profiled vertical-capture joint

`perimeter_split_negative.scad` now generates the **complete three-dimensional negative-volume cutter for the hooked backplate/perimeter interface**. It is not the old straight vertical slit.

The cutter follows the accepted S25-style five-segment cross-section all the way around a chamfered rectangle. Subtracting it from a suitable one-piece case creates the complementary vertical-capture geometry in the two resulting components.

## 1. What the profile does

At a straight edge, moving from the centre of the backplate toward the outside, the cutter follows this path:

1. Inner vertical cut from the exterior-back face to the upper step.
2. Upper horizontal shoulder cut, moving outward.
3. Middle vertical cut, descending to the lower step.
4. Lower horizontal shoulder cut, moving outward again.
5. Outer vertical cut, rising through the backplate thickness.

The resulting middle-height material sequence is:

`RIGID CORE | TPU TONGUE | RIGID RETAINING RAIL | TPU OUTER PERIMETER`

The TPU tongue remains connected to the perimeter below the rail. The rigid rail remains connected to the backplate above the tongue. Opposed vertical faces resist horizontal pull-apart forces; the horizontal shoulders resist lift/drop. This is the actual interlock profile, not a separate straight cut followed by a hand-designed hook.

See `../../Diagrams/profiled_split_section.png` for the cross-section and `../../Diagrams/profiled_split_plan.png` for the three nested chamfered contours.

## 2. Main inputs

Edit these at the top of `perimeter_split_negative.scad`:

| Parameter | Meaning |
|---|---|
| `split_boundary_width` | Width of the visible outer backplate outline, in mm. |
| `split_boundary_height` | Height of the visible outer backplate outline, in mm. |
| `split_corner_chamfer` | Chamfer leg length measured along each straight edge, in mm. |
| `backplate_thickness` | Thickness from the exterior-back plane to the phone-facing backplate surface at the joint, in mm. |

The outline dimensions describe the **backplate perimeter**, not the entire phone-case outside dimensions. `split_center_x`, `split_center_y` and `base_z` position the cutter in the donor case. `base_z` is normally the exterior-back face; +Z points into the phone cavity.

## 3. Interlock parameters

The defaults reproduce the proportions of the physically accepted S25 Ultra joint. They are starting values, not universal dimensions.

| Parameter | Default | Purpose |
|---|---:|---|
| `joint_inner_inset` | 3.20 mm | Core-to-TPU-tongue contour (C1), measured inward from the visible outline. |
| `joint_middle_inset` | 1.65 mm | Tongue-to-rigid-rail contour (C2). |
| `joint_outer_inset` | 0.35 mm | Rigid-rail-to-outer-TPU contour (C3). |
| `joint_lower_step_fraction` | 0.32 | Lower shoulder height as a fraction of backplate thickness. |
| `joint_upper_step_fraction` | 0.70 | Upper shoulder height as a fraction of backplate thickness. |
| `joint_radial_clearance` | 0.15 mm | Total gap width at vertical mating faces. |
| `joint_vertical_clearance` | 0.08 mm | Total gap height at horizontal shoulders. |
| `cut_end_overrun` | 0.20 mm | Extends cutter slightly beyond the top and bottom faces for a clean boolean. |

The default 3.20 / 1.65 / 0.35 mm insets produce a nominal 1.55 mm TPU tongue and 1.30 mm rigid rail before clearances. With 0.15 mm clearance on each side, the nominal remaining tongue width is about 1.25 mm and the rail about 1.00 mm.

The step heights scale with `backplate_thickness`. At 2.65 mm thickness, the lower and upper levels are approximately 0.85 mm and 1.86 mm. Keep the inset ordering `inner > middle > outer`; OpenSCAD assertions reject invalid basic dimensions.

**Before adapting to a new case:** check the actual perimeter wall thickness, camera apertures, ports, buttons, side rails and other internal features. The generic rectangular cutter cannot automatically detect these features. If the desired hook crosses a keep-out or a thin wall, change the outline/profile or make a local relief in CAD before printing. Do not simply use the default dimensions blindly.

## 4. Export the cutter

Open `perimeter_split_negative.scad` in OpenSCAD. Edit the four main inputs and, if needed, the advanced profile values. Press F6 (Render), then export STL.

Command-line examples, run from this folder:

```sh
# Recommended: one complete, connected cutter ring
openscad -D 'output_mode="all"' -o profiled_perimeter_cut_full_ring.stl perimeter_split_negative.scad

# Optional: separate straight runs and chamfer-corner runs
openscad -D 'output_mode="straight"' -o profiled_perimeter_cut_straight_edges.stl perimeter_split_negative.scad
openscad -D 'output_mode="corners"' -o profiled_perimeter_cut_chamfer_corners.stl perimeter_split_negative.scad
```

Use `all` by default. If your boolean tool handles the long straight runs and chamfer corners more reliably as separate operations, subtract `straight` and `corners` once each instead. Do **not** subtract the full cutter as well as its two component exports.

- `all` exports one watertight connected cutter ring.
- `straight` exports four separate straight-edge cutter pieces.
- `corners` exports four separate chamfer-corner cutter pieces.

The supplied STL files are generated examples for 80 x 160 mm, 6 mm chamfer, 2.65 mm thickness and the default S25-derived profile. Regenerate them after changing any parameter.

## 5. Apply it to a case and split the result

This is a boolean cutter, not a printable case part.

1. Import the original phone-case solid/mesh into a mesh or CAD program that can perform a true boolean difference.
2. Confirm the model uses millimetres and has the intended orientation. Set the exterior-back face to `base_z` and align the cutter centre (`split_center_x`, `split_center_y`) to the backplate outline.
3. Subtract `profiled_perimeter_cut_full_ring.stl` from the original case. If the program cannot use STL cutters reliably, use the straight/corner exports as separate boolean operations or convert/rebuild the cutter in the target CAD system.
4. Extract the resulting connected components. A simple closed test slab with the shipped default profile splits into exactly two watertight components; a real case may have extra bridges or local features that prevent a clean split and must be inspected.
5. Identify the central backplate and outer perimeter. The central component contains the rigid core and retaining rail; the outer component contains the TPU tongue and full-height perimeter.
6. Export the two components separately. Print the backplate in rigid material and the outer perimeter in TPU.
7. Inspect sections at all four straight edges and at all four chamfered corners. Confirm the tongue is captured behind the rail and the side walls/camera features remain intact. Clean supports from the hidden undercut on the rigid part.

Some slicers can use a negative-volume modifier to preview or slice a cut but cannot export the resulting two independent solids. In that case, perform the boolean difference in a mesh/CAD application before importing the two parts into the slicer.

## 6. Output modes and limitations

The generic cutter is a chamfered rectangle, not an automatic shape recognizer. It does not inspect an arbitrary STL, detect camera holes, infer the correct plate outline, or locally route around buttons/rails. You must measure and position it, then verify that its entire swept profile lies in solid material and leaves safe wall thickness.

The final S25 Ultra joint needed a local relief near an existing grip rail. The generic cutter cannot infer that feature; reproduce such a relief manually in CAD if your donor case has a similar obstruction.

The cutter's default clearances reproduce the accepted S25-style joint but may be too tight or loose for another printer, material or case. Make a small section/coupon test if uncertain. This is a geometry generator, not a guarantee of mechanical retention in every case.
