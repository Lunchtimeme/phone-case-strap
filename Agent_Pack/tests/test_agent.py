"""Regression tests for the agent and the shared SCAD parameters.

Run from Agent_Pack:  python -m unittest discover -s tests -v

These are unit tests around the failure modes that actually bit: a binary STL
whose header says "solid", a 3MF in microns with a build transform, mesh repair
that used to weld anything it found, and placement that used to centre the
housing on a case with no camera. They do not run OpenSCAD.
"""

import importlib.util
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PACK = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


agent = _load("agent_under_test", PACK / "agent" / "agent.py")
scad_params = _load("scad_params", PACK / "modules" / "scad_params.py")

KIT = PACK / "human_kit"
PARAMS = scad_params.Parameters(KIT / "strap_system_parameters.scad")


def write_binary_stl(path, tris, header=b"solid this is a binary file"):
    out = bytearray(header.ljust(80, b"\0")[:80])
    out += struct.pack("<I", len(tris))
    for a, b, c in tris:
        out += struct.pack("<3f", 0, 0, 0)
        for p in (a, b, c):
            out += struct.pack("<3f", *p)
        out += struct.pack("<H", 0)
    Path(path).write_bytes(bytes(out))


def backplate(width=77.4, height=162.24):
    return {"x": [0.0, width], "y": [0.0, height], "size": [width, height, 2.8]}


def housing(w=32.4, h=145.7):
    return {"size": [w, h, 3.4]}


class TestInputParsing(unittest.TestCase):
    def test_binary_stl_whose_header_says_solid(self):
        """The 80-byte header is arbitrary; a binary STL may start with 'solid'."""
        tri = ((0, 0, 0), (10, 0, 0), (0, 10, 0))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "case.stl"
            write_binary_stl(p, [tri])
            verts, tris = agent.read_stl(p)
        self.assertEqual(len(tris), 1)
        self.assertEqual(len(verts), 3)
        self.assertAlmostEqual(max(v[0] for v in verts), 10.0)

    def test_truncated_stl_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "short.stl"
            p.write_bytes(b"\0" * 80 + struct.pack("<I", 5) + b"\0" * 20)
            with self.assertRaises(SystemExit) as ctx:
                agent.read_stl(p)
        self.assertIn("truncated or corrupt", str(ctx.exception))

    def test_3mf_units_and_build_transform(self):
        """Micron units scale to mm, and the transform applies before scaling."""
        model = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="micron" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources>
  <object id="1" type="model">
   <mesh>
    <vertices>
     <vertex x="1000" y="0" z="0"/>
     <vertex x="2000" y="0" z="0"/>
     <vertex x="0" y="1000" z="0"/>
    </vertices>
    <triangles><triangle v1="0" v2="1" v3="2"/></triangles>
   </mesh>
  </object>
 </resources>
 <build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 5000 0 0"/></build>
</model>"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "case.3mf"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("3D/3dmodel.model", model)
            verts, tris = agent.read_3mf(p)
        self.assertEqual(len(tris), 1)
        xs = sorted(v[0] for v in verts)
        # 1000 micron + 5000 micron translation = 6 mm, not 5.001 mm
        self.assertAlmostEqual(xs[0], 5.0, places=6)
        self.assertAlmostEqual(xs[2], 7.0, places=6)


class TestRepair(unittest.TestCase):
    def _nonmanifold(self, gap):
        v0, v1 = (0.0, 0.0, 0.0), (gap, 0.0, 0.0)
        verts = [v0, v1, (0, 10, 0), (0, -10, 0), (10, 0, 5), (-10, 0, 5)]
        tris = [(0, 1, 2), (1, 0, 3), (0, 1, 4), (1, 0, 5)]
        return verts, tris

    def test_small_defect_is_collapsed_and_recorded(self):
        verts, tris = self._nonmanifold(0.02)
        _, _, rep = agent.repair(verts, tris, max_collapse=0.05)
        self.assertGreaterEqual(len(rep["collapsed_edges"]), 1)
        self.assertLessEqual(rep["max_displacement_mm"], 0.05)
        self.assertIn("before", rep)
        self.assertIn("after", rep)

    def test_large_defect_aborts_instead_of_being_welded(self):
        verts, tris = self._nonmanifold(1.0)
        with self.assertRaises(SystemExit) as ctx:
            agent.repair(verts, tris, max_collapse=0.05)
        msg = str(ctx.exception)
        self.assertIn("larger", msg)
        self.assertIn("--repair-tolerance", msg)


