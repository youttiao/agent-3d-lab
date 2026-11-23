"""量一下 v_finger_pair 的几何自洽性：管子到底有没有卡在 V 槽里。

疑问：`v_finger_pair` 里右指（sign=+1）的 V 开口朝 +X，也就是背离夹爪中线，
而管子中心在 X=0。按 apex 到管心的距离算，槽位是对的——但方向对不对，
要靠算，不能靠看。

量三样：
  1. 管子与每个手指实体的**公共体积**（>0 = 穿模）
  2. 管子与每个手指的**最小距离**（=0 = 接触）
  3. 每个手指的 V 槽口在哪一侧

跑法： cd <项目根> && cad run checks/check_v_pair.py
"""

# /// script
# dependencies = ["cad[build123d]"]
# ///

from __future__ import annotations

import math
import sys
from pathlib import Path

import build123d as bd
from cad.build123d import leaves

# checks/ 与 src/ 是兄弟目录，把 src 加进搜索路径，这样
# `cad run checks/check_v_pair.py` 不用额外设 PYTHONPATH。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import robotiq_v_finger as rvf


def overlap_volume(a, b) -> float:
    """两个实体的公共体积（mm^3）。布尔运算失败时返回 -1。"""
    try:
        common = a & b
    except Exception as exc:  # noqa: BLE001
        print(f"    布尔运算失败: {exc}")
        return -1.0
    try:
        return float(common.volume)
    except Exception:
        return -1.0


def min_distance(a, b) -> float:
    """两个实体之间的最小距离（mm）。用 BRepExtrema。"""
    try:
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
        d.Perform()
        return float(d.Value())
    except Exception as exc:  # noqa: BLE001
        print(f"    距离计算失败: {exc}")
        return float("nan")


def main() -> None:
    print("=== 常量 ===")
    print(f"  MOUNT_W={rvf.MOUNT_W}  MOUNT_L={rvf.MOUNT_L}  MOUNT_H={rvf.MOUNT_H}")
    print(f"  PIPE_OD={rvf.PIPE_OD}  PIPE_R={rvf.PIPE_R}  V_DEPTH={rvf.V_DEPTH}")
    print(f"  V_WIDTH_AT_FACE={rvf.V_WIDTH_AT_FACE}")

    half_pitch = rvf._half_pitch()
    print(f"  half_pitch={half_pitch:.4f}   （右指中心 X={half_pitch:.4f}，左指 X=-{half_pitch:.4f}）")
    print(f"  apex 在手指局部的 X = {rvf.V_DEPTH - rvf.MOUNT_W/2.0:+.4f}")

    rf = bd.Pos(+half_pitch, 0.0, 0.0) * rvf._finger("right")
    lf = bd.Pos(-half_pitch, 0.0, 0.0) * rvf._finger("left")
    pipe = rvf._pipe_sample()

    print()
    print("=== 包围盒 ===")
    for name, shape in (("右指 rf", rf), ("左指 lf", lf), ("管子 pipe", pipe)):
        bb = shape.bounding_box()
        print(f"  {name:10} X[{bb.min.X:8.3f},{bb.max.X:8.3f}] "
              f"Y[{bb.min.Y:8.3f},{bb.max.Y:8.3f}] Z[{bb.min.Z:8.3f},{bb.max.Z:8.3f}]")

    print()
    print("=== 管子 vs 手指 ===")
    for name, finger in (("右指 rf", rf), ("左指 lf", lf)):
        vol = overlap_volume(pipe, finger)
        dist = min_distance(pipe, finger)
        print(f"  {name}: 公共体积 = {vol:.1f} mm^3   最小距离 = {dist:.4f} mm")
        verdict = "❌ 穿模（管子插进了实体里）" if vol > 1.0 else (
            "✅ 不穿模" if vol <= 1.0 else "⚠️ 布尔失败"
        )
        print(f"      {verdict}")

    print()
    print("=== V 槽口朝向（手指局部 X 方向）===")
    print(f"  右指的 V 槽口在局部 X=-{rvf.MOUNT_W/2:.1f}（朝中线），"
          f"apex 在局部 X={rvf.V_DEPTH - rvf.MOUNT_W/2:+.1f}")
    print(f"  管子中心在世界 X=0")
    print(f"  → 右指槽口世界 X={half_pitch - rvf.MOUNT_W/2:.3f}，apex 世界 X={half_pitch + rvf.V_DEPTH - rvf.MOUNT_W/2:.3f}")
    print(f"  → apex 到管心的距离 = {half_pitch + rvf.V_DEPTH - rvf.MOUNT_W/2:.4f}"
          f"（应为 R/sin(半角) = {rvf.PIPE_R/math.sin(math.radians(rvf.V_ANGLE_DEG/2)):.4f}）")


if __name__ == "__main__":
    main()
