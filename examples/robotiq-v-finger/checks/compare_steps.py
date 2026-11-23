"""Compare a STEP file built by the 0.6-era runtime against the 0.11 one.

Migration fidelity check: the 0.11 runtime and the 0.6.5 one must produce the
same geometry, not merely a file of the same name.

    cad run checks/compare_steps.py <old.step> <new.step>
"""

# /// script
# dependencies = ["cad[build123d]"]
# ///

from __future__ import annotations

import sys

from cad import step
from cad.build123d import leaves

TOL = 1e-4  # mm


def profile(path: str) -> dict:
    tree = step.read(path)
    parts = leaves(tree)
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for part in parts:
        bb = part.bounding_box()
        for axis, v in enumerate((bb.min.X, bb.min.Y, bb.min.Z)):
            lo[axis] = min(lo[axis], v)
        for axis, v in enumerate((bb.max.X, bb.max.Y, bb.max.Z)):
            hi[axis] = max(hi[axis], v)
    return {
        "n": len(parts),
        "lo": lo,
        "hi": hi,
        "size": [hi[i] - lo[i] for i in range(3)],
        "labels": sorted(p.label for p in parts),
    }


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    old, new = sys.argv[1], sys.argv[2]
    a, b = profile(old), profile(new)

    print(f"old: {old}\n  parts={a['n']}  size={['%.4f' % v for v in a['size']]}")
    print(f"new: {new}\n  parts={b['n']}  size={['%.4f' % v for v in b['size']]}")

    ok = True
    if a["n"] != b["n"]:
        print(f"  ✗ 零件数不同: {a['n']} vs {b['n']}")
        ok = False
    else:
        print(f"  ✓ 零件数相同 ({a['n']})")

    for i, axis in enumerate("XYZ"):
        d = abs(a["size"][i] - b["size"][i])
        flag = "✓" if d <= TOL else "✗"
        if d > TOL:
            ok = False
        print(f"  {flag} {axis} 尺寸差 {d:.6f} mm")

    for i, axis in enumerate("XYZ"):
        for j, kind in enumerate(("min", "max")):
            d = abs((a["lo" if j == 0 else "hi"])[i] - (b["lo" if j == 0 else "hi"])[i])
            if d > TOL:
                print(f"  ✗ {axis} {kind} 差 {d:.6f} mm")
                ok = False

    if a["labels"] != b["labels"]:
        print(f"  ✗ 标签集合不同:\n      old={a['labels']}\n      new={b['labels']}")
        ok = False
    else:
        print(f"  ✓ 标签集合相同: {a['labels']}")

    print("\n结论:", "几何一致 ✅" if ok else "几何有差异 ❌")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
