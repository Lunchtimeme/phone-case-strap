# Analytic strap-housing negative for CAD booleans

Use this module when the housing will be subtracted from a rigid-case rear panel in a B-rep CAD kernel (FreeCAD/OCCT or CadQuery). It is not the same geometry as the Human Kit slicer-modifier STL.

| File | Purpose |
|---|---|
| `strap_housing_negative_agentsafe.step` | Preferred analytic negative for CAD/B-rep boolean subtraction. |
| `strap_housing_negative_agentsafe.stl` | Mesh export for inspection or slicer use. |
| `build_agentsafe_housing.py` | FreeCAD builder with geometry and slab self-tests. |

## Important distinction: 0.20 mm vs 0.40 mm

- The Human Kit SCAD and shipped negative STL use **0.20 mm**. The project owner confirmed this setting in their 0.20 mm layer / 0.6 mm nozzle slicer workflow. Use it as the slicer-modifier starting point for that profile.
- This analytic B-rep module uses **0.40 mm**. It is a deliberately more conservative two-layer spring gap for a 0.20 mm layer profile. It also avoids exactly coincident faces around the spring, which made the Human Kit faceted STL unreliable as an OCCT boolean input. The larger gap shortens the remaining free spring beam height and can make the detent softer.

Do not describe 0.40 mm as a universal minimum. If matching the Human Kit/user-tested 0.20 mm behaviour is important, regenerate an analytic 0.20 mm variant and validate it in the target CAD kernel and on a test print. Do not simply substitute the faceted Human Kit STL into a B-rep boolean.

## Coordinate system and placement

The negative is generated in strap-local coordinates:

- exterior back face: Z=0;
- +Z: toward the phone cavity;
- X=0: strap-band centre;
- Y=0: fixed end, +Y toward moving end.

The housing footprint is approximately 32.4 x 145.7 mm. Place it on a clear rear-panel area and check cameras, rails, buttons, ports and outer skin thickness. The S25 placement values in the Agent Handoff are an example for that case only. The outer ~3.2 mm of a split backplate belongs to the vertical-capture interlock, so the usable flat area starts that far in.

## Rebuilding

The builder is intended to run inside the FreeCAD Python environment, not ordinary system Python:

```sh
cd Agent_Pack/modules
FreeCADCmd build_agentsafe_housing.py
# On installations using the lowercase executable name:
freecadcmd build_agentsafe_housing.py
```

The build script keeps its relevant geometry parameters as inline Python constants that manually mirror the included read-only snapshot of the Human Kit SCAD parameter file. They are not automatically synchronized. If you change strap length, ear dimensions, travel, track dimensions or notch position, update both sources and inspect the derived geometry. The 0.40 mm `SPRING_AIR_GAP` here is an intentional override of the Human Kit's 0.20 mm default.

The builder performs a flat-slab test and checks that the track floor survives, the air gap is empty and the spring beam remains solid. It now exits before exporting if these checks fail. The script calls `main()` unconditionally because some FreeCADCmd builds execute scripts without setting `__name__` to `__main__`.

## After subtraction

- Re-import the result and confirm one valid, closed solid.
- Confirm the exported STL is watertight and one connected component (`prusa-slicer --info part.stl` where available).
- Probe the spring gap and inspect the beam underside bridge paths.
- Confirm the track floor and exterior skin remain continuous.
- Place the strap in its assembled orientation and check for intersections; raw print orientation is not assembly orientation.
- Test the detent and retention physically. CAD validity does not prove spring force or fatigue life.

---

Part of the Agent Pack 1.0. The original work here is licensed CC BY-NC-SA 4.0; credit **lunchtime** and link the source listing and the licence if you redistribute or remix it. Full terms: `../LICENSE`.
