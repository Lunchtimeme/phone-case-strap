#!/usr/bin/env python3
"""Build the analytic strap-housing negative for CAD/B-rep booleans.

Run this script inside the Python environment supplied by FreeCAD, for example:

    FreeCADCmd build_agentsafe_housing.py

or on installations using the lowercase executable:

    freecadcmd build_agentsafe_housing.py

The script writes `strap_housing_negative_agentsafe.step` and `.stl` beside
itself, but only after its geometry checks pass.

WHY THERE ARE TWO HOUSING FILES IN THIS PROJECT
------------------------------------------------
The Human Kit `strap_housing_negative.stl` is intended for use as a slicer
negative-volume modifier. Its default `spring_air_gap` is 0.20 mm, a setting
the project owner successfully used with a 0.6 mm nozzle and 0.20 mm layers
after regenerating the modifier STL. That value is a known-good starting
point for that workflow, not a universal printer/material rule.

The faceted Human Kit STL contains coincident faces around the spring relief.
Although it is suitable as a slicer modifier, converting it to a B-rep and
using it in an OCCT boolean can create zero-area sliver faces or non-manifold
results. This script therefore rebuilds the negative analytically and adds
small deliberate overlaps at those boundaries to avoid exact face coincidence.

This analytic CAD/B-rep variant uses a separate 0.40 mm spring air gap. It is
a more conservative two-layer gap for a 0.20 mm layer profile and reduces the
remaining spring-beam height, so the detent may feel softer than the Human Kit
0.20 mm variant. It is not a universal minimum or a mandatory 2x-layer rule.
Choose the gap for the target material and process, inspect the resulting
beam, and test the detent physically. Do not assume the two negative volumes
are geometrically interchangeable.

PARAMETER SOURCING
------------------
The geometry parameters are read from the Human Kit's
`strap_system_parameters.scad` at build time - the same file the SCAD models
include - so the analytic STEP variant cannot drift away from them. Point
`STRAP_PARAMETERS` at a different parameter file to build a variant.
`SPRING_AIR_GAP=0.40` remains an intentional override of the Human Kit's 0.20 mm
default, and the two are not interchangeable.

All dimensions are in millimetres. Exterior back face is Z=0; +Z points toward
the phone. The part is generated in strap-local coordinates: X is centred on
the strap band and Y=0 is the fixed end.
"""

import math
import os
import sys

import Part
from FreeCAD import Vector

# --------------------------------------------------------------------------
# Parameters: read from the Human Kit's shared parameter file at build time.
#
# There is one source of truth for these numbers - strap_system_parameters.scad.
# This module evaluates that file's numeric assignments instead of carrying a
# hand-copied set of constants, which is what let the analytic STEP variant drift
# away from the SCAD version. If the file is missing, or a value cannot be
# evaluated, the build stops rather than guessing.
#
# The three spring gaps remain deliberately different and are NOT unified:
#   0.10 mm  integrated in the accepted S25 backplate, physically tested
#   0.20 mm  Human Kit slicer modifier default (in the SCAD)
#   0.40 mm  this analytic B-rep variant (below)
# --------------------------------------------------------------------------
from pathlib import Path


def _candidate_dirs():
    """Where the parameter module might live, without relying on __file__."""
    dirs = []
    try:
        dirs.append(Path(__file__).resolve().parent)
    except NameError:
        pass
    dirs += [Path.cwd(), Path.cwd() / "modules", Path.cwd().parent / "modules"]
    return dirs


