"""Inspect Robotiq STEP files — try multiple cadgen APIs."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

from cadgen import read_scene, read_step

for name in ("robotiq_2f85_body.step", "robotiq_2f85_fingertip.step"):
    p = ROOT / "imported" / name
    if not p.exists():
        print(p, "MISSING"); continue
    print(f"\n=== {name} (size={p.stat().st_size}) ===")
    try:
        scene = read_scene(str(p))
        print(f"  scene type: {type(scene).__name__}")
        for attr in ("occurrences", "shapes", "components", "products", "labels", "tree"):
            if hasattr(scene, attr):
                v = getattr(scene, attr)
                try:
                    n = len(v)
                except Exception:
                    n = "?"
                print(f"  .{attr}() -> {n}")
        # Try reading bbox from native shapes
        if hasattr(scene, "shapes"):
            shapes = scene.shapes()
            print(f"  shapes count: {len(shapes)}")
            for i, s in enumerate(shapes[:5]):
                try:
                    bb = s.bounding_box()
                    mn, mx, sz = bb.min, bb.max, bb.size
                    print(f"    shape[{i}] bbox min=({mn.X:.1f},{mn.Y:.1f},{mn.Z:.1f}) "
                          f"max=({mx.X:.1f},{mx.Y:.1f},{mx.Z:.1f}) "
                          f"size=({sz.X:.1f},{sz.Y:.1f},{sz.Z:.1f})")
                except Exception as e:
                    print(f"    shape[{i}] bbox err: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ERR: {e}")