# Agent hand-off: modular phone case with captive sliding grip

**Version 1.0.** Read this file before modifying any CAD. The split-and-housing workflow is automated in `agent/agent.py`; this file records the accepted hand-built design's dimensions and the reasoning that the agent's defaults encode. Current changes are summarized in `CHANGELOG.md`, with validation scope in `AUDIT_REPORT.md`. Earlier v2.1 notes remain in `history/` as historical records.

## Accepted final state

The user has printed and assembled all three parts and reports that the strap/kickstand works exactly as intended: it supports the phone as a stand, does not twist, is comfortable to hold, and the TPU perimeter/backplate retention is secure enough to grab and gently wiggle the phone by the strap. Treat this as the final product. Do not redesign it without a concrete new failure report.

Parts:
1. `backplate.step/.stl` - rigid backplate with camera apertures, cosmetic hex window, phone-facing-open strap tracks, compliant detents and rigid half of the vertical-capture joint.
2. `perimeter.step/.stl` - TPU perimeter with full-height case walls and matching captive return/tongue.
3. `strap.step` and `strap_print_orientation.stl` - TPU band, four ears, detent notches and underside flex grooves.

The assembly STEP/STL is for inspection only; print the three parts separately.

## Agent-safe negative volume for CAD booleans

`modules/strap_housing_negative_agentsafe.step` is the housing negative to use whenever the housing will be subtracted in a CAD/B-rep kernel. `modules/build_agentsafe_housing.py` regenerates it and self-tests before writing. Its dimensions are manually mirrored from the Human Kit SCAD parameter file; they are not read from that file automatically. Keep them synchronized if the strap is edited.

Do **not** subtract the Human Kit `strap_housing_negative.stl` (available in the separate Human Kit or the complete bundle) in CAD. It is a fine slicer modifier but unsafe boolean input: three pairs of faces are exactly coincident around the spring (track wall / keep-out / spring body at x = +/- track_outer_x; air-gap top / keep-out bottom at the same z; relief wall / keep-out outer wall at +/- 17.80). A boolean against it intermittently returns zero-area sliver faces, `isValid() == False` and a non-manifold STL, and the STL-to-solid conversion is itself not reproducible. See `history/CHANGELOG_v2_1.md` (included in this Agent Pack) for the measurements. The included agent-safe STEP was independently re-opened as one valid solid in the v2 audit. The original v2 audit report records six successful repeated subtractions; the bundled builder itself performs a slab self-test before writing. Re-run the builder and validate the target case boolean in the actual CAD kernel before relying on a new output.

## Functional topology of the perimeter joint

At the locking band, moving radially from the centre of the rear panel toward the outside:

`RIGID BACKPLATE CORE | TPU TONGUE | RIGID RETAINING RAIL | TPU OUTER PERIMETER`

- The TPU tongue joins the outer TPU frame by a lower TPU bridge.
- The rigid retaining rail joins the rigid backplate core by an upper rigid bridge.
- Opposed vertical faces resist horizontal/radial separation.
- Horizontal shoulders capture the tongue against vertical lift/drop.
- The plan-view interface is a mostly regular chamfered rectangle, with local relief only for an existing grip-rail feature.

Do not replace this with a horizontal Z-only split, shallow wedge, thin non-returning tongue or friction-only bead. A flat split made the perimeter too easy to stretch; the wedge did not retain the backplate sufficiently.

## Strap and slider reference

- TPU band: 16.60 mm wide x 143.50 mm long x 2.60 mm thick before grooves.
- Four ears: 6.40 mm wide, 1.85 mm thick; fixed-end ear length 10.0 mm; moving-end ear length 15.8 mm. Ear centres at +/-10.90 mm; the tracks sit at +/-11.30 mm, 7.20 mm wide, for a 0.80 mm lateral clearance.
- Travel to detent: 33.0 mm; ear hard stop about 0.20 mm beyond engagement.
- Track floor: 0.60 mm.
- Spring beam underside floats above the track floor, anchored at both ends. The beam body is flush with the track wall; only its rounded nose protrudes into the ear path.
- **There are three distinct spring-gap settings.** The canonical S25 backplate has an integrated **0.10 mm** spring/floor relief; this exact S25 assembly was physically tested and accepted. The reusable Human Kit slicer-modifier SCAD/STL defaults to **0.20 mm**, which the project owner confirmed on a 0.20 mm layer / 0.6 mm nozzle profile after regenerating the modifier STL. The separate analytic CAD-boolean-safe module in `modules/` uses **0.40 mm** as a more conservative two-layer variant; it leaves less spring-beam height and may feel softer. Do not interchange these numbers between models or describe any as universal. Automatic variable layer height may ignore negative-volume modifier geometry, so set the actual gap in the SCAD/build geometry and inspect the toolpath.
- Slicer: confirm in preview that the beam's first layer bridges across the pocket and does not fuse to the floor. Use the material/profile's bridge speed, flow and cooling settings as a starting point; tune them from the actual toolpath and a small test print. Do not treat any one bridge-flow or fan value as universal.
- Strap has 35 underside transverse wedge grooves at 3.15 mm pitch, 1.80 mm mouth and 1.45 mm depth, leaving 1.15 mm continuous skin. Grooves only span the flexible band and do not reach the ears.
- The printed strap installs **mirrored across XY, then +2.60 mm in Z**. In its raw print orientation its ears sit 0.75 mm low and collide with the track floor. A rigid translation of the strap is not a valid deployed-state test - the real strap bends into a loop.

