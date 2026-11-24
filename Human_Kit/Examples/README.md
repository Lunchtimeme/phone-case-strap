# Worked example — the kit applied to one case

A matched set, cut from the same `strap_system_parameters.scad` that ships at the
top of this kit. **Print all three and they assemble and work** — that is the
point of including them.

| file | what it is | print |
|---|---|---|
| `backplate_rigid.stl` | rigid backplate, housing already cut into it | rigid |
| `perimeter_TPU.stl` | the matching flexible perimeter | TPU |
| `strap_TPU.stl` | the strap that fits those tracks | TPU |
| `strap_TPU.step` | same strap as STEP, for CAD | — |
| `strap_housing_negative.stl` | the housing on its own, as a slicer modifier | no |
| `cutter/` | the three perimeter-split cutter exports | no |

The strap is the same file as the kit's reference strap — the example backplate
was cut to those parameters, so it slides in without adjustment.

`backplate_rigid.stl` and `perimeter_TPU.stl` are one specific case: a **Galaxy
S25 Ultra** shell, split by the agent pack's run. Use them as a check on your
printer and your material before cutting a case of your own — a 12 minute
perimeter and a 90 minute backplate will tell you more about your settings than
any amount of previewing.

The strap sits on the track floor at **Z +0.60 mm**. Its ears drop into the tracks
from the phone-facing side; the phone closes them once it's in the case.

## Licence

The case geometry here is a remix of
["S25 Ultra case with edge protection"](https://makerworld.com/en/models/1183966-s25-ultra-case-with-edge-protection)
by **Alex ([@alexm2901](https://makerworld.com/en/@alexm2901))**, CC BY-NC-SA 4.0.

Changes: two zero-length non-manifold edges were collapsed so the mesh would
boolean; the back panel was split from the perimeter with the parametric cutter;
the strap housing was subtracted from the backplate. Nothing else was altered.

These files inherit that licence — non-commercial, ShareAlike, credited to Alex
for the case and to **lunchtime** for the strap, the split profile and the
housing.
