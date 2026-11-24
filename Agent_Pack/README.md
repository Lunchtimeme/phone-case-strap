# Agent Pack — autonomous case split and strap housing

**Version 1.0**

The Human Kit tells you how to measure a case, choose the cut profile and do the
booleans by hand. This pack does that for you: `agent/agent.py` measures the
case, fits the split ring, renders the Human Kit's own SCAD modules, performs
the booleans and checks its own output.

It is not a separate implementation of the joint. It **drives the Human Kit's
SCAD files**, so the two can never drift apart.

```sh
cd Agent_Pack
python3 agent/agent.py --case reference/case/s25UltraTHIKnoCutout.3mf --out build/
```

A run on the reference case takes about a second and produces a two-part split
plus a backplate with the strap tracks and springs already cut in.

## Start here

1. `agent/README.md` — how the agent measures, fits and verifies.
2. `reference/case/ATTRIBUTION.md` — whose case this is built on, and its licence.
3. `examples/s25-ultra-thik/` — one real run, start to finish, numbers included.
4. `AGENT_HANDOFF.md` — the accepted design's dimensions and the reasoning behind them.
5. `modules/README.md` — the analytic B-rep housing negative, for CAD work.
6. `project_context.json` — machine-readable summary.

## What the agent does

| stage | detail |
|---|---|
| repair | collapses zero-length non-manifold edges that boolean kernels reject |
| measure | finds the exterior back face, the panel thickness and the visible outline |
| fit | shrinks the outline until the whole cut ring sits in back-panel material |
| cut | renders `perimeter_split_negative.scad` and subtracts it |
| split | extracts the perimeter and backplate as separate solids |
| openings | scans the back panel for camera/sensor/socket through-holes |
| place | offsets the housing into the clear band and faces the springs at the camera end |
| housing | subtracts `strap_housing_negative.scad` from the backplate |
| verify | part counts, volumes, clearance, and `report.md` / `report.json` |

Two things are worth understanding before trusting a run:

**The fitted outline.** A case's visible outline curves into its side walls; a cut
ring that lands in a 12 mm wall cuts a slot and leaves material above the cutter,
so the two halves stay fused even though the boolean reports success. The fit
shrinks the outline until the worst wall along the entire ring, chamfer corners
included, is within the cutter's vertical reach. On the reference case that is
78.89 → 77.89 mm.

**The placement.** The camera cluster is a real hole in the back panel, and the
housing is a negative volume — centred, it carves straight into that hole and the
part cannot be assembled, while the boolean still looks clean. The agent finds
the openings, offsets the housing into the clear band, and puts the spring end at
the camera end of the phone. If it cannot satisfy the clearance rule it **exits
with the numbers instead of cutting**. See `agent/README.md` for the full decision
procedure.

## What changed from the previous Agent Pack

The earlier pack shipped CadQuery builders (`scripts/01`–`05`) tied to fixed S25
coordinates. They were a worked example that could not run without the
case meshes they were written against, and they duplicated logic that already
lives in the Human Kit. They are gone. `agent/` replaces them and is both
smaller and actually runnable.

The example geometry is now generated from a case that is licensed for
redistribution, so it ships: see `reference/case/`.

## Spring gaps — three values, three models

Do not treat these as interchangeable:

| gap | where it lives |
|---|---|
| **0.10 mm** | integrated into the accepted hand-built S25 backplate. Historical; described in `AGENT_HANDOFF.md`. |
| **0.20 mm** | Human Kit slicer-modifier default. Confirmed on a 0.20 mm layer / 0.6 mm nozzle profile. **This is what the agent produces.** |
| **0.40 mm** | `modules/strap_housing_negative_agentsafe.step`, an analytic two-layer variant for CAD booleans. |

Automatic variable layer height can ignore geometry that exists only inside a
negative-volume modifier. Set the gap in the SCAD, regenerate, and inspect the
bridge path.

## Requirements

- Python 3 (standard library only)
- OpenSCAD on `PATH`
- optional: PrusaSlicer, for an independent check on the exported STLs

## Limits

- No camera, button or port keep-out detection — inspect the split before printing.
- The chamfer is a parameter (6.0 mm default), not measured.
- The strap itself is the Human Kit's 143.5 mm reference strap.
- No STEP export; OpenSCAD cannot. Use `modules/` for B-rep.
- A clean boolean is not a fit test. Print it.

## Licence

CC BY-NC-SA 4.0. Everyone's original work is attributed in `LICENSE`, including
**Alex** (@alexm2901), whose "S25 Ultra case with edge protection" supplies the reference
case, and who is the reason this whole release is non-commercial.
