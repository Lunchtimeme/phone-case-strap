#!/usr/bin/env python3
"""
Autonomous phone-case strap installer.

Mirrors the Human Kit's manual workflow, but does the measuring, the parametric
selection and the boolean work itself:

    measure  ->  fit the split outline  ->  render the Human Kit cutter
             ->  split the case        ->  cut the strap housing
             ->  verify and report

It drives the *Human Kit's own SCAD files* (perimeter_split_negative.scad and
strap_housing_negative.scad). It does not carry its own copy of the joint
geometry, so anything you change in the Human Kit changes here too.

Requirements: python3 (standard library only) and OpenSCAD on PATH.
PrusaSlicer is optional and only used for an independent sanity check.

Usage:
    python3 agent.py --case path/to/case.3mf --out build/
    python3 agent.py --case case.stl --out build/ --chamfer 8 --no-housing

Exit codes:
    0 success, 1 bad input or geometry failure, 2 missing tool.
"""

import argparse
import collections
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------
# mesh io
# --------------------------------------------------------------------------

# Output name -> name used in the Human Kit's flat Examples/ folder.
MIRROR_MAP = {
    "04_perimeter.stl": "perimeter_TPU.stl",
    "05_backplate.stl": "backplate_rigid.stl",
}

V3 = "([-\\d.eE+]+)"            # number as written in 3MF xml


def read_3mf(path):
    """Return (verts, tris) from a 3MF container holding a single mesh object.

    3MF allows several objects, components and build transforms. This reads the
    common single-object case exactly and refuses anything else rather than
    guessing - a wrong mesh is worse than a clear error.
    """
    import re
    with zipfile.ZipFile(path) as z:
        model = None
        for name in z.namelist():
            if name.lower().endswith(".model"):
                model = z.read(name).decode("utf-8", "replace")
                break
    if model is None:
        raise SystemExit(f"{path}: no 3dmodel.model inside the 3MF")

    objects = len(re.findall(r"<object\b", model))
    comps = len(re.findall(r"<component\b", model))
    if objects != 1 or comps:
        raise SystemExit(
            f"{path}: this 3MF has {objects} objects and {comps} components. "
            "Export it as a single body first (the agent can only boolean a single closed mesh)."
        )

    v = re.findall(r'<vertex x="%s" y="%s" z="%s"' % (V3, V3, V3), model)
    t = re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', model)
    verts = [(float(a), float(b), float(c)) for a, b, c in v]
    tris = [(int(a), int(b), int(c)) for a, b, c in t]
    if not verts or not tris:
        raise SystemExit(f"{path}: no mesh data found")
    return verts, tris


def read_stl(path):
    b = Path(path).read_bytes()
    if b[:5].lower() == b"solid" and b"facet" in b[:2000]:
        import re
        v = re.findall(rb"vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)", b)
        verts = [(float(x), float(y), float(z)) for x, y, z in v]
        tris = [(i, i + 1, i + 2) for i in range(0, len(verts), 3)]
        return verts, tris
    n = struct.unpack("<I", b[80:84])[0]
    verts, tris = [], []
    for i in range(n):
        d = struct.unpack("<12fH", b[84 + 50 * i:134 + 50 * i])
        base = len(verts)
        verts += [(d[3], d[4], d[5]), (d[6], d[7], d[8]), (d[9], d[10], d[11])]
        tris.append((base, base + 1, base + 2))
    return verts, tris


def write_stl(path, verts, tris):
    out = bytearray(b"agent.py - vertical-capture phone-case split".ljust(80, b"\0"))
    out += struct.pack("<I", len(tris))
    for a, b, c in tris:
        out += struct.pack("<3f", 0, 0, 0)
        for i in (a, b, c):
            out += struct.pack("<3f", *verts[i])
        out += struct.pack("<H", 0)
    Path(path).write_bytes(bytes(out))


def weld_mesh(verts, tris, tol=1e-4):
    """Merge coincident vertices. Returns (welded verts, welded tris)."""
    idx, weldv, out = {}, [], []
    for a, b, c in tris:
        row = []
        for i in (a, b, c):
            p = verts[i]
            k = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
            if k not in idx:
                idx[k] = len(weldv)
                weldv.append(p)
            row.append(idx[k])
        if len(set(row)) == 3:
            out.append(tuple(row))
    return weldv, list(dict.fromkeys(out))


def edge_map(tris):
    e = collections.defaultdict(list)
    for i, (a, b, c) in enumerate(tris):
        for pair in ((a, b), (b, c), (c, a)):
            e[tuple(sorted(pair))].append(i)
    return e


# --------------------------------------------------------------------------
# repair
# --------------------------------------------------------------------------

