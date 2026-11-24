# Agent Pack changelog

## 1.0 - first public release

First published version. The Agent Pack was rebuilt around an autonomous pipeline and the whole release moved to CC BY-NC-SA 4.0.

- **New agent.** `agent/agent.py` measures a case, fits the split outline, renders the Human Kit's own SCAD modules, splits the case and cuts the strap housing, then verifies its own output. Standard-library Python plus OpenSCAD. On the reference case it runs in about a second and produces a clean two-part split.
- **Placement is a decision, not a default.** The housing is offset from the centreline — that offset is what gives the kickstand its two angles, and on a phone it also keeps the housing out of the camera cluster. The agent scans the back panel for through-openings, places the housing in the clear band, faces the spring end at the camera end of the phone, and refuses to cut when the clearance rule cannot be met. A panel with no openings is legitimate (not every device has a camera behind the case): the offset still applies, and `--camera-end` covers the orientation. `agent/README.md` documents the procedure and the order of concessions.
- **One parameter set, no drift.** `strap_ear_center_spacing` is now derived from band width, ear width and a named ear/band overlap; track spacing, track width and window width are derived from the ears. Narrowing the band moves the ears, the tracks and the window with it. The parameter file asserts a minimum 0.40 mm ear/band overlap and a minimum 0.40 mm track clearance, and OpenSCAD refuses to render otherwise.
- **The agent generates the strap too.** `08_strap.stl` is rendered from the same values passed to the housing, so a narrowed housing can no longer be paired with a strap cut to different numbers. `--track-center-spacing` is gone: it changed the housing without moving the ears, which is exactly how the two parts came apart.
- **Strap sized to the measured hole.** Band 16.60 mm, ears 6.00 mm, ear centres 21.40 mm, tracks 22.20 mm at 6.80 mm wide. The camera opening, measured on a 0.6 mm grid and expanded by half a step because samples sit inside the hole, is 33.6 x 58.2 mm — wider than the 1.0 mm grid first reported. That leaves a 32.4 mm housing clearing the opening by 2.14 mm and the interlock by 5.2 mm. Detent nose depth 1.55 mm keeps engagement at 0.75 mm.
- **Placement accounts for the interlock.** The clear zone is the backplate inset by `joint_inset (3.2) + margin (2.0)`, not just the margin. The outer 3.2 mm of a split backplate is the TPU tongue's retaining rail.
- **Analytic housing module reads the SCAD.** `modules/build_agentsafe_housing.py` no longer mirrors the dimensions in Python constants; it evaluates `strap_system_parameters.scad` through `modules/scad_params.py`, the same loader the tests use. Its self-test probes are derived from the resolved geometry, so they cannot point at empty space again once the strap changes. The 0.40 mm spring gap remains a deliberate local override of the Human Kit's 0.20 mm.
- **Fails closed.** Mesh repair only collapses non-manifold edges no longer than `--repair-tolerance` (0.05 mm default) and aborts above it, recording before/after bounds, volumes and maximum displacement. Every printable mesh is checked for watertightness, manifoldness, single-component and non-zero volume before it is written. The split must remove at least nothing and no more than the cutter holds; the housing cut must move material and not exceed the negative's own volume. A failed check exits non-zero instead of publishing the part.
- **Placement constraints are separate and complete.** Opening clearance and interlock clearance are tracked independently, on all four sides, including Y — previously the Y edges were compared against the ordinary 2.0 mm clearance rather than the 5.2 mm interlock margin. `--housing-x` bypasses the search but not the checks.
- **Opening detection is finer.** A 0.6 mm grid with a cluster and size filter replaces the 1.0 mm grid that needed six samples, and each bounding box is expanded by half a step so clearances are not optimistic.
- **Input parsing hardened.** 3MF is parsed as XML with namespace support, the model `unit` applied once and the build transform applied in model space; STL binary detection uses the declared triangle count and file length, so a binary file whose header starts with `solid` is read correctly. Truncated and malformed files are rejected with an explanation.
- **The pack is standalone.** `human_kit/` carries a byte-identical copy of the four SCAD files; a sibling `../Human_Kit` is used only if the bundle is absent, and a divergence between them is reported as a warning.
- **Tests and CI.** `tests/test_agent.py` covers the parsing, repair, placement and parameter-coupling failure modes above (18 tests, stdlib `unittest`), and `.github/workflows/tests.yml` runs them plus the manifest checks and a bundled-SCAD comparison.
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
