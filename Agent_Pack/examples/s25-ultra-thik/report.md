# Agent run report

- input: `s25UltraTHIKnoCutout.3mf` - 3879 verts, 7770 tris
- back face: z = -2.80 mm
- back-panel thickness: **2.80 mm**
- measured outline: 78.89 x 164.09 mm
- fitted outline: **77.89 x 163.09 mm** (worst wall on the cut ring 2.80 mm)
- split into **2 parts**
- perimeter: 83.15 x 167.60 x 11.93 mm, 13914 mm3
- backplate: 77.04 x 162.24 x 2.80 mm, 27654 mm3

## Strap housing placement

- openings found in the back panel: **1**
  - opening 0: x 3.98..37.58, y 3.38..61.58 (33.6 x 58.2 mm)
- camera end of the phone: **low** (detected)
- housing rotated: 180 deg (springs toward the camera end)
- housing rect: x 39.72..72.12, y 8.55..154.25
- offset from the centreline: 17.12 mm (target 6.0 mm) - this is what makes it a two-angle stand
- clearance to openings: [2.14]
- clearance to the interlock edge: 5.2 mm
- material removed: 8614 mm3, 1 part(s) after the cut

## Strap

- generated from the same parameters: [27.4, 143.5, 2.6] mm, 5922.3 mm3

## Assumptions

- chamfer is a parameter (default 6.0 mm), not measured
- the strap is generated from the same parameter set as the housing, so the two always match; strap_TPU.step is only rebuilt by modules/build_agentsafe_housing.py
- only the back panel is scanned for through-openings; side ports, buttons, raised camera islands and rails are not detected
- a panel with no openings is allowed - not every device has a camera behind the case - and is then placed by offset alone
- openings are approximated by their bounding rectangles, so reported clearances are conservative
- the outline is auto-fitted to the flat back panel, which may be smaller than the visible outline
- the kickstand's two angles come from the housing sitting off the centreline; a case too narrow to offset cannot have both

## Log

```
Human Kit   : /mnt/4TBHDD/3D Printing/Modely/Phone case S25U/Design by ChatGPT and me/Phone_Case_Public_Release_v2_3/Agent_Pack/human_kit  (bundled)
OpenSCAD    : /usr/sbin/openscad
case        : s25UltraTHIKnoCutout.3mf  3883 verts / 7786 tris
repair      : 2 degenerate edges collapsed (max 0.017 mm, tolerance 0.05 mm)
back face   : z=-2.80 (flat area 10888 mm2)
panel       : 2.80 mm thick (probes [2.225, 2.8, 2.8, 2.8, 2.8, 2.8, 2.8, 2.8])
outline     : 78.89 x 164.09 mm at (38.8, 81.4)
fitted      : 77.89 x 163.09 mm (worst wall on the cut ring 2.80 mm)
cutter      : 02_cutter.stl
split       : 2 parts
  perimeter : 83.15 x 167.60 x 11.93 mm, 13914 mm3
  backplate : 77.04 x 162.24 x 2.80 mm, 27654 mm3
strap       : 27.40 x 143.50 x 2.60 mm, 5922 mm3 - same parameters as the housing
opening 0   : x 3.98..37.58  y 3.38..61.58  (33.6 x 58.2 mm)
clear zone  : backplate inset by 5.2 mm (3.2 interlock + 2.0 margin)
camera end  : low (detected)  ->  springs at the top, housing rotated 180 deg
offset      : 17.12 mm off the centreline, target 6.0 mm
housing     : 32.4 x 145.7 mm at x 39.72..72.12, y 8.55..154.25
clearance   : 2.14 mm to the nearest opening, 5.2 mm to the interlock edge
removed     : 8614 mm3, 1 part(s)
```