def repair(verts, tris):
    """Make the mesh edge-manifold.

    Exported case models routinely contain a few zero-length edges where two
    surfaces meet. Boolean kernels (CGAL especially) refuse those outright, so
    collapse any edge shared by more than two faces onto a single vertex. The
    collapse distance is reported; anything above 0.1 mm is flagged because it
    starts to change the model.
    """
    verts, tris = weld_mesh(verts, tris)
    report: dict = {"collapsed_edges": [], "warnings": []}

    for _ in range(6):
        em = edge_map(tris)
        bad = [(e, f) for e, f in em.items() if len(f) > 2]
        if not bad:
            break
        merge = {}
        for (v0, v1), faces in bad:
            d = math.dist(verts[v0], verts[v1])
            report["collapsed_edges"].append({"vertices": [v0, v1], "faces": len(faces), "distance_mm": round(d, 4)})
            if d > 0.1:
                report["warnings"].append(f"collapsed a {d:.3f} mm edge - check the source model")
            merge[v1] = v0

        def resolve(i, _m=merge):
            while i in _m:
                i = _m[i]
            return i

        tris = [tuple(resolve(i) for i in t) for t in tris]
        tris = list(dict.fromkeys(t for t in tris if len(set(t)) == 3))

    em = edge_map(tris)
    report["boundary_edges"] = sum(1 for f in em.values() if len(f) == 1)
    report["non_manifold_edges"] = sum(1 for f in em.values() if len(f) > 2)
    report["triangles"] = len(tris)
    report["vertices"] = len({i for t in tris for i in t})
    return verts, tris, report


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------

def triangle_volume(verts, tris):
    v = 0.0
    for a, b, c in tris:
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        v += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6.0
    return abs(v)


class Caster:
    """Axis-parallel ray casting along Z, with a 2D bounding-box reject."""

    def __init__(self, verts, tris):
        self.tris = [(verts[a], verts[b], verts[c]) for a, b, c in tris]
        self.boxes = [
            (min(p[0] for p in t), max(p[0] for p in t),
             min(p[1] for p in t), max(p[1] for p in t))
            for t in self.tris
        ]

    def hits(self, px, py):
        out = []
        for (a, b, c), (x0, x1, y0, y1) in zip(self.tris, self.boxes):
            if px < x0 or px > x1 or py < y0 or py > y1:
                continue
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
            l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
            l3 = 1 - l1 - l2
            if l1 < -1e-9 or l2 < -1e-9 or l3 < -1e-9:
                continue
            out.append(l1 * a[2] + l2 * b[2] + l3 * c[2])
        return sorted(out)

    def first_wall(self, px, py):
        h = self.hits(px, py)
        return (h[1] - h[0]) if len(h) >= 2 else None


def back_face(verts, tris):
    """Which Z extreme is the exterior back panel?

    The back panel is a large flat area, the open side is not. Compare the
    surface area lying in a thin band at each extreme.
    """
    zs = [v[2] for v in verts]
    zmin, zmax = min(zs), max(zs)

    def flat_area(zflat):
        total = 0.0
        for a, b, c in tris:
            if all(abs(verts[i][2] - zflat) < 0.15 for i in (a, b, c)):
                u = [verts[b][k] - verts[a][k] for k in range(3)]
                w = [verts[c][k] - verts[a][k] for k in range(3)]
                cx, cy, cz = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
                total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
        return total

    a_low, a_high = flat_area(zmin), flat_area(zmax)
    return (zmin, a_low, a_high) if a_low >= a_high else (zmax, a_low, a_high)


def outline_contour(w, h, chamfer, inset, cx, cy, samples=200):
    """Points along a chamfered rectangle, corners included.

    The chamfer segments matter: on real cases the corners carry extra material
    ("bump resistant corners"), and a cut ring that skims them fails to separate
    even when every straight edge looks clean.
    """
    W, H = w - 2 * inset, h - 2 * inset
    c = min(chamfer, min(W, H) / 2 - 0.01)
    poly = [
        (-W / 2 + c, -H / 2), (W / 2 - c, -H / 2),
        (W / 2, -H / 2 + c), (W / 2, H / 2 - c),
        (W / 2 - c, H / 2), (-W / 2 + c, H / 2),
        (-W / 2, H / 2 - c), (-W / 2, -H / 2 + c),
    ]
    perim = sum(math.dist(poly[i], poly[(i + 1) % 8]) for i in range(8))
    pts = []
    for i in range(8):
        a, b = poly[i], poly[(i + 1) % 8]
        seg = math.dist(a, b)
        n = max(2, int(round(samples * seg / perim)))
        for k in range(n):
            t = k / n
            pts.append((cx + a[0] + t * (b[0] - a[0]), cy + a[1] + t * (b[1] - a[1])))
    return pts