def _load_scad_params():
    """Import scad_params.py from beside this script.

    FreeCADCmd does not put the script's directory on sys.path, so the module is
    loaded by path rather than by name.
    """
    import importlib.util
    tried = []
    for d in _candidate_dirs():
        cand = d / "scad_params.py"
        tried.append(cand)
        if cand.is_file():
            spec = importlib.util.spec_from_file_location("scad_params", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError("cannot find modules/scad_params.py; looked in:\n"
                       + "\n".join(f"  {c}" for c in tried))


scad_params = _load_scad_params()
PARAMETERS = scad_params.Parameters(extra_dirs=_candidate_dirs())
PARAMETERS_FILE = PARAMETERS.path
UNRESOLVED = PARAMETERS.unresolved


def P(name):
    try:
        return PARAMETERS[name]
    except KeyError as e:
        raise RuntimeError(str(e)) from None


STRAP_LENGTH = P("strap_length")
STRAP_BAND_WIDTH = P("strap_band_width")
STRAP_EAR_WIDTH = P("strap_ear_width")
STRAP_EAR_CENTER_SPACING = P("strap_ear_center_spacing")
STRAP_FIXED_EAR_LENGTH = P("strap_fixed_ear_length")
STRAP_MOVING_EAR_LENGTH = P("strap_moving_ear_length")
STRAP_FIXED_SOCKET_CLEARANCE = P("strap_fixed_socket_clearance")
STRAP_TRAVEL = P("strap_travel")
TRACK_HARD_STOP_OVERTRAVEL = P("track_hard_stop_overtravel")
STRAP_STOW_NOTCH_OFFSET = P("strap_stow_notch_offset")

TRACK_CENTER_SPACING = P("track_center_spacing")
TRACK_WIDTH = P("track_width")
TRACK_FLOOR_THICKNESS = P("track_floor_thickness")
BACKPLATE_THICKNESS = P("backplate_thickness")
NEGATIVE_CUT_OVERRUN = P("negative_cut_overrun")
STRAP_WINDOW_WIDTH = P("strap_window_width")
STRAP_WINDOW_END_CLEARANCE = P("strap_window_end_clearance")
STRAP_WINDOW_CORNER_RADIUS = P("strap_window_corner_radius")

SPRING_BODY_WIDTH = P("spring_body_width")
SPRING_RELIEF_WIDTH = P("spring_relief_width")
SPRING_BEAM_HALF_LENGTH = P("spring_beam_half_length")
SPRING_RELIEF_HALF_LENGTH = P("spring_relief_half_length")
SPRING_NOSE_HALF_LENGTH = P("spring_nose_half_length")
SPRING_NOSE_DEPTH = P("strap_detent_nose_depth")
SPRING_NOSE_SAMPLES = int(P("spring_nose_samples"))

# --- the two deliberate differences ---------------------------------------
# More conservative B-rep variant; see the module README.
SPRING_AIR_GAP = 0.40
# How far the cavities reach past the keep-out boundary so no two faces are
# exactly coincident. The keep-out trims this back; geometry is unaffected.
SAFE_OVERLAP = 0.10
# Keep-out starts this far above the air-gap cavity's top face.
KEEPOUT_START_CLEARANCE = 0.02

# --------------------------------------------------------------------------
# Derived (same formulas as the shared parameter file)
# --------------------------------------------------------------------------
TRACK_OUTER_X = TRACK_CENTER_SPACING / 2 + TRACK_WIDTH / 2          # 16.80
TRACK_Y_MIN = STRAP_LENGTH - STRAP_MOVING_EAR_LENGTH - STRAP_TRAVEL - TRACK_HARD_STOP_OVERTRAVEL
TRACK_Y_MAX = STRAP_LENGTH + 0.35
SPRING_DETENT_Y = STRAP_LENGTH - STRAP_STOW_NOTCH_OFFSET - STRAP_TRAVEL
WINDOW_LENGTH = STRAP_LENGTH + 2 * STRAP_WINDOW_END_CLEARANCE
TOP_Z = BACKPLATE_THICKNESS + NEGATIVE_CUT_OVERRUN
GAP_TOP_Z = TRACK_FLOOR_THICKNESS + SPRING_AIR_GAP
KEEPOUT_Z0 = GAP_TOP_Z + KEEPOUT_START_CLEARANCE
KEEPOUT_Z1 = 3.15


def log(*a):
    sys.stderr.write(" ".join(str(x) for x in a) + "\n")
    sys.stderr.flush()


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def rounded_rect_prism(cx, cy, w, h, z0, z1, r):
    b = Part.makeBox(w, h, z1 - z0, Vector(cx - w / 2, cy - h / 2, z0))
    vertical = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
    return b.makeFillet(r, vertical)


def spring_keepout_polygon(sign):
    """Plan outline of one spring beam: body plus the cosine detent nose.

    The nose leans toward the track centre, i.e. away from `boundary` in the
    direction of x = 0. Getting this sign wrong points both noses outwards.
    """
    y0 = SPRING_DETENT_Y - SPRING_BEAM_HALF_LENGTH
    y1 = SPRING_DETENT_Y + SPRING_BEAM_HALF_LENGTH
    n0 = SPRING_DETENT_Y - SPRING_NOSE_HALF_LENGTH
    n1 = SPRING_DETENT_Y + SPRING_NOSE_HALF_LENGTH
    boundary = sign * TRACK_OUTER_X
    outer = sign * (TRACK_OUTER_X + SPRING_BODY_WIDTH)

    pts = [(outer, y0), (boundary, y0)]
    for i in range(SPRING_NOSE_SAMPLES + 1):
        y = n0 + (n1 - n0) * i / SPRING_NOSE_SAMPLES
        bulge = SPRING_NOSE_DEPTH * math.cos(math.radians(90) * (y - SPRING_DETENT_Y) / SPRING_NOSE_HALF_LENGTH) ** 2
        pts.append((boundary - sign * bulge, y))
    pts.append((boundary, y1))
    pts.append((outer, y1))
    return pts


def build():
    cavities = [rounded_rect_prism(0, STRAP_LENGTH / 2, STRAP_WINDOW_WIDTH, WINDOW_LENGTH,
                                  -0.20, TOP_Z, STRAP_WINDOW_CORNER_RADIUS)]

    for s in (-1, 1):
        cx = s * TRACK_CENTER_SPACING / 2

        # fixed-end ear socket
        cavities.append(box(cx - TRACK_WIDTH / 2, cx + TRACK_WIDTH / 2,
                            -STRAP_FIXED_SOCKET_CLEARANCE,
                            STRAP_FIXED_EAR_LENGTH + STRAP_FIXED_SOCKET_CLEARANCE,
                            TRACK_FLOOR_THICKNESS, TOP_Z))

        # moving-ear track: outer end pushed SAFE_OVERLAP past the keep-out edge
        a, b = cx - TRACK_WIDTH / 2, cx + TRACK_WIDTH / 2
        if s > 0:
            b += SAFE_OVERLAP
        else:
            a -= SAFE_OVERLAP
        cavities.append(box(a, b, TRACK_Y_MIN, TRACK_Y_MAX, TRACK_FLOOR_THICKNESS, TOP_Z))

        # outer spring relief: pulled SAFE_OVERLAP/2 inward, into the keep-out
        c = s * (TRACK_OUTER_X + SPRING_BODY_WIDTH + SPRING_RELIEF_WIDTH / 2) - s * SAFE_OVERLAP / 2
        cavities.append(box(min(c - SPRING_RELIEF_WIDTH / 2, c + SPRING_RELIEF_WIDTH / 2),
                            max(c - SPRING_RELIEF_WIDTH / 2, c + SPRING_RELIEF_WIDTH / 2),
                            SPRING_DETENT_Y - SPRING_RELIEF_HALF_LENGTH,
                            SPRING_DETENT_Y + SPRING_RELIEF_HALF_LENGTH,
                            TRACK_FLOOR_THICKNESS, TOP_Z))

        # air gap under the moving beam span
        g0, g1 = s * TRACK_OUTER_X, s * (TRACK_OUTER_X + SPRING_BODY_WIDTH)
        cavities.append(box(min(g0, g1), max(g0, g1),
                            SPRING_DETENT_Y - SPRING_RELIEF_HALF_LENGTH,
                            SPRING_DETENT_Y + SPRING_RELIEF_HALF_LENGTH,
                            TRACK_FLOOR_THICKNESS, GAP_TOP_Z))

    union = cavities[0]
    for c in cavities[1:]:
        union = union.fuse(c)

    keeps = []
    for s in (-1, 1):
        pts = spring_keepout_polygon(s)
        wire = Part.makePolygon([Vector(p[0], p[1], KEEPOUT_Z0) for p in pts] +
                                [Vector(pts[0][0], pts[0][1], KEEPOUT_Z0)])
        keeps.append(Part.Face(wire).extrude(Vector(0, 0, KEEPOUT_Z1 - KEEPOUT_Z0)))

    keepout = keeps[0].fuse(keeps[1])
    return union.cut(keepout)


def selftest(neg):
    """Cut a plain 4 mm slab and prove floor / gap / beam are all as intended."""
    log("--- self-test: cut a 4.00 mm flat slab ---")
    slab = box(-30, 30, -10, 160, 0.0, 4.0)
    cut = slab.cut(neg)
    log("   slab after cut: solids=%d valid=%s closed=%s" % (len(cut.Solids), cut.isValid(), cut.isClosed()))

    def filled(tag, x0, x1, y0, y1, z0, z1):
        v = cut.common(box(x0, x1, y0, y1, z0, z1)).Volume
        exp = (x1 - x0) * (y1 - y0) * (z1 - z0)
        log("   %-34s %6.1f%% of the sample" % (tag, 100 * v / exp))
        return v / exp

    # Probe positions are derived from the parameter set, never hard-coded:
    # fixed numbers silently pointed at empty space the moment the strap changed.
    floor_x0 = STRAP_WINDOW_WIDTH / 2 + 0.3      # clear of the through-window
    floor_x1 = TRACK_OUTER_X - 0.2               # inside the track cavity wall
    beam_x0 = TRACK_OUTER_X + 0.05               # spring beam span
    beam_x1 = TRACK_OUTER_X + SPRING_BODY_WIDTH - 0.05
    probe_y0 = SPRING_DETENT_Y - SPRING_BEAM_HALF_LENGTH + 2.0
    probe_y1 = SPRING_DETENT_Y + SPRING_BEAM_HALF_LENGTH - 2.0

    floor_ok = filled("track floor (below the gap)", floor_x0, floor_x1,
                      probe_y0, probe_y1, 0.05, TRACK_FLOOR_THICKNESS - 0.05)
    gap_ok = filled("air gap under the spring", beam_x0, beam_x1,
                    probe_y0, probe_y1, TRACK_FLOOR_THICKNESS + 0.03, GAP_TOP_Z - 0.03)
    beam_ok = filled("spring beam (above the gap)", beam_x0, beam_x1,
                     probe_y0, probe_y1, GAP_TOP_Z + 0.03, min(2.40, 4.0 - 0.1))
    log("   nominal gap height = %.3f mm, beam height in a %.2f mm panel = %.3f mm"
        % (SPRING_AIR_GAP, BACKPLATE_THICKNESS, BACKPLATE_THICKNESS - GAP_TOP_Z))
    ok = floor_ok > 0.85 and gap_ok < 0.02 and beam_ok > 0.95
    log("   self-test: %s" % ("PASS" if ok else "FAIL"))
    return ok


def main():
    here = os.path.dirname(os.path.abspath(__file__)) or "."
    log("building agent-safe housing negative")
    log("  air gap        = %.2f mm  (Human Kit slicer-modifier default is 0.20 mm)" % SPRING_AIR_GAP)
    log("  safe overlap   = %.2f mm" % SAFE_OVERLAP)
    log("  track y range  = %.2f .. %.2f mm" % (TRACK_Y_MIN, TRACK_Y_MAX))
    log("  spring detent  = y %.2f mm" % SPRING_DETENT_Y)

    neg = build()
    bb = neg.BoundBox
    log("  result: solids=%d valid=%s closed=%s volume=%.3f mm3"
        % (len(neg.Solids), neg.isValid(), neg.isClosed(), neg.Volume))
    log("  bbox   x %.3f .. %.3f   y %.3f .. %.3f   z %.3f .. %.3f"
        % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))

    problems = []
    if len(neg.Solids) != 1:
        problems.append("expected 1 solid, got %d" % len(neg.Solids))
    if not neg.isValid():
        problems.append("shape is not valid")
    if not neg.isClosed():
        problems.append("shape is not closed")
    if any(f.Area < 1e-7 for f in neg.Faces):
        problems.append("zero-area faces present")

    test_ok = selftest(neg)
    if not test_ok:
        problems.append("geometry self-test failed")

    # Never write an apparently usable negative when validation has failed.
    if problems:
        log("FAILED - no output files written:")
        for p in problems:
            log("  - " + p)
        sys.exit(1)

    out_step = os.path.join(here, "strap_housing_negative_agentsafe.step")
    out_stl = os.path.join(here, "strap_housing_negative_agentsafe.stl")
    neg.exportStep(out_step)
    neg.exportStl(out_stl)
    log("  wrote %s (%d bytes)" % (os.path.basename(out_step), os.path.getsize(out_step)))
    log("  wrote %s (%d bytes)" % (os.path.basename(out_stl), os.path.getsize(out_stl)))
    log("OK - geometry tests passed; output files written")


# FreeCADCmd executes this file without setting __name__ to "__main__", so the
# build runs unconditionally rather than behind the usual guard.
main()
