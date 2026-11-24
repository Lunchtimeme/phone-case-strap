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

def read_3mf(path):
    """Return (verts, tris) from a 3MF container holding exactly one mesh object.

    Parsed as XML rather than by regex, with the model's `unit` attribute and the
    build-item transform applied. Anything this cannot represent as a single
    closed mesh is refused with an explicit message - a wrong mesh is worse than
    a clear error.
    """
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".model")]
        if not names:
            raise SystemExit(f"{path}: no 3dmodel.model inside the 3MF")
        raw = z.read(names[0])

    def local(tag):
        return tag.rsplit("}", 1)[-1]

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise SystemExit(f"{path}: 3MF model XML is malformed: {e}")
    if local(root.tag) != "model":
        raise SystemExit(f"{path}: unexpected root element <{local(root.tag)}>")

    UNIT_MM = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0,
               "inch": 25.4, "foot": 304.8, "meter": 1000.0}
    unit = root.get("unit", "millimeter")
    if unit not in UNIT_MM:
        raise SystemExit(f"{path}: unsupported 3MF unit {unit!r} "
                         f"(known: {', '.join(sorted(UNIT_MM))})")
    scale = UNIT_MM[unit]

    objects = [el for el in root.iter() if local(el.tag) == "object"]
    comps = [el for el in root.iter() if local(el.tag) == "component"]
    if len(objects) != 1 or comps:
        raise SystemExit(
            f"{path}: this 3MF has {len(objects)} objects and {len(comps)} components. "
            "Export it as a single body first (the agent can only boolean a single closed mesh)."
        )

    obj = objects[0]
    mesh = next((el for el in obj.iter() if local(el.tag) == "mesh"), None)
    if mesh is None:
        raise SystemExit(f"{path}: object has no <mesh>")
    vel = next((el for el in mesh.iter() if local(el.tag) == "vertices"), None)
    tel = next((el for el in mesh.iter() if local(el.tag) == "triangles"), None)
    if vel is None or tel is None:
        raise SystemExit(f"{path}: mesh is missing its <vertices> or <triangles>")

    try:
        def num(el, attr):
            val = el.get(attr)
            if val is None:
                raise SystemExit(f"{path}: <{local(el.tag)}> is missing its {attr} attribute")
            return float(val)

        # Raw model units: the unit scale is applied once, at the end, after the
        # build transform has been applied in model space.
        verts = [(num(v, "x"), num(v, "y"), num(v, "z"))
                 for v in vel if local(v.tag) == "vertex"]
        tris = [(int(num(t, "v1")), int(num(t, "v2")), int(num(t, "v3")))
                for t in tel if local(t.tag) == "triangle"]
    except ValueError as e:
        raise SystemExit(f"{path}: malformed vertex/triangle data: {e}")
    if not verts or not tris:
        raise SystemExit(f"{path}: no mesh data found")
    if max(max(t) for t in tris) >= len(verts):
        raise SystemExit(f"{path}: triangles reference vertices that do not exist")

    # Build items place the object in the scene. The transform maps object space
    # to build space in model units, so it is applied before the unit scale.
    items = [el for el in root.iter() if local(el.tag) == "item"]
    xform = None
    if len(items) > 1:
        raise SystemExit(f"{path}: {len(items)} build items - export a single object")
    if items:
        tfs = items[0].get("transform")
        if tfs:
            nums = [float(n) for n in tfs.split()]
            if len(nums) != 12:
                raise SystemExit(f"{path}: build transform has {len(nums)} values, expected 12")
            xform = tuple(nums)

    if xform:
        a, b, c, d, e, f, g, h, i, tx, ty, tz = xform
        verts = [(x * a + y * d + z * g + tx,
                  x * b + y * e + z * h + ty,
                  x * c + y * f + z * i + tz) for x, y, z in verts]

    return [(x * scale, y * scale, z * scale) for x, y, z in verts], tris