def fit_outline(caster, outline, thickness, chamfer, outer_inset, tol=0.15, step=0.5, min_margin=1.0):
    """Shrink the outline until the whole cut ring sits in the flat back panel.

    The Human Kit asks you to 'enter the visible backplate outline'. On a real
    case that outline curves into the side walls, and a cut ring that lands in
    the wall leaves material above the cutter - the two halves never separate.

    The tolerance is tied to the cutter, not to taste: the outer wall reaches
    profile_top + cut_end_overrun (2.80 + 0.20 = 3.00 mm here), so any material
    thicker than that along the contour bridges the cut. Keep the allowed wall
    below that with a margin.
    """
    w, h = outline["width"], outline["height"]
    cx, cy = outline["center_x"], outline["center_y"]
    attempts = []
    for _ in range(40):
        worst = 0.0
        for px, py in outline_contour(w, h, chamfer, outer_inset, cx, cy):
            t = caster.first_wall(px, py)
            if t and t > worst:
                worst = t
        attempts.append({"width": round(w, 2), "height": round(h, 2), "max_wall_mm": round(worst, 2)})
        if worst <= thickness + tol:
            return {"width": round(w, 2), "height": round(h, 2), "max_wall_mm": round(worst, 2)}, attempts
        if w - 2 * step < 2 * (3.2 + chamfer + min_margin):
            break
        w -= step
        h -= step
    raise SystemExit(
        "could not fit a split outline inside the flat back panel: "
        f"last attempt {attempts[-1] if attempts else 'n/a'}"
    )


# --------------------------------------------------------------------------
# openscad
# --------------------------------------------------------------------------

def find_openscad():
    exe = shutil.which("openscad")
    if not exe:
        raise SystemExit("openscad not found on PATH (install it, or pass --openscad)")
    return exe


def run_openscad(exe, scad_text, out_stl, workdir, defines=None, extra_files=()):
    work = Path(workdir)
    script = work / "driver.scad"
    script.write_text(scad_text)
    cmd = [exe, "-o", str(out_stl), "--export-format", "binstl"]
    for k, v in (defines or {}).items():
        cmd += ["-D", f"{k}={v}"]
    cmd.append(str(script))
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(work))
    if r.returncode != 0 or not Path(out_stl).exists():
        raise SystemExit(f"OpenSCAD failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    if "empty" in r.stdout.lower():
        raise SystemExit(f"OpenSCAD produced an empty model for {out_stl}\n{r.stdout[-1000:]}")
    return r.stdout


# --------------------------------------------------------------------------
# components
# --------------------------------------------------------------------------

def components(verts, tris, tol=1e-4):
    """Edge-connected components. Vertex contact alone is not a connection."""
    verts, indexed = weld_mesh(verts, tris, tol)
    em = edge_map(indexed)
    parent = list(range(len(indexed)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for faces in em.values():
        for j in faces[1:]:
            ra, rb = find(faces[0]), find(j)
            if ra != rb:
                parent[ra] = rb

    groups = collections.defaultdict(list)
    for i in range(len(indexed)):
        groups[find(i)].append(i)
    out = []
    for ids in groups.values():
        sub = [indexed[i] for i in ids]
        used = sorted({i for t in sub for i in t})
        remap = {old: new for new, old in enumerate(used)}
        out.append({
            "verts": [verts[i] for i in used],
            "tris": [(remap[a], remap[b], remap[c]) for a, b, c in sub],
        })
    return out


def bbox(verts):
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "x": [round(min(xs), 3), round(max(xs), 3)],
        "y": [round(min(ys), 3), round(max(ys), 3)],
        "z": [round(min(zs), 3), round(max(zs), 3)],
        "size": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3), round(max(zs) - min(zs), 3)],
    }


# --------------------------------------------------------------------------
# main pipeline
# --------------------------------------------------------------------------

def material_at(caster, px, py, z):
    """True if the point is inside solid material at height z (ray parity)."""
    return sum(1 for h in caster.hits(px, py) if h < z) % 2 == 1


def find_openings(caster, backplate_bbox, z_probe, step=1.0, margin=1.5, min_points=6):
    """Through-openings in the back panel: camera, flash, sensors, pop-socket.

    These are where the phone's own hardware sits, so the strap housing must
    never overlap them - the housing is a negative volume, and carving into an
    existing hole produces a part that cannot be assembled.
    """
    x0, x1 = backplate_bbox["x"]
    y0, y1 = backplate_bbox["y"]
    pts = []
    y = y0 + margin
    while y <= y1 - margin:
        x = x0 + margin
        while x <= x1 - margin:
            if not material_at(caster, x, y, z_probe):
                pts.append((round(x, 2), round(y, 2)))
            x += step
        y += step

    pts_set, seen, out = set(pts), set(), []
    for p in pts:
        if p in seen:
            continue
        stack, comp = [p], []
        seen.add(p)
        while stack:
            c = stack.pop()
            comp.append(c)
            for dx in (-step, 0, step):
                for dy in (-step, 0, step):
                    q = (round(c[0] + dx, 3), round(c[1] + dy, 3))
                    if q in pts_set and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(comp) >= min_points:
            xs = [p_[0] for p_ in comp]
            ys = [p_[1] for p_ in comp]
            out.append({"x0": round(min(xs), 2), "x1": round(max(xs), 2),
                        "y0": round(min(ys), 2), "y1": round(max(ys), 2),
                        "samples": len(comp)})
    out.sort(key=lambda o: -((o["x1"] - o["x0"]) * (o["y1"] - o["y0"])))
    return out


