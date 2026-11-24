# Agent Pack changelog

## 1.0 - first public release

First published version. The Agent Pack was rebuilt around an autonomous pipeline and the whole release moved to CC BY-NC-SA 4.0.

- **New agent.** `agent/agent.py` measures a case, fits the split outline, renders the Human Kit's own SCAD modules, splits the case and cuts the strap housing, then verifies its own output. Standard-library Python plus OpenSCAD. On the reference case it runs in about a second and produces a clean two-part split.
- **Placement is a decision, not a default.** The housing is never centred: the agent scans the back panel for through-openings (the camera cluster), offsets the housing into the clear band, faces the spring end at the camera end of the phone, and refuses to cut when the clearance rule cannot be met. `agent/README.md` and `AGENTS.md` document the procedure and the order of concessions when a case is too tight.
- **Strap narrowed for the split-backplate route.** Band 19.60 → 16.60 mm, ears back up to 6.40 mm, ear centres 21.80 mm, tracks 22.60 mm at 7.20 mm wide. The ear width is the maximum that keeps a 0.80 mm lateral clearance in the track while the 33.2 mm housing still clears the camera cutout (2.14 mm) and the interlock band (2.42 mm). Detent nose depth 1.25 → 1.55 mm keeps engagement at 0.75 mm.
- **Placement accounts for the interlock.** The clear zone is the backplate inset by `joint_inset (3.2) + margin (2.0)`, not just the margin. The outer 3.2 mm of a split backplate is the TPU tongue's retaining rail.
- **Analytic housing module regenerated.** `modules/build_agentsafe_housing.py` mirrors the strap parameters inline; its self-test probes are now derived from those constants instead of hard-coded X values that silently pointed at empty space once the strap was narrowed.
- **Reference case added.** `reference/case/s25UltraTHIKnoCutout.3mf` by Alex (@alexm2901), CC BY-NC-SA 4.0, with attribution. The generated example in `examples/s25-ultra-thik/` ships with it.
- **Licence changed to CC BY-NC-SA 4.0.** The reference case is NC, so this pack - and therefore the release as a whole - is non-commercial.

The strap artefacts, the interlock reasoning, the analytic housing module and the split-tool reference copy are original work and remain.

## v2.3 - internal draft (pre-release)

### Human workflow correction

The reusable split helper is now a true parametric five-segment negative-volume cutter that creates the vertical-capture backplate/perimeter joint. It is no longer described as a thin initial cut. A reference copy is included at `reference/human_kit_case_split_tools/`.

The cross-section sequence at the locking band is `RIGID CORE | TPU TONGUE | RIGID RETAINING RAIL | TPU OUTER PERIMETER`. The TPU tongue joins the outer frame below the rail; the rigid rail joins the backplate above it. Vertical opposing faces resist horizontal separation and horizontal shoulders capture the tongue vertically.

### Usage

Set `split_boundary_width`, `split_boundary_height`, `split_corner_chamfer` and `backplate_thickness` in `perimeter_split_negative.scad`. Render `output_mode="all"` and subtract it from the donor case in a Boolean-capable CAD/mesh tool. Extract the two components and inspect the actual profile at all straight edges and chamfer corners.

The helper is a generic chamfered-rectangle profile generator. It does not inspect donor geometry, detect keep-outs or automatically relieve features. A case-specific placement/clearance review and Boolean validation remain mandatory. The simple slab smoke test is not a phone-case validation.

### Unchanged canonical design

The accepted S25 Ultra three-piece assembly, its geometry and the three distinct spring-gap variants are unchanged. The S25-specific scripts remain worked examples rather than universal case converters.
