# S25 Ultra case with edge protection — source model

`s25UltraTHIKnoCutout.3mf` is **not** the author's work. It is the reference
case that the Agent Pack's example is built on, included under the terms of its
original licence.

| | |
|---|---|
| **Title** | S25 Ultra case with edge protection |
| **Author** | Alex — https://makerworld.com/en/@alexm2901 |
| **Source** | https://makerworld.com/en/models/1183966-s25-ultra-case-with-edge-protection |
| **Licence** | CC BY-NC-SA 4.0 — https://creativecommons.org/licenses/by-nc-sa/4.0/ |
| **Released** | 2025-03-07 |
| **File** | `s25UltraTHIKnoCutout.3mf`, single body, 7786 triangles |

## Changes made

The original design was not modified. It is used as input geometry:

1. Two zero-length non-manifold edges were collapsed so the mesh can be
   processed by a boolean kernel (a repair, not a redesign).
2. The back panel was split from the perimeter with the Human Kit's parametric
   five-segment vertical-capture cutter.
3. A sliding strap housing was subtracted from the resulting backplate.

The generated parts in `../../examples/s25-ultra-thik/` are therefore a remix,
distributed under the same CC BY-NC-SA 4.0 licence as this source.

## What that means for reuse

- **No commercial use.** The whole release is NC because this file is NC.
- **ShareAlike.** Anything you publish that builds on these parts must carry the
  same licence.
- **Attribution.** Credit Alex (@alexm2901) for the case geometry, and the author of this
  kit for the split, the strap system and the housing.