def rect_gap(a, b):
    """Shortest distance between two axis-aligned rectangles; 0 if they touch."""
    dx = max(a["x0"] - b["x1"], b["x0"] - a["x1"], 0.0)
    dy = max(a["y0"] - b["y1"], b["y0"] - a["y1"], 0.0)
    return math.hypot(dx, dy)


def largest_free_width(openings, backplate_bbox, y_span, clearance, edge_margin):
    """Widest gap in X that clears every opening, at a given Y span."""
    bx0, bx1 = backplate_bbox["x"]
    lo, hi = bx0 + edge_margin, bx1 - edge_margin
    blocked = []
    for o in openings:
        if o["y1"] < y_span[0] - clearance or o["y0"] > y_span[1] + clearance:
            continue
        blocked.append((o["x0"] - clearance, o["x1"] + clearance))
    blocked.sort()
    best, cursor = 0.0, lo
    for b0, b1 in blocked:
        if b0 > cursor:
            best = max(best, min(b0, hi) - cursor)
        cursor = max(cursor, b1)
    if cursor < hi:
        best = max(best, hi - cursor)
    return max(0.0, best)


def place_housing(housing_bbox, backplate_bbox, openings, clearance, edge_margin, springs_local_end="high"):
    """Choose where the housing goes and which way round it faces.

    Two rules, both learned the hard way:

    1. Never centre it. A phone's camera cluster is a real hole in the back
       panel; a centred housing overlaps it. Offset laterally into the clear
       band instead.
    2. The spring/detent end faces the camera end of the phone. Every case in
       practice has the camera at the top, so the springs go to the top.

    Returns a placement dict, or raises SystemExit with the numbers needed to
    decide what to do instead (narrow the strap, or relax the clearance).
    """
    W, H = housing_bbox["size"][0], housing_bbox["size"][1]
    bx0, bx1 = backplate_bbox["x"]
    by0, by1 = backplate_bbox["y"]

    if openings:
        biggest = openings[0]
        cam_y = (biggest["y0"] + biggest["y1"]) / 2
        camera_end = "low" if cam_y < (by0 + by1) / 2 else "high"
    else:
        camera_end = "low"

    rotate = (camera_end == "low" and springs_local_end == "high") or \
             (camera_end == "high" and springs_local_end == "low")

    y_centre = (by0 + by1) / 2
    y_span = (y_centre - H / 2, y_centre + H / 2)

    best = None
    lo = bx0 + edge_margin + W / 2
    hi = bx1 - edge_margin - W / 2
    if hi < lo:
        raise SystemExit(
            f"housing {W:.1f} mm wide does not fit inside the backplate "
            f"({bx1 - bx0:.1f} mm) with a {edge_margin} mm edge margin. "
            "Narrow the strap before building."
        )

    # A fixed grid cannot land on the constraint boundary - it stops one step
    # short and reports a false failure. Test the exact positions where the
    # housing just clears an opening or the edge, plus a coarse sweep for the
    # cases in between.
    candidates = [lo, hi, (lo + hi) / 2]
    for o in openings:
        candidates.append(o["x1"] + clearance + W / 2)
        candidates.append(o["x0"] - clearance - W / 2)
    x = lo
    while x <= hi + 1e-9:
        candidates.append(x)
        x += 0.5

    for xc in candidates:
        xc = max(lo, min(hi, xc))
        rect = {"x0": xc - W / 2, "x1": xc + W / 2, "y0": y_span[0], "y1": y_span[1]}
        edge_gap = min(rect["x0"] - bx0, bx1 - rect["x1"], rect["y0"] - by0, by1 - rect["y1"])
        gaps = [rect_gap(rect, o) for o in openings]
        worst = min(gaps + [edge_gap])
        if best is None or worst > best["min_clearance"] + 1e-9:
            best = {"x_centre": round(xc, 2), "y_centre": round(y_centre, 2),
                    "min_clearance": round(worst, 2), "rect": rect,
                    "edge_gap": round(edge_gap, 2),
                    "opening_gaps": [round(g, 2) for g in gaps]}

    if best is None:
        raise SystemExit("internal error: no candidate placement was evaluated")

    if best["min_clearance"] + 1e-9 < clearance:
        free = largest_free_width(openings, backplate_bbox, y_span, clearance, edge_margin)
        raise SystemExit(
            f"no placement clears the case openings by {clearance} mm.\n"
            f"  housing is {W:.1f} x {H:.1f} mm\n"
            f"  best achievable clearance: {best['min_clearance']} mm at x={best['x_centre']}\n"
            f"  widest housing that fits at {clearance} mm clearance: {free:.1f} mm\n"
            "Decide: narrow the strap (reduce strap_band_width and track_center_spacing in\n"
            "strap_system_parameters.scad, regenerate the strap to match), or lower\n"
            "--clearance if the remaining bridge is genuinely thick enough."
        )

    return {"camera_end": camera_end, "rotate_180": rotate,
            "springs_local_end": springs_local_end, **best}


