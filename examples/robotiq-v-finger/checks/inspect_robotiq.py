"""Inspect the vendor Robotiq STEP files.

Reading a STEP file: `step.read(path)` gives a build123d tree, and
`cad.build123d.leaves(tree)` gives every part placed where it stands in the
tree's frame (a leaf carries its own label, colour and material).

Run from the project root:

    cad run checks/inspect_robotiq.py
"""

# /// script
# dependencies = ["cad[build123d]"]
# ///

from __future__ import annotations

from pathlib import Path

from cad import step
from cad.build123d import leaves

ROOT = Path(__file__).resolve().parent.parent
IMPORTED = ROOT / "imported"

FILES = ("robotiq_2f85_body.step", "robotiq_2f85_fingertip.step")


def describe(path: Path) -> None:
    print(f"\n=== {path.name} (size={path.stat().st_size:,} bytes) ===")
    tree = step.read(str(path))
    parts = leaves(tree)
    print(f"  leaves: {len(parts)}")

    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for i, part in enumerate(parts):
        bb = part.bounding_box()
        mn, mx, sz = bb.min, bb.max, bb.size
        print(
            f"    [{i:2d}] {part.label or '(no label)':<28} "
            f"min=({mn.X:8.2f},{mn.Y:8.2f},{mn.Z:8.2f}) "
            f"max=({mx.X:8.2f},{mx.Y:8.2f},{mx.Z:8.2f}) "
            f"size=({sz.X:8.2f} × {sz.Y:8.2f} × {sz.Z:8.2f})"
        )
        for axis, v in enumerate((mn.X, mn.Y, mn.Z)):
            lo[axis] = min(lo[axis], v)
        for axis, v in enumerate((mx.X, mx.Y, mx.Z)):
            hi[axis] = max(hi[axis], v)

    if parts:
        print(
            f"  overall bbox: {hi[0] - lo[0]:.2f} × {hi[1] - lo[1]:.2f} × "
            f"{hi[2] - lo[2]:.2f} mm   "
            f"(min=({lo[0]:.2f},{lo[1]:.2f},{lo[2]:.2f}) max=({hi[0]:.2f},{hi[1]:.2f},{hi[2]:.2f}))"
        )


def main() -> None:
    for name in FILES:
        p = IMPORTED / name
        if not p.exists():
            print(f"{p} — MISSING（厂商件需自行从 Robotiq 官网下载）")
            continue
        try:
            describe(p)
        except Exception as exc:  # noqa: BLE001 — a check prints, it does not raise
            import traceback

            traceback.print_exc()
            print(f"  ERR: {exc}")


if __name__ == "__main__":
    main()
