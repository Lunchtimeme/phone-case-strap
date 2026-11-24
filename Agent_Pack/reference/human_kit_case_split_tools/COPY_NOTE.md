# Generic profiled split cutter - reference copy

This is a read-only copy of the reusable Human Kit five-segment vertical-capture perimeter cutter (Human Kit 1.0). It generates the actual negative-volume cut profile, not a straight razor slit. The source of truth for the human-facing module remains the separately distributed Human Kit at `Modules/Case_Split_Tools/` within that package.

Edit `perimeter_split_negative.scad` to set the donor backplate outline width, height, corner chamfer and thickness. The profile insets and step fractions are S25-derived starting values. It does not inspect arbitrary case meshes or identify keep-outs. Inspect camera, button, port, rail and wall clearances before subtraction.

See `README.md`, `validation.json` and the two diagrams. The test host proves only that the cutter splits a simple slab into two watertight components; it does not prove fit on a real phone case.