def read_stl(path):
    """Return (verts, tris) from a binary or ASCII STL.

    Binary is detected from the declared triangle count and the expected file
    length, not from the 80-byte header - headers are arbitrary and a binary file
    may legitimately begin with the word `solid`.
    """
    b = Path(path).read_bytes()
    if len(b) < 84:
        raise SystemExit(f"{path}: {len(b)} bytes is too short to be an STL")

    n = struct.unpack("<I", b[80:84])[0]
    if 84 + 50 * n == len(b) and n > 0:
        verts, tris = [], []
        for i in range(n):
            d = struct.unpack("<12fH", b[84 + 50 * i:134 + 50 * i])
            base = len(verts)
            verts += [(d[3], d[4], d[5]), (d[6], d[7], d[8]), (d[9], d[10], d[11])]
            tris.append((base, base + 1, base + 2))
        return verts, tris

    head = b.lstrip()[:5].lower()
    if head == b"solid":
        import re
        v = re.findall(rb"vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)", b)
        if v and len(v) % 3 == 0:
            verts = [(float(x), float(y), float(z)) for x, y, z in v]
            tris = [(i, i + 1, i + 2) for i in range(0, len(verts), 3)]
            return verts, tris

    raise SystemExit(
        f"{path}: not a valid STL.\n"
        f"  the binary header declares {n} triangles, which needs {84 + 50 * n} bytes, "
        f"but the file is {len(b)} bytes\n"
        f"  and it does not parse as ASCII STL. The file is probably truncated or corrupt."
    )


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

def repair(verts, tris, max_collapse=0.05):
    """Make the mesh edge-manifold, refusing to change the model.

    Exported case models routinely carry a few degenerate edges where two
    surfaces meet. Only edges no longer than `max_collapse` may be collapsed, and
    collapsing one moves a vertex by at most that distance.

    Anything larger is a real defect in the source model, not a rounding
    artefact. Those abort instead of being quietly welded - silently moving
    geometry on someone's phone case is not a repair, it is a redesign.
    """
    before_box = bbox(verts)
    before_vol = triangle_volume(verts, tris)
    verts, tris = weld_mesh(verts, tris)
    report: dict = {
        "collapsed_edges": [], "warnings": [],
        "max_collapse_mm": max_collapse,
        "before": {"bbox": before_box, "volume_mm3": round(before_vol, 3)},
    }

    for _ in range(6):
        em = edge_map(tris)
        bad = [(e, f) for e, f in em.items() if len(f) > 2]
        if not bad:
            break
        merge = {}
        for (v0, v1), faces in bad:
            d = math.dist(verts[v0], verts[v1])
            if d > max_collapse:
                raise SystemExit(
                    f"non-manifold edge of {d:.3f} mm shared by {len(faces)} faces - larger "
                    f"than the {max_collapse} mm repair tolerance.\n"
                    "That is a real defect in the source model, not a rounding artefact. Repair "
                    "it in your mesh/CAD tool and re-export; the agent will not move geometry "
                    "on your case to work around it.\n"
                    "If the defect is genuinely negligible you can raise the tolerance with "
                    "--repair-tolerance, and the report will record what was moved."
                )
            report["collapsed_edges"].append(
                {"vertices": [v0, v1], "faces": len(faces), "distance_mm": round(d, 4)})
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

    after_box = bbox(verts)
    report["after"] = {"bbox": after_box, "volume_mm3": round(triangle_volume(verts, tris), 3)}
    report["max_displacement_mm"] = max((e["distance_mm"] for e in report["collapsed_edges"]),
                                        default=0.0)
    report["volume_change_mm3"] = round(report["after"]["volume_mm3"] - report["before"]["volume_mm3"], 3)
    report["displaced_mm"] = round(max(
        abs(a - b) for key in ("x", "y", "z")
        for a, b in zip(before_box[key], after_box[key])), 4)
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


def validate_part(verts, tris, label):
    """Hard acceptance gate for a mesh the pipeline is about to publish.

    Connectivity alone does not make a part printable: a single component can
    still be an open surface or fold through itself. Anything that fails here
    stops the run instead of being reported as a successful build.
    """
    _, welded = weld_mesh(verts, tris)
    em = edge_map(welded)
    boundary = sum(1 for f in em.values() if len(f) == 1)
    nonman = sum(1 for f in em.values() if len(f) > 2)
    parts = len(components(verts, tris))
    vol = triangle_volume(verts, tris)

    problems = []
    if boundary:
        problems.append(f"{boundary} boundary edges (not watertight)")
    if nonman:
        problems.append(f"{nonman} non-manifold edges")
    if parts != 1:
        problems.append(f"{parts} disconnected components")
    if vol <= 0:
        problems.append(f"volume is {vol:.1f} mm3")
    if problems:
        raise SystemExit(
            f"VALIDATION FAILED - {label}: {', '.join(problems)}\n"
            "Nothing has been published as a successful build. Intermediate files "
            "are left in the output folder so you can see what happened."
        )
    return {"label": label, "components": parts, "volume_mm3": round(vol, 1),
            "watertight": True, "manifold": True}


