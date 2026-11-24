# The agent

This is a **decision procedure with a script attached**, not an autonomous
pipeline. The script does measuring, arithmetic and booleans. The judgement —
where the strap goes, which way round, and whether it fits at all — is the part
you (an agent or a person) are expected to make, and the script is built to
refuse rather than guess when that judgement hasn't been made.

It drives the Human Kit's own SCAD files
(`perimeter_split_negative.scad`, `strap_housing_negative.scad`); it holds no
copy of the joint geometry.

## The four decisions that matter

### 1. Never centre the housing

A phone case is not a blank rectangle. It has a camera cluster cut clean through
the back panel, usually 30-35 mm wide and 55-60 mm tall, sitting hard against
one long edge. The strap housing is a **negative volume** — it is where the strap
will live. If it overlaps the camera opening you get a part that cannot be
assembled, and the boolean will still succeed and look clean. That is the single
most expensive mistake in this workflow.

Find the openings, then offset the housing into the clear band beside them.

### 2. Springs at the camera end

The housing is not symmetric along its length. The spring/detent beam sits near
the **moving** end, at roughly 75 % of the strap length. The camera end of the
phone is the top. So in every case seen so far the springs belong at the top,
which means the housing is usually rotated 180° relative to the case's own
coordinate system.

Get this wrong and the strap's detents engage at the wrong end of its travel:
the part prints, the strap goes in, and it locks in the wrong position.

### 3. Clearance is the bridge of material left behind

Keep at least **2.0 mm** between the housing rectangle and any opening, and
2.0 mm from the backplate edge. That gap is the wall carrying load between two
holes; below roughly 1.2 mm in rigid filament it becomes the place the part
breaks.

The script measures clearance to the openings' bounding rectangles, which is
deliberately conservative — real openings are rounded, so the true gap is
usually a little larger than reported.

### 4. If it does not fit, narrow the strap

The order of concessions:

1. **Move** the housing within the clear band (the script searches this).
2. **Narrow the strap** — reduce `strap_band_width` and `track_center_spacing` in
   `strap_system_parameters.scad`, then regenerate the strap so the two still
   match. This is the intended answer when the phone is small or the camera
   cluster is wide.
3. **Lower the clearance**, and only with a reason. Say so in the report.

Never widen the case to fit the strap, and never let the housing touch an
opening.

## Usage

```sh
cd Agent_Pack
python3 agent/agent.py --case reference/case/s25UltraTHIKnoCutout.3mf --out build/
```

The tool exits non-zero and explains itself when the placement cannot satisfy
the clearance rule, in this shape:

```
no placement clears the case openings by 2.0 mm.
  housing is 37.0 x 145.7 mm
  best achievable clearance: 1.5 mm at x=56.78
  widest housing that fits at 2.0 mm clearance: 36.5 mm
```

(Those numbers are from the reference case *before* the strap was narrowed from
a 37.0 mm to a 28.1 mm housing, which is exactly the decision this message asks
for. With the narrowed strap it passes at the 2.0 mm default with 2.1 mm to
spare.)

That is a decision point, not an error to work around. Either narrow the strap
by the amount shown, or accept the smaller clearance deliberately and record
why.

| flag | meaning |
|---|---|
| `--case PATH` | `.3mf` (single body) or `.stl` |
| `--out DIR` | output directory (default `build/`) |
| `--clearance MM` | minimum gap to any opening or edge (default 2.0) |
| `--edge-margin MM` | minimum margin to the backplate edge (default 2.0) |
| `--strap-band-width MM` | narrow the strap when it will not fit |
| `--track-center-spacing MM` | narrow the tracks to match |
| `--housing-x MM` | force the centre X — **only** after reading the clearances |
| `--no-rotate` | keep the housing's native orientation |
| `--chamfer MM` | corner chamfer for the split ring (default 6.0) |
| `--human-kit PATH` | where the Human Kit lives (default `../Human_Kit`) |
| `--no-housing` | split only |

## What the script measures

| quantity | method |
|---|---|
| exterior back face | which Z extreme carries the larger flat surface area |
| back-panel thickness | median first-wall thickness over nine ray casts |
| visible outline | footprint of vertices within 0.5 mm of the back face |
| fitted outline | shrink until the cut ring stays inside back-panel material |
| openings | grid scan of in/out parity through the panel, clustered |
| camera end | the Y half holding the largest opening |

**The fitted outline matters as much as the placement.** A case's visible
outline curves into its side walls. A cut ring that lands in a 12 mm wall cuts a
slot and leaves material above the cutter, so the two halves stay fused even
though the boolean reports success. The fit shrinks the outline until the worst
wall along the whole ring — chamfer corners included — is within the cutter's
vertical reach.

## Repair

Exported meshes are often not manifold. The reference case has two zero-length
edges where two surfaces meet, and CGAL refuses the whole model because of
them. The script collapses any edge shared by more than two faces and reports
the distance; above 0.1 mm it warns, because at that point it is changing the
model rather than repairing it.

## Outputs

| file | what |
|---|---|
| `01_case_normalised.stl` | input, repaired, back face at Z=0 |
| `02_cutter.stl` | the Human Kit cutter at the fitted parameters |
| `03_split.stl` | boolean result |
| `04_perimeter.stl` | TPU perimeter |
| `05_backplate.stl` | rigid backplate with the housing subtracted |
| `06_housing_negative.stl` | housing negative on its own |
| `report.md`, `report.json` | every measurement, the placement, the clearances, the log |

## Still yours to check

- The strap you print must be oriented to match the housing — notched/moving end
  towards the springs.
- Camera, button and port keep-outs on the *perimeter* are not checked; only the
  back panel is.
- No STEP export; OpenSCAD cannot. Use `modules/` for B-rep work.
- A clean boolean is not a fit test.
