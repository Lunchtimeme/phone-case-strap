/*
  Boolean smoke-test host for the profiled perimeter cutter.
  This is NOT a phone case. It is a simple 100 x 180 x 2.65 mm slab whose
  backplate is split from its surrounding frame by the generated cutter.

  From this folder:
    openscad -o profile_split_test_host.stl profile_split_test_host.scad

  The exported mesh should contain two watertight connected solids. The import
  path assumes the default cutter STL is present in this same folder.
*/

difference() {
    translate([-50,-90,0]) cube([100,180,2.65]);
    import("profiled_perimeter_cut_full_ring.stl", convexity=10);
}