## Case adaptation workflows

### Arbitrary flexible case STL -> three-piece case

1. Inspect units, orientation, watertightness and shell topology. Establish exterior rear face as Z=0 and positive Z toward the phone cavity.
2. Identify the central rear-panel boundary, camera keep-outs, wall thickness, buttons, ports, rails and all exterior features.
3. Measure the intended backplate outline width, height, corner chamfer and thickness. Set those values in `reference/human_kit_case_split_tools/perimeter_split_negative.scad` and render the complete profiled cutter.
4. Subtract that five-segment cutter from the donor case in a boolean-capable CAD/mesh tool and extract the two components. Inspect the actual cut at straight edges and chamfer corners; manually relieve or reposition the profile wherever it conflicts with camera openings, side rails, buttons, ports or thin walls. The cutter creates the vertical-capture topology but does not find case-specific keep-outs.
5. Add phone-facing-open slider tracks and compliant detents to the rigid panel; the phone closes the tracks in use.
6. Use a common parameter source for strap and housing so travel, notch position and hard stop remain coupled.
7. Add the TPU strap, inspect actual mesh cross-sections, validate solids, components and intersections, then physically test.

### Two-piece case (no strap)

Use the case split and vertical-capture backplate/perimeter joint, but omit all tracks, springs and strap features. The optional starting geometry came from the donor case and is not shipped; generate an equivalent start from your own case export with the Human Kit cutter. It is a starting point, not a finished alternative final export.

### Existing rigid case retrofit

This is the simplest path: keep the rigid case whole, subtract the strap housing negative volume from its phone-facing rear panel, and use the TPU strap. Preserve adequate exterior skin and a suitable rigid material for repeated spring flexing.

Use `modules/strap_housing_negative_agentsafe.step`, not the Human Kit STL. It is generated in the strap datum the parameter file uses - exterior back at Z=0, X centred on the band, Y=0 at the fixed end - so for a case already built that way you only translate in X and Y.

Practical placement, learned on the S25 Ultra minimalist shell: find the rear panel's inner floor and its camera openings, then place the 33.2 x 145.7 mm footprint in the clear strip - never centred. On that case the inner floor spans x 54.25..131.85 and the camera openings begin at x 95.57, so the housing went to x 56.41..93.41, y 52.21..197.91 - translate (74.91, 53.31, 0). That places the strap 18.15 mm off the panel centreline, which agrees with the 18.25 mm offset of the reference donor backplate. Narrowing the strap from the original 37 mm housing (band 19.60 -> 16.60, ears 7.10 -> 6.40) is what made the split-backplate example fit: the wider housing put one spring relief pocket into the interlock band and the other within 1.5 mm of the camera opening.

A reference copy of the case-independent Human Kit profiled split tool is included at `reference/human_kit_case_split_tools/`. It generates the complete five-segment vertical-capture negative-volume cutter from backplate width, height, corner chamfer and thickness; it is not a straight slit. The original Human Kit remains the publication-oriented source of truth. The cutter does not inspect arbitrary donor meshes or detect camera/button/port/rail keep-outs.

## Non-negotiable design rules

- Do not let spring beams touch the track floor. The Human Kit slicer modifier uses 0.20 mm; the agent-safe analytic STEP module uses 0.40 mm. Select deliberately and test the actual bridge/profile.
- Do not cut spring relief through the exterior back skin; keep the track floor at 0.60 mm.
- Do not move the spring body into the ear path; only the nose engages.
- Do not extend flex grooves under ears/notches.
- Do not globally shrink the TPU perimeter until the vertical hook fit is rechecked.
- Do not treat the generic profiled split cutter as an automatic case-safe split: it creates the intended hook topology, but donor-case alignment, keep-outs, local reliefs and physical fit still require validation.
- Do not subtract a faceted STL housing from a B-rep case; use the analytic module.
- Do not recommend the full-TPU whole-case experiment; it failed physical retention testing.

## Validation requirements for modifications

Re-import exported STEP files and verify valid single solids. Verify individual STL meshes are watertight and connected (`prusa-slicer --info` must report `manifold = yes` and `number_of_parts = 1`). Check exact intersections between assembly parts and inspect actual exported cross-sections at straight edges and chamfered corners. Top view alone cannot prove the hook topology. Probe the air gap under each beam to confirm it is still open. Confirm the strap does not intersect the case when placed mirrored with a +2.60 mm Z offset. Physical assembly and retention testing remain necessary for any changed geometry.
