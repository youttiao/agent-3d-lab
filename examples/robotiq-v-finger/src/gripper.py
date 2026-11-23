"""Two-finger parallel gripper — Festo-like vibe demo.

Coordinate convention:
  X = finger protrusion axis (positive toward finger tips)
  Y = gripping direction (symmetric across Y=0)
  Z = up

Layout (mm):
  Flange   X[-20,+20]  Y[-20,+20]  Z[0, 5]    4× M3 through holes on 30×30 pitch
  Body     X[-20,+20]  Y[-5,+5]    Z[5, 25]
  Fingers  X[+20,+60]  Y[±15,±25] (demo open +15mm per finger, full travel 30mm)
  V-groove at finger inner face: 20mm long × 8mm wide × 3mm deep

Note: build123d 0.11 Box defaults to align=CENTER (centered on origin),
so we set align=(CENTER, CENTER, MIN) for the Z-axis datum to sit on Z=0.
"""

from __future__ import annotations

from cadgen import build123d as bd
from cadgen import step


# === Dimensions (mm) ===
FLANGE_L, FLANGE_W, FLANGE_H = 40.0, 40.0, 5.0
BODY_L, BODY_W, BODY_H = 40.0, 10.0, 20.0
FINGER_L, FINGER_W, FINGER_H = 40.0, 10.0, 18.0

# demo-open state: each finger offset by 15mm from closed (full travel 30mm)
DEMO_OPEN = 15.0

V_LEN, V_WIDTH, V_DEPTH = 20.0, 8.0, 3.0
MOUNT_HOLE_DIA = 3.2          # M3 clearance hole
MOUNT_HOLE_PITCH = 30.0       # hole-to-hole spacing


# === Derived positions ===
FINGER_X0 = BODY_L / 2.0                            # 20
FINGER_Z0 = FLANGE_H                                # 5
FINGER_Z_MID = FLANGE_H + FINGER_H / 2.0            # 14
V_X_CENTER = FINGER_X0 + FINGER_L / 2.0             # 40

_BOX_XY = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)


def _v_cutter(sign: int) -> bd.Shape:
    """V-groove cutter. V length along X, cross-section in YZ plane.

    sign=+1 → right finger (V apex toward Y+)
    sign=-1 → left finger  (V apex toward Y-)

    After centering along X, the cutter spans:
      X: -V_LEN/2 .. +V_LEN/2
      Y: 0 .. sign*V_DEPTH      (V opens at Y=0, apex at sign*V_DEPTH)
      Z: -V_WIDTH/2 .. +V_WIDTH/2
    """
    with bd.BuildPart() as v_part:
        with bd.BuildSketch(bd.Plane.YZ) as sketch:
            bd.Polygon(
                (0.0, -V_WIDTH / 2.0),
                (sign * V_DEPTH, 0.0),
                (0.0, +V_WIDTH / 2.0),
            )
        bd.extrude(amount=V_LEN)
    v = v_part.part
    # Center along X (so position math is symmetric)
    v = bd.Pos(-V_LEN / 2.0, 0.0, 0.0) * v
    return v


def _add_mount_holes(target: bd.Shape) -> bd.Shape:
    """Drill 4× M3 through holes on the flange."""
    p = MOUNT_HOLE_PITCH / 2.0
    for dx, dy in [(-p, -p), (-p, +p), (+p, -p), (+p, +p)]:
        # Cylinder built centered on origin; length = 2× flange thickness clears it
        hole = bd.Cylinder(MOUNT_HOLE_DIA / 2.0, FLANGE_H * 2.0)
        hole = bd.Pos(dx, dy, FLANGE_H / 2.0) * hole
        target = target - hole
    return target


@step(out="../STEP/gripper.step")
def gripper():
    parts = []

    # --- Flange: X[-20,+20], Y[-20,+20], Z[0,5] ---
    flange = bd.Box(FLANGE_L, FLANGE_W, FLANGE_H, align=_BOX_XY)
    flange = _add_mount_holes(flange)
    flange.label = "flange"
    parts.append(flange)

    # --- Body: X[-20,+20], Y[-5,+5], Z[5,25] ---
    body = bd.Box(BODY_L, BODY_W, BODY_H, align=_BOX_XY)
    body = bd.Pos(0.0, 0.0, FLANGE_H) * body
    body.label = "body"
    parts.append(body)

    # --- Right finger: X[+20,+60], Y[+15,+25], Z[+5,+23] ---
    rf = bd.Box(FINGER_L, FINGER_W, FINGER_H, align=_BOX_XY)
    rf = bd.Pos(V_X_CENTER, DEMO_OPEN + FINGER_W / 2.0, FINGER_Z0) * rf
    vc_r = bd.Pos(V_X_CENTER, DEMO_OPEN, FINGER_Z_MID) * _v_cutter(+1)
    rf = rf - vc_r
    rf.label = "finger_right"
    parts.append(rf)

    # --- Left finger: X[+20,+60], Y[-25,-15], Z[+5,+23] ---
    lf = bd.Box(FINGER_L, FINGER_W, FINGER_H, align=_BOX_XY)
    lf = bd.Pos(V_X_CENTER, -DEMO_OPEN - FINGER_W / 2.0, FINGER_Z0) * lf
    vc_l = bd.Pos(V_X_CENTER, -DEMO_OPEN, FINGER_Z_MID) * _v_cutter(-1)
    lf = lf - vc_l
    lf.label = "finger_left"
    parts.append(lf)

    return bd.Compound(children=parts, label="parallel_gripper")


if __name__ == "__main__":
    gripper()