# --------------------------------------------------------------------------
# main pipeline
# --------------------------------------------------------------------------

def material_at(caster, px, py, z):
    """True if the point is inside solid material at height z (ray parity)."""
    return sum(1 for h in caster.hits(px, py) if h < z) % 2 == 1


def find_openings(caster, backplate_bbox, z_probe, step=0.6, margin=1.0, min_size=1.0):
    """Through-openings in the back panel: camera, flash, sensors, pop-socket.

    These are where the phone's own hardware sits, so the strap housing must never
    overlap them - the housing is a negative volume, and carving into an existing
    hole produces a part that cannot be assembled.

    A panel with no openings at all is legitimate: not every device has a camera
    behind the case. So an empty result is a fact to report, not an error - the
    caller decides what placement is safe without one.
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
        xs = [p_[0] for p_ in comp]
        ys = [p_[1] for p_ in comp]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        # A single sample is as likely to be a thin wall as a hole; require a
        # cluster, and a cluster wide enough to be a real opening.
        if len(comp) < 3 or max(w, h) + step < min_size:
            continue
        # The sampled points lie *inside* the hole, so their bounding box
        # understates it by up to one grid step per side. Expand by half a step:
        # the reported opening is then centred on the true edge instead of
        # always optimistic, and the clearances derived from it stay honest.
        pad = step / 2
        out.append({"x0": round(min(xs) - pad, 2), "x1": round(max(xs) + pad, 2),
                    "y0": round(min(ys) - pad, 2), "y1": round(max(ys) + pad, 2),
                    "samples": len(comp), "edge_uncertainty_mm": round(pad, 2)})
    out.sort(key=lambda o: -((o["x1"] - o["x0"]) * (o["y1"] - o["y0"])))
    return out


def rect_gap(a, b):
    """Shortest distance between two axis-aligned rectangles; 0 if they touch."""
    dx = max(a["x0"] - b["x1"], b["x0"] - a["x1"], 0.0)
    dy = max(a["y0"] - b["y1"], b["y0"] - a["y1"], 0.0)
    return math.hypot(dx, dy)


def check_placement(rect, openings, backplate_bbox, clearance, edge_inset):
    """Evaluate one candidate rectangle against every placement constraint.

    Kept separate so a manually supplied position is checked by exactly the same
    rules as an automatically chosen one.
    """
    bx0, bx1 = backplate_bbox["x"]
    by0, by1 = backplate_bbox["y"]
    gaps = [rect_gap(rect, o) for o in openings]
    opening_worst = min(gaps) if gaps else math.inf
    edge_gap = min(rect["x0"] - bx0, bx1 - rect["x1"],
                   rect["y0"] - by0, by1 - rect["y1"])

    problems = []
    if openings and opening_worst + 1e-9 < clearance:
        problems.append(f"opening clearance {opening_worst:.2f} mm is under {clearance} mm")
    if edge_gap + 1e-9 < edge_inset:
        problems.append(f"interlock/edge clearance {edge_gap:.2f} mm is under {edge_inset} mm")
    return {
        "opening_clearance": round(opening_worst, 2) if gaps else None,
        "edge_clearance": round(edge_gap, 2),
        "opening_gaps": [round(g, 2) for g in gaps],
        "problems": problems, "ok": not problems,
    }


def infer_camera_end(openings, backplate_bbox):
    """Which end of the model the camera is on, from the largest opening."""
    if not openings:
        return None
    biggest = openings[0]
    cam_y = (biggest["y0"] + biggest["y1"]) / 2
    return "low" if cam_y < (backplate_bbox["y"][0] + backplate_bbox["y"][1]) / 2 else "high"


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


def place_housing(housing_bbox, backplate_bbox, openings, clearance, edge_inset,
                  camera_end=None, min_offset=6.0, springs_local_end="high"):
    """Choose where the housing goes and which way round it faces.

    Three rules, none of which may be traded against another:

    1. **Offset it from the centreline.** The kickstand leans at two angles
       because the strap is off-centre: the standing loop ends up nearer one edge
       of the case than the other, so it can rest at two different pitches.
       Centred, it stands at one. On a device with a camera cluster the offset
       keeps the housing out of the openings as well.
    2. **The spring/detent end faces the camera end of the phone** - the top, as
       a person holds it. With no openings to measure there is nothing to infer
       this from, so the caller's assumption is used and reported as assumed.
    3. **Stay clear of the perimeter interlock by `edge_inset` on all four
       sides.** That is a stricter requirement than the clearance to openings and
       is tracked separately.

    Returns a placement dict, or raises SystemExit with the numbers needed to
    decide what to do instead (narrow the strap, shorten it, or relax clearance).
    """
    W, H = housing_bbox["size"][0], housing_bbox["size"][1]
    bx0, bx1 = backplate_bbox["x"]
    by0, by1 = backplate_bbox["y"]
    bcx = (bx0 + bx1) / 2

    inferred = infer_camera_end(openings, backplate_bbox)
    cam = camera_end or inferred or "low"
    cam_source = "given" if camera_end else ("detected" if inferred else "assumed")

    rotate = (cam == "low" and springs_local_end == "high") or \
             (cam == "high" and springs_local_end == "low")

    # Y: centred by preference; on a short backplate only the extremes fit.
    y_lo, y_hi = by0 + edge_inset, by1 - edge_inset
    if y_hi - y_lo < H - 1e-9:
        raise SystemExit(
            f"housing is {H:.1f} mm tall but the backplate leaves only "
            f"{y_hi - y_lo:.1f} mm once the {edge_inset:.1f} mm interlock margin is "
            "respected at both ends.\n"
            "The strap is longer than this case can carry. Shorten strap_length in "
            "strap_system_parameters.scad and regenerate both parts.")
    y_candidates = [(by0 + by1) / 2, y_lo + H / 2, y_hi - H / 2]

    lo = bx0 + edge_inset + W / 2
    hi = bx1 - edge_inset - W / 2
    if hi < lo - 1e-9:
        raise SystemExit(
            f"housing {W:.1f} mm wide does not fit inside the backplate "
            f"({bx1 - bx0:.1f} mm) once the {edge_inset:.1f} mm interlock margin is "
            "respected on both sides.\nNarrow the strap before building.")
    free = hi - lo

    # A fixed grid cannot land on the constraint boundary - it stops one step
    # short and reports a false failure. Test the exact positions where the
    # housing just clears an opening, plus the offset positions and a sweep.
    candidates = [lo, hi, (lo + hi) / 2, bcx - min_offset, bcx + min_offset]
    for o in openings:
        candidates.append(o["x1"] + clearance + W / 2)
        candidates.append(o["x0"] - clearance - W / 2)
    x = lo
    while x <= hi + 1e-9:
        candidates.append(x)
        x += 0.5

    best, best_any = None, None
    for yc in y_candidates:
        for xc in candidates:
            xc = max(lo, min(hi, xc))
            rect = {"x0": xc - W / 2, "x1": xc + W / 2,
                    "y0": yc - H / 2, "y1": yc + H / 2}
            gaps = [rect_gap(rect, o) for o in openings]
            opening_worst = min(gaps) if gaps else math.inf
            edge_gap = min(rect["x0"] - bx0, bx1 - rect["x1"],
                           rect["y0"] - by0, by1 - rect["y1"])
            score = min(opening_worst - clearance, edge_gap - edge_inset)
            rec = {
                "x_centre": round(xc, 2), "y_centre": round(yc, 2),
                "opening_clearance": (round(opening_worst, 2) if gaps else None),
                "edge_clearance": round(edge_gap, 2),
                "offset_from_centre": round(abs(xc - bcx), 2),
                "score": score, "rect": rect,
                "opening_gaps": [round(g, 2) for g in gaps],
            }
            if best_any is None or score > best_any["score"] + 1e-9:
                best_any = rec
            if abs(xc - bcx) + 1e-9 >= min_offset and (best is None or score > best["score"] + 1e-9):
                best = rec

    offset_satisfied = best is not None
    if not offset_satisfied:
        best = best_any

    if best["score"] < -1e-9:
        narrowest = largest_free_width(openings, backplate_bbox,
                                       (best["y_centre"] - H / 2, best["y_centre"] + H / 2),
                                       clearance, edge_inset)
        raise SystemExit(
            f"no placement satisfies both constraints.\n"
            f"  housing            : {W:.1f} x {H:.1f} mm\n"
            f"  needed             : {clearance} mm to every opening, "
            f"{edge_inset} mm to the interlock on all four sides\n"
            f"  opening clearance  : {best['opening_clearance']} mm\n"
            f"  edge clearance     : {best['edge_clearance']} mm\n"
            f"  widest housing that fits at {clearance} mm: {narrowest:.1f} mm\n"
            "Decide: narrow the strap (lower strap_band_width and strap_ear_width in "
            "strap_system_parameters.scad and regenerate both parts), shorten it, or "
            "lower --clearance if the remaining bridge is genuinely thick enough."
        )

    out = dict(best)
    out.update({
        "camera_end": cam, "camera_end_source": cam_source,
        "rotate_180": rotate, "springs_local_end": springs_local_end,
        "offset_satisfied": offset_satisfied,
        "min_offset_target": min_offset,
        "free_x_range": [round(lo, 2), round(hi, 2)], "free_x_width": round(free, 2),
        "constraints": {"opening_clearance_mm": clearance,
                        "interlock_edge_inset_mm": edge_inset,
                        "min_offset_from_centre_mm": min_offset},
    })
    return out


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
                   help="minimum gap between the housing and any case opening, mm (default 2.0)")
    p.add_argument("--edge-margin", type=float, default=2.0,
                   help="margin beyond the interlock band, mm (default 2.0)")
    p.add_argument("--joint-inset", type=float, default=3.2,
                   help="width of the interlock band at the backplate edge that must stay "
                        "uncut; matches joint_inner_inset in the Human Kit (default 3.2)")
    p.add_argument("--min-offset", type=float, default=6.0,
                   help="how far the housing centre must sit off the backplate centreline, mm "
                        "(default 6.0). The offset is what gives the kickstand its two angles")
    p.add_argument("--camera-end", choices=("low", "high"), default=None,
                   help="which end of the model the phone's camera is on. Detected from the "
                        "openings when possible; give it explicitly for a case with no "
                        "openings (a device without a camera)")
    p.add_argument("--strap-band-width", type=float, default=None,
                   help="narrow the strap band, mm. Applied to the strap AND the housing "
                        "together; ear spacing, track spacing and window follow from it")
    p.add_argument("--strap-ear-width", type=float, default=None,
                   help="change the strap ear width, mm. Applied to the strap AND the housing")
    p.add_argument("--repair-tolerance", type=float, default=0.05,
                   help="largest non-manifold edge the mesh repair may collapse, mm "
                        "(default 0.05). Larger defects abort the run")
    p.add_argument("--housing-x", type=float, default=None,
                   help="force the housing centre X. The position is still validated against "
                        "every opening, the interlock and the backplate edge")
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
    # The pack carries its own copy of the two SCAD files it drives, so it runs
    # as a standalone folder. An adjacent Human Kit is used when present; the
    # two copies are compared so a stale bundle is visible rather than silent.
    pack = Path(__file__).resolve().parents[1]
    if args.human_kit:
        kit = Path(args.human_kit).resolve()
        kit_source = "--human-kit"
    elif (pack / "human_kit").is_dir():
        kit = pack / "human_kit"
        kit_source = "bundled"
    else:
        kit = pack.parent / "Human_Kit"
        kit_source = "sibling Human_Kit"
    cutter_scad = kit / "perimeter_split_negative.scad"
    housing_scad = kit / "strap_housing_negative.scad"
    missing = [f for f in (cutter_scad, housing_scad) if not f.exists()]
    if missing:
        raise SystemExit(
            "required SCAD file missing:\n"
            + "".join(f"  {f}\n" for f in missing)
            + f"  (looked in {kit}, chosen by {kit_source})\n"
            "The Agent Pack expects its own copy at Agent_Pack/human_kit/. "
            "Pass --human-kit PATH if your Human Kit lives somewhere else."
        )

    kit_drift = None
    sibling = pack.parent / "Human_Kit"
    if kit_source == "bundled" and sibling.is_dir():
        import hashlib
        for name in ("perimeter_split_negative.scad", "strap_housing_negative.scad",
                     "strap_system_parameters.scad"):
            a, b = kit / name, sibling / name
            if a.exists() and b.exists() and \
                    hashlib.sha256(a.read_bytes()).hexdigest() != hashlib.sha256(b.read_bytes()).hexdigest():
                kit_drift = f"{name} differs between the bundle and ../Human_Kit"

    exe = args.openscad or find_openscad()
    say(f"Human Kit   : {kit}  ({kit_source})")
    if kit_drift:
        say(f"WARNING     : {kit_drift}")
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

    verts, tris, rep = repair(verts, tris, max_collapse=args.repair_tolerance)
    for w in rep["warnings"]:
        say(f"WARNING     : {w}")
    if rep["non_manifold_edges"] or rep["boundary_edges"]:
        raise SystemExit(f"mesh still not manifold after repair: {rep}")
    say(f"repair      : {len(rep['collapsed_edges'])} degenerate edges collapsed "
        f"(max {rep['max_displacement_mm']:.3f} mm, tolerance {rep['max_collapse_mm']} mm)")

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

    # The split has to remove material - the cutter's kerf - but it can never
    # remove more than the cutter itself contains. If it does, the boolean ran
    # away and the parts are not what the case actually is.
    cutter_v, cutter_t = read_stl(cutter_stl)
    cutter_vol = triangle_volume(cutter_v, cutter_t)
    input_vol = triangle_volume(verts, tris)
    kept_vol = sum(triangle_volume(p_["verts"], p_["tris"]) for p_ in parts)
    removed_by_split = input_vol - kept_vol
    if removed_by_split < -1e-6 or removed_by_split > cutter_vol + 1e-6:
        raise SystemExit(
            "split volume budget violated:\n"
            f"  input                    {input_vol:.1f} mm3\n"
            f"  perimeter + backplate    {kept_vol:.1f} mm3\n"
            f"  removed by the cut       {removed_by_split:.1f} mm3\n"
            f"  the cutter only holds    {cutter_vol:.1f} mm3\n"
            "The parts do not add up to the case minus the kerf, so the boolean did "
            "not do what it was asked to. Nothing has been published."
        )

    validate_part(perimeter["verts"], perimeter["tris"], "perimeter")
    validate_part(backplate["verts"], backplate["tris"], "backplate")

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
    strap_info = None
    if not args.no_housing:
        # One parameter set drives both generators. Whatever narrows the housing
        # narrows the strap with it: both files include the same parameter file,
        # and there the ear spacing, track spacing and window all follow from the
        # band width. Passing different values to the two would be the bug this
        # design exists to prevent.
        hdefs = {"backplate_thickness": round(thickness, 3)}
        if args.strap_band_width is not None:
            hdefs["strap_band_width"] = args.strap_band_width
        if args.strap_ear_width is not None:
            hdefs["strap_ear_width"] = args.strap_ear_width

        housing_stl = out / "06_housing_negative.stl"
        run_openscad(exe, f'include <{housing_scad.as_posix()}>;', housing_stl, work, defines=hdefs)
        hv, ht = read_stl(housing_stl)
        hb = bbox(hv)
        hx0, hx1 = hb["x"]
        hy0, hy1 = hb["y"]

        strap_scad = kit / "strap_parametric.scad"
        strap_stl = out / "08_strap.stl"
        if strap_scad.exists():
            run_openscad(exe, f'include <{strap_scad.as_posix()}>;', strap_stl, work, defines=hdefs)
            stv, stt = read_stl(strap_stl)
            strap_val = validate_part(stv, stt, "strap")
            sb = bbox(stv)
            strap_info = {"file": strap_stl.name, "bbox": sb,
                          "volume_mm3": strap_val["volume_mm3"],
                          "parameters_sent": hdefs}
            say(f"strap       : {sb['size'][0]:.2f} x {sb['size'][1]:.2f} x {sb['size'][2]:.2f} mm, "
                f"{strap_val['volume_mm3']:.0f} mm3 - same parameters as the housing")
        else:
            strap_info = {"file": None, "note": "strap_parametric.scad not found"}
            say("strap       : NOT generated - strap_parametric.scad is missing, so a "
                "resized housing would have no matching strap")

        # The housing is a negative volume: it must not touch a hole the phone
        # already needs. A panel with no openings at all is legitimate.
        op = find_openings(caster, pt, thickness / 2)
        for i, o in enumerate(op):
            say(f"opening {i}   : x {o['x0']:.2f}..{o['x1']:.2f}  y {o['y0']:.2f}..{o['y1']:.2f}"
                f"  ({o['x1'] - o['x0']:.1f} x {o['y1'] - o['y0']:.1f} mm)")
        if not op:
            say("openings    : none in the back panel - placing by offset alone")
            if args.camera_end is None:
                say("              nothing to infer a camera end from, so assuming 'low'; "
                    "pass --camera-end to say which way up the phone goes")

        usable_inset = args.edge_margin + args.joint_inset
        W, H = hb["size"][0], hb["size"][1]

        if args.housing_x is not None:
            # A manual X replaces the search, not the safety checks.
            y_centre = (pt["y"][0] + pt["y"][1]) / 2
            rect = {"x0": args.housing_x - W / 2, "x1": args.housing_x + W / 2,
                    "y0": y_centre - H / 2, "y1": y_centre + H / 2}
            chk = check_placement(rect, op, pt, args.clearance, usable_inset)
            if not chk["ok"]:
                raise SystemExit(
                    f"--housing-x {args.housing_x} is not a safe position:\n"
                    + "\n".join(f"  - {p}" for p in chk["problems"])
                    + "\nA manual position skips the search, not the checks. "
                      "Nothing has been cut.")
            cam_inferred = infer_camera_end(op, pt)
            cam = args.camera_end or cam_inferred or "low"
            bcx = (pt["x"][0] + pt["x"][1]) / 2
            place = {
                "x_centre": args.housing_x, "y_centre": y_centre,
                "rotate_180": (not args.no_rotate) and cam == "low",
                "camera_end": cam,
                "camera_end_source": "given" if args.camera_end else
                                     ("detected" if cam_inferred else "assumed"),
                "offset_from_centre": round(abs(args.housing_x - bcx), 2),
                "offset_satisfied": abs(args.housing_x - bcx) + 1e-9 >= args.min_offset,
                "opening_clearance": chk["opening_clearance"],
                "edge_clearance": chk["edge_clearance"],
                "opening_gaps": chk["opening_gaps"],
            }
            say(f"placement   : forced by --housing-x at x={args.housing_x} (checked)")
        else:
            place = place_housing(hb, pt, op, args.clearance, usable_inset,
                                  camera_end=args.camera_end, min_offset=args.min_offset,
                                  springs_local_end="high")
            if args.no_rotate:
                place["rotate_180"] = False
            say(f"clear zone  : backplate inset by {usable_inset:.1f} mm "
                f"({args.joint_inset} interlock + {args.edge_margin} margin)")
            say(f"camera end  : {place['camera_end']} ({place['camera_end_source']})  ->  "
                f"springs at the {'top' if place['camera_end'] == 'low' else 'bottom'}, "
                f"housing rotated {180 if place['rotate_180'] else 0} deg")
            say(f"offset      : {place['offset_from_centre']} mm off the centreline, "
                f"target {args.min_offset} mm"
                + ("" if place["offset_satisfied"]
                   else "  [cannot be met on this backplate - the kickstand will be a "
                        "one-angle stand]"))

        rot = place["rotate_180"]
        x0 = place["x_centre"] - W / 2
        y0 = place["y_centre"] - H / 2
        tx = (x0 + hx1) if rot else (x0 - hx0)
        ty = (y0 + hy1) if rot else (y0 - hy0)

        # hard guarantee, independent of how the rectangle was chosen
        placed = {"x0": x0, "x1": x0 + W, "y0": y0, "y1": y0 + H}
        final = check_placement(placed, op, pt, args.clearance, usable_inset)
        if not final["ok"]:
            raise SystemExit(
                "REFUSING: the housing would sit at x "
                f"{placed['x0']:.2f}..{placed['x1']:.2f}, y "
                f"{placed['y0']:.2f}..{placed['y1']:.2f} and violates:\n"
                + "\n".join(f"  - {p}" for p in final["problems"])
                + "\nNothing has been cut. Reposition with --housing-x or narrow the strap.")

        say(f"housing     : {W:.1f} x {H:.1f} mm at x {placed['x0']:.2f}..{placed['x1']:.2f}, "
            f"y {placed['y0']:.2f}..{placed['y1']:.2f}")
        say(f"clearance   : {final['opening_clearance']} mm to the nearest opening, "
            f"{final['edge_clearance']} mm to the interlock edge")

        xform = (f"translate([{tx:.4f}, {ty:.4f}, 0]) " +
                 ("rotate([0,0,180]) " if rot else "") +
                 f'import("{housing_stl.as_posix()}");')
        cut_stl = out / "07_backplate_with_tracks.stl"
        run_openscad(exe, f'difference() {{ import("{bp_stl.as_posix()}"); {xform} }}', cut_stl, work)
        cv, ct = read_stl(cut_stl)
        cparts = components(cv, ct)
        removed = triangle_volume(backplate["verts"], backplate["tris"]) - triangle_volume(cv, ct)
        housing_vol = triangle_volume(hv, ht)
        housing_info = {
            "negative_size": hb["size"],
            "placement": place,
            "placed_rect": placed,
            "openings": op,
            "clearance_to_openings": final["opening_gaps"],
            "edge_clearance_mm": final["edge_clearance"],
            "transform": {"translate": [round(tx, 3), round(ty, 3), 0], "rotate_z_deg": 180 if rot else 0},
            "material_removed_mm3": round(removed, 1),
            "parts_after_cut": len(cparts),
        }
        say(f"removed     : {removed:.0f} mm3, {len(cparts)} part(s)")

        if not (0 < removed <= housing_vol + 1e-6):
            raise SystemExit(
                f"housing volume budget violated: the cut removed {removed:.1f} mm3 but the "
                f"negative volume only holds {housing_vol:.1f} mm3.\n"
                "Nothing has been published.")
        # Raises if the cut left more than one piece: a backplate in two halves is
        # not a backplate, and it must not be reported as a successful build.
        validate_part(cv, ct, "backplate with strap housing")

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
        "strap": strap_info,
        "outputs": sorted(p.name for p in out.iterdir() if p.is_file()),
        "assumptions": [
            "chamfer is a parameter (default 6.0 mm), not measured",
            "the strap is generated from the same parameter set as the housing, so the "
            "two always match; strap_TPU.step is only rebuilt by modules/build_agentsafe_housing.py",
            "only the back panel is scanned for through-openings; side ports, buttons, "
            "raised camera islands and rails are not detected",
            "a panel with no openings is allowed - not every device has a camera behind "
            "the case - and is then placed by offset alone",
            "openings are approximated by their bounding rectangles, so reported clearances are conservative",
            "the outline is auto-fitted to the flat back panel, which may be smaller than the visible outline",
            "the kickstand's two angles come from the housing sitting off the centreline; "
            "a case too narrow to offset cannot have both",
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
            f"- camera end of the phone: **{pl.get('camera_end')}** "
            f"({pl.get('camera_end_source', 'n/a')})",
            f"- housing rotated: {housing_info['transform']['rotate_z_deg']} deg "
            f"(springs toward the camera end)",
            f"- housing rect: x {r['x0']:.2f}..{r['x1']:.2f}, y {r['y0']:.2f}..{r['y1']:.2f}",
            f"- offset from the centreline: {pl.get('offset_from_centre')} mm "
            f"(target {args.min_offset} mm) - this is what makes it a two-angle stand",
            f"- clearance to openings: {housing_info['clearance_to_openings']}",
            f"- clearance to the interlock edge: {housing_info['edge_clearance_mm']} mm",
            f"- material removed: {housing_info['material_removed_mm3']:.0f} mm3, "
            f"{housing_info['parts_after_cut']} part(s) after the cut",
        ]
    if strap_info:
        md += ["", "## Strap",
               "",
               f"- generated from the same parameters: "
               f"{strap_info.get('bbox', {}).get('size', 'n/a')} mm, "
               f"{strap_info.get('volume_mm3', 'n/a')} mm3"]
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
        pairs = dict(MIRROR_MAP)
        if strap_info and strap_info.get("file"):
            pairs[strap_info["file"]] = "strap_TPU.stl"
        for src_name, dst_name in pairs.items():
            src = out / src_name
            if not src.exists():
                say(f"WARNING     : {src_name} missing, not mirrored")
                continue
            shutil.copy2(src, target / dst_name)
            if (target / dst_name).stat().st_size != src.stat().st_size:
                say(f"WARNING     : {dst_name} size differs after copy")
        say(f"mirrored    : {len(pairs)} parts -> {target}")
        if args.strap_band_width is not None or args.strap_ear_width is not None:
            say("note        : the strap changed, so Examples/strap_TPU.step is now stale - "
                "rebuild it with Agent_Pack/modules/build_agentsafe_housing.py")

    say(f"\ndone        : {out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
