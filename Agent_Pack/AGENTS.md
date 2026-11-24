# Instructions for CAD agents

Read `README.md`, `AGENTS.md`, `AGENT_HANDOFF.md`, `agent/README.md`, `AUDIT_REPORT.md` and `CHANGELOG.md`; consult older changelogs only for historical context. The split-and-housing workflow is automated in `agent/agent.py`; `AGENT_HANDOFF.md` records the accepted design's dimensions and the reasoning that the agent's defaults encode.

## Placement protocol — do not skip this

The script measures and booleans. **Where the strap goes is your decision**, and
it is the one that produces unusable parts when skipped.

1. **Find every through-opening in the back panel.** `agent.py` reports them as
   `opening 0..n`. The largest is the camera cluster, 30-35 mm wide and 55-60 mm
   tall, hard against one long edge.
2. **The camera cluster marks the top of the phone.** That end is where the
   user's head is when they hold it.
3. **Never centre the housing.** It is a negative volume: overlapping the camera
   opening produces a part that cannot be assembled, while the boolean still
   succeeds and looks clean. Offset into the clear band beside the cluster.
4. **Springs go to the camera end.** The spring/detent beam sits near the moving
   end of the strap (~75 % of its length), so the housing is normally rotated
   180° from the case's own axes. Wrong way round = detents engage at the wrong
   end of travel, and it is not obvious until the strap is in.
5. **Keep 2.0 mm clearance** to every opening and to the backplate edge. That
   gap is the load-bearing bridge between two holes; under ~1.2 mm in rigid
   filament it is where the part breaks.
6. **If it will not fit, narrow the strap.** Reduce `strap_band_width` and
   `track_center_spacing` in `strap_system_parameters.scad` and regenerate the
   strap to match. Only then consider lowering `--clearance`, and record why.
7. **A refusal is information.** When `agent.py` exits with "no placement clears
   the case openings", it is telling you the strap must shrink or the clearance
   must be justified. Do not pass `--housing-x` to push past it.

After cutting, verify: one part, the strap window clear of every opening, and
the report's clearance numbers non-zero.

## Critical geometry

The accepted flexible-case interface uses the radial material sequence `rigid core | TPU tongue | rigid retaining rail | TPU outer perimeter`. The TPU tongue connects to the TPU frame below the locking band; the rigid rail connects to the backplate above it. Opposing vertical faces resist horizontal separation, and overlapping horizontal shoulders capture the tongue against vertical lift/drop. Inspect actual mesh cross-sections at straight and chamfered regions; a correct top view alone proves nothing.

The strap is TPU. The backplate/housing and its spring detents must be rigid. A full-TPU case was physically tested and failed to retain the slider securely.

## Spring-gap variants - three different models; do not conflate them

- **Canonical accepted S25 integrated backplate: 0.10 mm.** This is an already-integrated gap in the S25-specific final backplate. It was physically tested as part of the accepted three-piece case. It is not a generic modifier negative.
- **Human Kit slicer modifier: 0.20 mm.** The reusable SCAD and shipped negative STL use this value. The project owner confirmed it on a 0.20 mm layer / 0.6 mm nozzle profile after regenerating the negative STL. Automatic variable layer height may ignore modifier-only geometry; set the value in SCAD and inspect the bridge paths.
- **Agent Pack analytic CAD-boolean module: 0.40 mm.** This is a separate B-rep-safe negative with deliberate non-coincident overlaps. It is a more conservative two-layer option for a 0.20 mm layer profile, but leaves less beam height and may soften the detent.

These values are tied to different artefacts/workflows, not a universal layer-height law. Do not copy one gap value into another model without regenerating and validating it. For changed materials/profiles, inspect the bridge paths and make a test print.

`modules/build_agentsafe_housing.py` manually mirrors the Human Kit dimensions; it does not parse the SCAD file. A read-only snapshot is included at `reference/human_kit_parameters/strap_system_parameters.scad`. If dimensions change, update both and validate.

## Generic profiled split cutter

A reference copy of the reusable Human Kit split tool is at `reference/human_kit_case_split_tools/`. It generates the complete five-segment vertical-capture negative volume from the measured backplate width, height, corner chamfer and thickness. It is not a straight slit. Use it to define the cut topology, then Boolean-subtract it from the donor case and inspect the actual resulting sections. It does not detect case-specific keep-outs.

## Adaptation rules

For a new case, inspect/repair the source STL, confirm units/orientation, measure every wall and keep-out, and rework the coordinates. The supplied S25 scripts are references, not universal converters. The first split of an arbitrary case into rear panel and full-height perimeter is case-specific and not automated.

The historical donor/rigid-retrofit variants with their 0.10 mm integrated spring gap are not shipped in this public release: their geometry is derived from a third-party case model. Do not recreate them as generic retrofit outputs without rebuilding and rechecking the spring geometry. The canonical physically accepted S25 three-piece example remains valid as that specific tested design.

## Validation requirements

- Re-import STEP files; confirm valid solids and expected solid count.
- Confirm STL meshes are watertight and connected (`prusa-slicer --info` where available).
- Check intersections and actual cross-sections at straight edges and corners.
- Probe spring gaps and inspect bridge toolpaths.
- Confirm the track floor and outer skin survive.
- Test fit, travel, detent, hard stop and physical retention before claiming compatibility.