def main(argv=None):
    p = argparse.ArgumentParser(description="Autonomous strap-housing installer for phone cases.")
    p.add_argument("--case", required=True, help=".3mf or .stl case model")
    p.add_argument("--out", default="build", help="output directory")
    p.add_argument("--human-kit", default=None, help="path to Human_Kit/ (default: ../Human_Kit)")
    p.add_argument("--openscad", default=None)
    p.add_argument("--chamfer", type=float, default=6.0, help="corner chamfer, mm (default 6.0)")
    p.add_argument("--outer-inset", type=float, default=0.35, help="Human Kit joint_outer_inset")
    p.add_argument("--no-housing", action="store_true", help="split only, do not cut the strap housing")
    p.add_argument("--clearance", type=float, default=2.0,
                   help="minimum gap between the housing and any case opening or edge, mm (default 2.0)")
    p.add_argument("--edge-margin", type=float, default=2.0,
                   help="minimum margin from the usable backplate edge, mm (default 2.0)")
    p.add_argument("--joint-inset", type=float, default=3.2,
                   help="width of the interlock band at the backplate edge that must stay "
                        "uncut; matches joint_inner_inset in the Human Kit (default 3.2)")
    p.add_argument("--strap-band-width", type=float, default=None,
                   help="override strap_band_width when the housing must be narrowed")
    p.add_argument("--track-center-spacing", type=float, default=None,
                   help="override track_center_spacing when the housing must be narrowed")
    p.add_argument("--housing-x", type=float, default=None,
                   help="force the housing centre X instead of using the automatic placement")
    p.add_argument("--no-rotate", action="store_true",
                   help="keep the housing's own orientation instead of facing the springs at the camera end")
    p.add_argument("--mirror", default=None,
                   help="copy the two printable parts into the Human Kit's Examples/ folder "
                        "after the run (e.g. ../Human_Kit/Examples) so both packages ship "
                        "the same example")
    p.add_argument("--keep-intermediates", action="store_true")
    args = p.parse_args(argv)

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = []

    def say(msg):
        print(msg)
        log.append(msg)

    # ---- locate the Human Kit ------------------------------------------
    kit = Path(args.human_kit).resolve() if args.human_kit else Path(__file__).resolve().parents[2] / "Human_Kit"
    cutter_scad = kit / "perimeter_split_negative.scad"
    housing_scad = kit / "strap_housing_negative.scad"
    for f in (cutter_scad, housing_scad):
        if not f.exists():
            raise SystemExit(f"Human Kit file missing: {f}")

    exe = args.openscad or find_openscad()
    say(f"Human Kit   : {kit}")
    say(f"OpenSCAD    : {exe}")

    # ---- read + repair --------------------------------------------------
    src = Path(args.case)
    if src.suffix.lower() == ".3mf":
        verts, tris = read_3mf(src)
    elif src.suffix.lower() == ".stl":
        verts, tris = read_stl(src)
    else:
        raise SystemExit("case must be .3mf or .stl")
    say(f"case        : {src.name}  {len(verts)} verts / {len(tris)} tris")

    verts, tris, rep = repair(verts, tris)
    for w in rep["warnings"]:
        say(f"WARNING     : {w}")
    if rep["non_manifold_edges"] or rep["boundary_edges"]:
        raise SystemExit(f"mesh still not manifold after repair: {rep}")
    say(f"repair      : {len(rep['collapsed_edges'])} degenerate edges collapsed, mesh is manifold")

    # ---- orientation and measurement -----------------------------------
    back, low_area, high_area = back_face(verts, tris)
    zs = [v[2] for v in verts]
    zmin, zmax = min(zs), max(zs)
    flip = back == zmax
    if flip:
        # back face is at the top: rotate 180 deg about X (mirror Z + reverse winding)
        shifted = [(v[0], v[1], zmax - v[2]) for v in verts]
        tris = [(a, c, b) for a, b, c in tris]
    else:
        # back face already at the bottom: plain translation keeps the winding
        shifted = [(v[0], v[1], v[2] - zmin) for v in verts]
    say(f"back face   : z={back:.2f} (flat area {low_area if back == zmin else high_area:.0f} mm2)"
        + ("  [model was upside down, flipped]" if flip else ""))

    caster = Caster(shifted, tris)
    xsb = bbox(shifted)
    cx = (xsb["x"][0] + xsb["x"][1]) / 2
    cy = (xsb["y"][0] + xsb["y"][1]) / 2

    # panel thickness: median of the first wall over a coarse grid inside the outline
    probes = []
    for fx in (-0.3, 0.0, 0.3):
        for fy in (-0.3, 0.0, 0.3):
            t = caster.first_wall(cx + fx * xsb["size"][0], cy + fy * xsb["size"][1])
            if t:
                probes.append(round(t, 3))
    if not probes:
        raise SystemExit("could not measure the back-panel thickness (no rays hit material)")
    probes.sort()
    thickness = probes[len(probes) // 2]
    say(f"panel       : {thickness:.2f} mm thick (probes {probes})")

    # outline: footprint of a thin slab just above the back face
    slab = [v for v in shifted if v[2] <= min(thickness, 0.5) + 1e-6]
    if len(slab) < 3:
        slab = shifted
    outline = {
        "width": round(max(v[0] for v in slab) - min(v[0] for v in slab), 2),
        "height": round(max(v[1] for v in slab) - min(v[1] for v in slab), 2),
        "center_x": round((max(v[0] for v in slab) + min(v[0] for v in slab)) / 2, 2),
        "center_y": round((max(v[1] for v in slab) + min(v[1] for v in slab)) / 2, 2),
    }
    say(f"outline     : {outline['width']} x {outline['height']} mm at "
        f"({outline['center_x']}, {outline['center_y']})")

    fitted, attempts = fit_outline(caster, outline, thickness, args.chamfer, args.outer_inset)
    say(f"fitted      : {fitted['width']} x {fitted['height']} mm "
        f"(worst wall on the cut ring {fitted['max_wall_mm']:.2f} mm)")

    # ---- write the normalised case -------------------------------------
    case_stl = out / "01_case_normalised.stl"
    write_stl(case_stl, shifted, tris)

    # ---- render the Human Kit cutter -----------------------------------
    work = out / "_work"
    work.mkdir(exist_ok=True)
    cutter_stl = out / "02_cutter.stl"
    run_openscad(exe, f'include <{cutter_scad.as_posix()}>;', cutter_stl, work, defines={
        "split_boundary_width": fitted["width"],
        "split_boundary_height": fitted["height"],
        "split_corner_chamfer": args.chamfer,
        "backplate_thickness": round(thickness, 3),
        "split_center_x": outline["center_x"],
        "split_center_y": outline["center_y"],
        "base_z": 0,
    })
    say(f"cutter      : {cutter_stl.name}")

    # ---- split ----------------------------------------------------------
    split_stl = out / "03_split.stl"
    run_openscad(exe, f'difference() {{ import("{case_stl.as_posix()}"); '
                      f'import("{cutter_stl.as_posix()}"); }}', split_stl, work)
    sv, st = read_stl(split_stl)
    parts = components(sv, st)
    parts.sort(key=lambda p: -bbox(p["verts"])["size"][2])
    say(f"split       : {len(parts)} parts")

    if len(parts) != 2:
        detail = ", ".join(f"{bbox(p_['verts'])['size']}" for p_ in parts)
        raise SystemExit(
            f"expected 2 parts after the cut, got {len(parts)} ({detail}).\n"
            "The cut ring probably still runs into a wall or the outline is too small.\n"
            "Try --chamfer or check the case for features bridging the cut."
        )

    perimeter, backplate = parts[0], parts[1]
    per_stl = out / "04_perimeter.stl"
    bp_stl = out / "05_backplate.stl"
    write_stl(per_stl, perimeter["verts"], perimeter["tris"])
    write_stl(bp_stl, backplate["verts"], backplate["tris"])
    pv, pt = bbox(perimeter["verts"]), bbox(backplate["verts"])
    say(f"  perimeter : {pv['size'][0]:.2f} x {pv['size'][1]:.2f} x {pv['size'][2]:.2f} mm, "
        f"{triangle_volume(perimeter['verts'], perimeter['tris']):.0f} mm3")
    say(f"  backplate : {pt['size'][0]:.2f} x {pt['size'][1]:.2f} x {pt['size'][2]:.2f} mm, "
        f"{triangle_volume(backplate['verts'], backplate['tris']):.0f} mm3")

    # ---- strap housing ---------------------------------------------------
    housing_info = None
    if not args.no_housing:
        housing_stl = out / "06_housing_negative.stl"
        hdefs = {"backplate_thickness": round(thickness, 3)}
        if args.strap_band_width:
            hdefs["strap_band_width"] = args.strap_band_width
        if args.track_center_spacing:
            hdefs["track_center_spacing"] = args.track_center_spacing
        run_openscad(exe, f'include <{housing_scad.as_posix()}>;', housing_stl, work, defines=hdefs)
        hv, ht = read_stl(housing_stl)
        hb = bbox(hv)
        hx0, hx1 = hb["x"]
        hy0, hy1 = hb["y"]

        # The housing is a negative volume: it must not touch a hole the phone
        # already needs. Find every through-opening in the back panel first.
        op = find_openings(caster, pt, thickness / 2)
        for i, o in enumerate(op):
            say(f"opening {i}   : x {o['x0']:.2f}..{o['x1']:.2f}  y {o['y0']:.2f}..{o['y1']:.2f}"
                f"  ({o['x1'] - o['x0']:.1f} x {o['y1'] - o['y0']:.1f} mm)")
        if not op:
            say("openings    : none detected - check this is really a phone case")

        # The outer `joint_inset` of the backplate belongs to the vertical-capture
        # interlock; cutting into it removes the TPU tongue's retaining rail. The
        # clear area starts that far in, plus the normal margin.
        usable_inset = args.edge_margin + args.joint_inset
        if args.housing_x is not None:
            place = {"x_centre": args.housing_x, "y_centre": (pt["y"][0] + pt["y"][1]) / 2,
                     "rotate_180": False if args.no_rotate else True,
                     "camera_end": "manual", "min_clearance": None, "opening_gaps": []}
            say(f"placement   : forced by --housing-x at x={args.housing_x}")
        else:
            place = place_housing(hb, pt, op, args.clearance, usable_inset,
                                  springs_local_end="high")
            if args.no_rotate:
                place["rotate_180"] = False
            say(f"clear zone  : backplate inset by {usable_inset:.1f} mm "
                f"({args.joint_inset} interlock + {args.edge_margin} margin)")
            say(f"camera end  : {place['camera_end']}  ->  springs at the "
                f"{'top' if place['camera_end'] == 'low' else 'bottom'}, "
                f"housing rotated {180 if place['rotate_180'] else 0} deg")

        rot = place["rotate_180"]
        W, H = hb["size"][0], hb["size"][1]
        x0 = place["x_centre"] - W / 2
        y0 = place["y_centre"] - H / 2
        tx = (x0 + hx1) if rot else (x0 - hx0)
        ty = (y0 + hy1) if rot else (y0 - hy0)

        # hard guarantee, independent of how the rectangle was chosen
        placed = {"x0": x0, "x1": x0 + W, "y0": y0, "y1": y0 + H}
        hits_open = [i for i, o in enumerate(op) if rect_gap(placed, o) == 0.0]
        if hits_open:
            raise SystemExit(
                f"REFUSING: the housing rectangle {placed} overlaps opening(s) {hits_open}. "
                "Nothing is cut. Reposition with --housing-x or narrow the strap.")

        say(f"housing     : {W:.1f} x {H:.1f} mm at x {placed['x0']:.2f}..{placed['x1']:.2f}, "
            f"y {placed['y0']:.2f}..{placed['y1']:.2f}")
        if place.get("min_clearance") is not None:
            say(f"clearance   : {place['min_clearance']} mm to the nearest opening/edge "
                f"(gaps {place['opening_gaps']})")

        xform = (f"translate([{tx:.4f}, {ty:.4f}, 0]) " +
                 ("rotate([0,0,180]) " if rot else "") +
                 f'import("{housing_stl.as_posix()}");')
        cut_stl = out / "07_backplate_with_tracks.stl"
        run_openscad(exe, f'difference() {{ import("{bp_stl.as_posix()}"); {xform} }}', cut_stl, work)
        cv, ct = read_stl(cut_stl)
        cparts = components(cv, ct)
        removed = triangle_volume(backplate["verts"], backplate["tris"]) - triangle_volume(cv, ct)
        housing_info = {
            "negative_size": hb["size"],
            "placement": place,
            "placed_rect": placed,
            "openings": op,
            "clearance_to_openings": place.get("opening_gaps"),
            "transform": {"translate": [round(tx, 3), round(ty, 3), 0], "rotate_z_deg": 180 if rot else 0},
            "material_removed_mm3": round(removed, 1),
            "parts_after_cut": len(cparts),
        }
        say(f"removed     : {removed:.0f} mm3, {len(cparts)} part(s)")
        if len(cparts) != 1:
            say("WARNING     : the housing cut broke the backplate into pieces")
        shutil.move(str(cut_stl), str(out / "05_backplate.stl"))

    # ---- report ----------------------------------------------------------
    report = {
        "input": {"file": src.name, "bytes": src.stat().st_size,
                  "verts": len(verts), "tris": len(tris)},
        "repair": rep,
        "measurement": {
            "back_face_z": round(back, 3),
            "back_face_area_mm2": round(low_area if back == zmin else high_area, 1),
            "flipped": flip,
            "panel_thickness_mm": thickness,
            "thickness_probes": probes,
            "outline_measured": outline,
            "outline_fitted": fitted,
            "fit_attempts": attempts,
        },
        "split": {
            "parts": len(parts),
            "perimeter": {"bbox": pv, "volume_mm3": round(triangle_volume(perimeter["verts"], perimeter["tris"]), 1)},
            "backplate": {"bbox": pt, "volume_mm3": round(triangle_volume(backplate["verts"], backplate["tris"]), 1)},
            "volume_conservation": round(
                triangle_volume(perimeter["verts"], perimeter["tris"])
                + triangle_volume(backplate["verts"], backplate["tris"]), 1),
            "input_volume_mm3": round(triangle_volume(verts, tris), 1),
        },
        "housing": housing_info,
        "outputs": sorted(p.name for p in out.iterdir() if p.is_file()),
        "assumptions": [
            "chamfer is a parameter (default 6.0 mm), not measured",
            "the strap is the Human Kit's 143.5 mm reference strap unless you regenerate it",
            "only the back panel is scanned for openings; side, button and port keep-outs are not",
            "openings are approximated by their bounding rectangles, so reported clearances are conservative",
            "the outline is auto-fitted to the flat back panel, which may be smaller than the visible outline",
        ],
        "log": log,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    md = [
        "# Agent run report",
        "",
        f"- input: `{src.name}` - {len(verts)} verts, {len(tris)} tris",
        f"- back face: z = {back:.2f} mm{' (flipped)' if flip else ''}",
        f"- back-panel thickness: **{thickness:.2f} mm**",
        f"- measured outline: {outline['width']} x {outline['height']} mm",
        f"- fitted outline: **{fitted['width']} x {fitted['height']} mm** "
        f"(worst wall on the cut ring {fitted['max_wall_mm']:.2f} mm)",
        f"- split into **{len(parts)} parts**",
        f"- perimeter: {pv['size'][0]:.2f} x {pv['size'][1]:.2f} x {pv['size'][2]:.2f} mm, "
        f"{report['split']['perimeter']['volume_mm3']:.0f} mm3",
        f"- backplate: {pt['size'][0]:.2f} x {pt['size'][1]:.2f} x {pt['size'][2]:.2f} mm, "
        f"{report['split']['backplate']['volume_mm3']:.0f} mm3",
    ]
    if housing_info:
        pl = housing_info["placement"]
        md += [
            "",
            "## Strap housing placement",
            "",
            f"- openings found in the back panel: **{len(housing_info['openings'])}**",
        ]
        for i, o in enumerate(housing_info["openings"]):
            md.append(f"  - opening {i}: x {o['x0']:.2f}..{o['x1']:.2f}, "
                      f"y {o['y0']:.2f}..{o['y1']:.2f} "
                      f"({o['x1'] - o['x0']:.1f} x {o['y1'] - o['y0']:.1f} mm)")
        r = housing_info["placed_rect"]
        md += [
            f"- camera end of the phone: **{pl.get('camera_end')}**",
            f"- housing rotated: {housing_info['transform']['rotate_z_deg']} deg "
            f"(springs toward the camera end)",
            f"- housing rect: x {r['x0']:.2f}..{r['x1']:.2f}, y {r['y0']:.2f}..{r['y1']:.2f}",
            f"- clearance to openings: {housing_info['clearance_to_openings']}",
            f"- material removed: {housing_info['material_removed_mm3']:.0f} mm3, "
            f"{housing_info['parts_after_cut']} part(s) after the cut",
        ]
    md += ["", "## Assumptions", ""] + [f"- {a}" for a in report["assumptions"]]
    md += ["", "## Log", "", "```"] + log + ["```", ""]
    (out / "report.md").write_text("\n".join(md))

    if not args.keep_intermediates:
        shutil.rmtree(work, ignore_errors=True)

    # The Human Kit is a standalone download with one flat Examples folder, so it
    # gets the two case-specific printable parts under friendly names and nothing
    # else. Its own strap and cutter never change from a case run. Mirror rather
    # than symlink: each package must work alone.
    if args.mirror:
        target = Path(args.mirror).resolve()
        target.mkdir(parents=True, exist_ok=True)
        for src_name, dst_name in MIRROR_MAP.items():
            src = out / src_name
            if not src.exists():
                say(f"WARNING     : {src_name} missing, not mirrored")
                continue
            shutil.copy2(src, target / dst_name)
            if (target / dst_name).stat().st_size != src.stat().st_size:
                say(f"WARNING     : {dst_name} size differs after copy")
        say(f"mirrored    : {len(MIRROR_MAP)} parts -> {target}")

    say(f"\ndone        : {out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
