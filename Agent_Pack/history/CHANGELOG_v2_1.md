# v2.1 audit and compatibility corrections

This note records corrections made after using the v2 archive in both a slicer-first human workflow and an AI/CAD-agent workflow.

## 1. Spring gap: three distinct models, three distinct settings

The canonical accepted S25 integrated backplate has a 0.10 mm spring/floor relief. Its build notes identify this as part of the V4 integrated backplate, and the user physically tested the complete three-piece case. This value belongs to that specific integrated model; it is not the generic modifier default.

The Human Kit `strap_system_parameters.scad` sets `spring_air_gap = 0.20`, and the shipped `strap_housing_negative.stl` measures approximately 0.20 mm under the beam. The old SCAD comments, human guide and PDF incorrectly said 0.10 mm. Those descriptions are corrected. The project owner found that 0.20 mm worked in their 0.20 mm layer-height / 0.6 mm nozzle slicer workflow after regenerating the negative-volume STL. This is a known-good starting point for that setup, not a universal value.

The separate Agent Pack analytic STEP module uses 0.40 mm. This is a more conservative two-layer setting for a 0.20 mm layer profile. It lifts the free spring beam farther from the track floor and reduces its remaining height, so its detent feel can differ from the Human Kit 0.20 mm version and the integrated S25 backplate. Choose the correct artefact deliberately; these three numbers are not interchangeable.

## 2. Variable layer height clarification

The housing cavity is created by a slicer negative-volume modifier. Automatic variable layer height may be calculated from the host model without considering geometry that exists only in the modifier. Do not rely on variable layer height to establish a layer boundary in this gap. Change `spring_air_gap` in the SCAD parameter file, regenerate the negative STL and inspect the actual sliced bridge paths. If the bridge fuses or sags on a different profile, test a larger gap.

## 3. Slicer STL vs CAD B-rep boolean

The Human Kit negative STL is watertight and suitable for use as a slicer modifier, but it contains exactly coincident faces around the spring. Converting that mesh to a B-rep and using it in an OCCT boolean can create zero-area slivers or non-manifold results. The Agent Pack therefore includes an analytic STEP negative rebuilt with deliberate face offsets. Use the STEP file for CAD booleans; use the Human Kit STL for the slicer modifier route.

The supplied agent-safe builder duplicates the relevant strap/housing dimensions as constants rather than reading the SCAD file automatically. If the strap dimensions are changed, update the builder constants as well. Its 0.40 mm spring gap is an intentional separate setting.

## 4. Agent builder safety correction

`modules/build_agentsafe_housing.py` previously wrote output files before checking the validation results. The script is corrected so it stops before writing if the shape or slab self-test fails. Its geometry-generation parameters are still manually mirrored from the Human Kit; they are not live-linked.

## 5. Agent script portability

The hex-window build script now uses the adjacent included v4 STEP input instead of an absolute path from the original workstation. The optional PrusaSlicer 3MF helper now accepts a user-supplied source project path instead of failing on a missing workstation-specific file.

## 6. Runtime compatibility and onboarding

The Agent Pack documentation now separates the runtime requirements instead of implying that every Python script runs in one environment: OpenSCAD for SCAD modules; regular Python with CadQuery/OCP for most geometry builders; FreeCAD's bundled Python for scripts importing `FreeCAD`, `Part` or `Mesh`; and Blender's bundled Python for previews. The optional 3MF helper now accepts a donor project using `--source` or `PHONE_CASE_SOURCE_3MF`, validates the expected project entries and fails clearly for an absent or incompatible project.

## 7. Verification performed for this release

- OpenSCAD 2021.01 successfully compiled the Human Kit strap, housing and all three split-cutter modes.
- The regenerated 0.20 mm Human Kit housing mesh is watertight and one connected component; its bounds and volume match the shipped housing STL closely.
- The parametric strap export is watertight and one connected component.
- The full-ring split cutter is one watertight component. Straight-only and corner-only cutters each contain four watertight components, as designed.
- The Agent Pack analytic STEP housing re-opened as one valid solid using OCP 7.9.3.1; its STL is watertight and one connected component.
- The Agent Pack SHA256 manifest is regenerated and checked after documentation/script updates.

FreeCADCmd was not installed in the audit environment, so the modified FreeCAD builder itself was not executed again here. Its supplied STEP/STL outputs were independently checked as above. Physical fit and spring durability remain printer/material dependent.