class TestPlacement(unittest.TestCase):
    def place(self, bp, hs, openings, **kw):
        return agent.place_housing(hs, bp, openings, kw.get("clearance", 2.0),
                                   kw.get("edge_inset", 5.2),
                                   camera_end=kw.get("camera_end"),
                                   min_offset=kw.get("min_offset", 6.0))

    def test_no_openings_still_offsets(self):
        """A case without a camera must still get an offset housing."""
        p = self.place(backplate(), housing(), [])
        self.assertGreaterEqual(p["offset_from_centre"], 6.0 - 1e-6)
        self.assertTrue(p["offset_satisfied"])
        self.assertEqual(p["camera_end_source"], "assumed")
        self.assertTrue(p["rotate_180"])

    def test_camera_end_can_be_given(self):
        p = self.place(backplate(), housing(), [], camera_end="high")
        self.assertEqual(p["camera_end"], "high")
        self.assertEqual(p["camera_end_source"], "given")
        self.assertFalse(p["rotate_180"])

    def test_placement_clears_the_opening(self):
        opening = {"x0": 5.0, "x1": 20.0, "y0": 3.0, "y1": 60.0, "samples": 40}
        p = self.place(backplate(), housing(), [opening])
        self.assertGreaterEqual(p["opening_clearance"], 2.0 - 1e-6)
        self.assertGreaterEqual(p["rect"]["x0"], 22.0 - 1e-6)
        self.assertEqual(p["camera_end_source"], "detected")

    def test_housing_too_wide_is_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            self.place(backplate(), housing(w=80.0), [])
        self.assertIn("does not fit", str(ctx.exception))

    def test_interlock_is_enforced_at_the_ends_too(self):
        """The Y edges get the interlock inset, not just the ordinary clearance."""
        with self.assertRaises(SystemExit) as ctx:
            self.place(backplate(height=150.0), housing(), [])
        self.assertIn("interlock", str(ctx.exception))

    def test_manual_position_is_checked(self):
        opening = {"x0": 5.0, "x1": 40.0, "y0": 3.0, "y1": 60.0, "samples": 40}
        rect = {"x0": 10.0, "x1": 42.4, "y0": 8.0, "y1": 153.7}
        chk = agent.check_placement(rect, [opening], backplate(), 2.0, 5.2)
        self.assertFalse(chk["ok"])
        self.assertTrue(any("opening clearance" in p for p in chk["problems"]))


class TestSharedParameters(unittest.TestCase):
    def test_coupling_is_derived_not_stored(self):
        band = PARAMS["strap_band_width"]
        ear = PARAMS["strap_ear_width"]
        overlap = PARAMS["strap_ear_band_overlap"]
        clear = PARAMS["strap_track_lateral_clearance"]
        self.assertAlmostEqual(PARAMS["strap_ear_center_spacing"],
                               band - 2 * overlap + ear, places=6)
        self.assertAlmostEqual(PARAMS["track_center_spacing"],
                               PARAMS["strap_ear_center_spacing"] + clear, places=6)
        self.assertAlmostEqual(PARAMS["track_width"], ear + clear, places=6)

    def test_narrowing_the_band_moves_the_ears(self):
        text = (KIT / "strap_system_parameters.scad").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "params.scad"
            p.write_text(text.replace("strap_band_width = 16.60;",
                                      "strap_band_width = 14.00;"), encoding="utf-8")
            narrowed = scad_params.Parameters(p)
        self.assertAlmostEqual(narrowed["strap_ear_center_spacing"],
                               narrowed["strap_band_width"] - 2 * narrowed["strap_ear_band_overlap"]
                               + narrowed["strap_ear_width"], places=6)
        self.assertLess(narrowed["strap_ear_center_spacing"],
                        PARAMS["strap_ear_center_spacing"])

    def test_every_parameter_the_builder_needs_resolves(self):
        needed = [
            "strap_length", "strap_band_width", "strap_ear_width",
            "strap_ear_center_spacing", "strap_fixed_ear_length",
            "strap_moving_ear_length", "strap_fixed_socket_clearance", "strap_travel",
            "track_hard_stop_overtravel", "strap_stow_notch_offset",
            "track_center_spacing", "track_width", "track_floor_thickness",
            "backplate_thickness", "negative_cut_overrun", "strap_window_width",
            "strap_window_end_clearance", "strap_window_corner_radius",
            "spring_body_width", "spring_relief_width", "spring_beam_half_length",
            "spring_relief_half_length", "spring_nose_half_length",
            "strap_detent_nose_depth", "spring_nose_samples",
        ]
        missing = [n for n in needed if n not in PARAMS.values]
        self.assertEqual(missing, [], f"missing from the SCAD: {missing}")

    def test_defaults_are_the_shipped_geometry(self):
        self.assertAlmostEqual(PARAMS["strap_band_width"], 16.60, places=2)
        self.assertAlmostEqual(PARAMS["strap_ear_width"], 6.00, places=2)
        self.assertAlmostEqual(PARAMS["strap_window_width"], 17.20, places=2)
        self.assertAlmostEqual(PARAMS["track_center_spacing"], 22.20, places=2)


class TestReleaseConsistency(unittest.TestCase):
    def test_bundled_kit_matches_the_human_kit(self):
        """The pack carries its own SCADs; a stale bundle must not go unnoticed."""
        sibling = PACK.parent / "Human_Kit"
        if not sibling.is_dir():
            self.skipTest("no sibling Human Kit in this checkout")
        for name in ("strap_system_parameters.scad", "perimeter_split_negative.scad",
                     "strap_housing_negative.scad", "strap_parametric.scad"):
            a = (KIT / name).read_bytes()
            b = (sibling / name).read_bytes()
            self.assertEqual(a, b, f"{name} differs between Agent_Pack/human_kit and Human_Kit")

    def test_example_report_matches_the_shipped_parts(self):
        report = json.loads((PACK / "examples" / "s25-ultra-thik" / "report.json").read_text())
        self.assertEqual(report["split"]["parts"], 2)
        self.assertEqual(report["housing"]["parts_after_cut"], 1)
        self.assertGreaterEqual(report["housing"]["clearance_to_openings"][0], 2.0)

    def test_manifests_do_not_checksum_themselves(self):
        for pkg in ("Human_Kit", "Agent_Pack"):
            sha = PACK.parent / pkg / "MANIFEST.sha256"
            if not sha.is_file():
                continue
            listed = {line.split("  ", 1)[1].strip() for line in sha.read_text().splitlines() if "  " in line}
            self.assertNotIn("MANIFEST.sha256", listed)
            if (PACK.parent / pkg / "MANIFEST.json").is_file():
                self.assertIn("MANIFEST.json", listed,
                              "the sha256 manifest should cover the json manifest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
