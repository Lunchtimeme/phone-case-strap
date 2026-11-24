# The agent

This is a **decision procedure with a script attached**, not an autonomous
pipeline. The script does measuring, arithmetic and booleans. The judgement —
where the strap goes, which way round, and whether it fits at all — is the part
you (an agent or a person) are expected to make, and the script is built to
refuse rather than guess when that judgement hasn't been made.

It drives the Human Kit's own SCAD files (`perimeter_split_negative.scad`,
`strap_housing_negative.scad`, `strap_parametric.scad`,
`strap_system_parameters.scad`). The pack carries a byte-identical copy of them
in `human_kit/` so it runs standalone; when a sibling `../Human_Kit/` is present
the two are compared and any divergence is reported.

## The four decisions that matter

### 1. Offset the housing from the centreline

Two reasons, and the first one is not about cameras at all:

- **The kickstand needs it.** The strap leans at two angles because it sits off
  the centre of the case: the standing loop ends up nearer one edge than the
  other, so it can rest at two different pitches. Centred, it stands at one.
- **The camera needs it.** A phone case is rarely a blank rectangle: there is
  usually a camera cluster cut clean through the back panel, 30-35 mm wide and
  55-60 mm tall, hard against one long edge. The strap housing is a **negative
  volume** — it is where the strap will live. Overlap the opening and you get a
  part that cannot be assembled, while the boolean still succeeds and looks
  clean.

A case with no openings at all is legitimate — not every device has a camera
behind the case — so an empty opening list is not an error. The offset rule still
applies, which is precisely what stops the tool dropping a centred housing onto a
blank panel.

### 2. Springs at the camera end

The housing is not symmetric along its length. The spring/detent beam sits near
the **moving** end, at roughly 75 % of the strap length. The camera end of the
phone is the top. So in every case seen so far the springs belong at the top,
which means the housing is usually rotated 180° relative to the case's own
coordinate system.

Get this wrong and the strap's detents engage at the wrong end of its travel:
the part prints, the strap goes in, and it locks in the wrong position.

### 3. Clearance is the bridge of material left behind

Keep at least **2.0 mm** between the housing rectangle and any opening, and keep
the interlock band plus a margin (`--joint-inset` + `--edge-margin`, 5.2 mm by
default) clear of every backplate edge. The gap between two holes is the wall
carrying load; below roughly 1.2 mm in rigid filament it becomes the place the
part breaks.

Those are two separate constraints and the tool tracks them separately, on all
four sides. The edge requirement is the stricter of the two because the outer
3.2 mm of a split backplate is the interlock's retaining rail — cut into it and
the perimeter comes off.

The script measures clearance to the openings' bounding rectangles, expanded by
half a sampling step, so the true gap is at least what it reports.

### 4. If it does not fit, narrow the strap

The order of concessions:

1. **Move** the housing within the clear band (the script searches this).
2. **Narrow the strap** — lower `strap_band_width` and/or `strap_ear_width`. The
   ear centres, track spacing, track width and window all follow from those by
   construction, and the agent regenerates the strap from the same values, so the
   two parts cannot end up mismatched. `--strap-band-width` and
   `--strap-ear-width` do exactly this. It is the intended answer when the phone
   is small or the camera cluster is wide.
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
no placement satisfies both constraints.
  housing            : 32.4 x 145.7 mm
  needed             : 2.0 mm to every opening, 5.2 mm to the interlock on all four sides
  opening clearance  : 1.34 mm
  edge clearance     : 5.2 mm
  widest housing that fits at 2.0 mm: 32.5 mm
```

(That is the real refusal from the reference case at a 33.2 mm housing — the
shipped 32.4 mm housing is the answer to this message. Note that both numbers
appear in it: the width that fails, and the width that would fit.)

That is a decision point, not an error to work around. Either narrow the strap
by the amount shown, or accept the smaller clearance deliberately and record
why.

| flag | meaning |
|---|---|
| `--case PATH` | `.3mf` (single body) or `.stl` |
| `--out DIR` | output directory (default `build/`) |
| `--clearance MM` | minimum gap to any opening (default 2.0) |
| `--joint-inset MM` | interlock band that must stay uncut (default 3.2) |
| `--edge-margin MM` | margin beyond that band (default 2.0) |
| `--min-offset MM` | how far off the centreline the housing must sit (default 6.0) — this is what gives the two kickstand angles |
| `--camera-end low\|high` | which end the camera is on. Detected when there are openings; give it for a case with none |
| `--strap-band-width MM` | narrow the strap. Applied to the strap **and** the housing together |
| `--strap-ear-width MM` | change the ear width. Applied to both |
| `--repair-tolerance MM` | largest non-manifold edge the repair may collapse (default 0.05); bigger ones abort |
| `--housing-x MM` | force the centre X — the position is still checked against every constraint |
| `--no-rotate` | keep the housing's native orientation |
| `--chamfer MM` | corner chamfer for the split ring (default 6.0) |
| `--human-kit PATH` | where the Human Kit lives (default: the copy bundled in `human_kit/`) |
| `--mirror DIR` | copy the printable parts into a Human Kit `Examples/` folder |
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
