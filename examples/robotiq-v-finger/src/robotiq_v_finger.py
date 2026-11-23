"""Robotiq 2F-85 V-groove fingertip — grip cylindrical workpieces (water pipe etc.).

Design intent
=============
Replaces the standard silicone pad (AGC-TIP-204-085) with a rigid V-groove
fingertip. Keeps the original 2F-85 mounting interface so it bolts onto the
stock finger rail without modification.

Coordinate convention (per finger)
==================================
  +X  = toward gripper centerline (grip motion direction)
  +Y  = along the finger rail (parallel to pipe axis when gripping)
  +Z  = up (out of mount face)

For the LEFT finger, mirror about the YZ plane: V opens in -X.
"""

from __future__ import annotations

import build123d as bd
from cad import step
import math

# Lazy bd attribute access — avoid touching the kernel at import time.
def _align_ccm(): return (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)


# === Mount interface (matches Robotiq AGC-TIP-204-085 footprint) ===
MOUNT_W = 22.0          # X — width across the gripper
MOUNT_L = 38.0          # Y — along the finger rail / pipe axis
MOUNT_H = 5.0           # Z — thickness of the mount rail

M3_HOLE_DIA = 3.2
M3_HOLE_PITCH = 16.0    # X spacing between the two M3 holes
M3_HOLE_Y = 0.0         # M3 holes centered along Y (typical OEM pattern)
INDEX_PIN_DIA = 3.0
INDEX_PIN_Y = -14.0     # offset toward the gripper body end


# === V-groove (defaults sized for DN25 water pipe = 33 mm OD) ===
PIPE_OD = 33.0
PIPE_R = PIPE_OD / 2.0
V_ANGLE_DEG = 90.0                      # full included angle
V_HALF_ANGLE = math.radians(V_ANGLE_DEG / 2.0)
V_DEPTH = PIPE_R                        # 16.5 — V opens wide enough for pipe OD
V_WIDTH_AT_FACE = 2.0 * V_DEPTH * math.tan(V_HALF_ANGLE)
# Block thickness in X must exceed V_DEPTH so material remains behind the apex.
V_BLOCK_THICK = V_DEPTH + 8.0           # ~24.5 — extra 8mm wall behind apex
# Make the V-block tall enough that the V opening (33mm) sits within it.
V_BLOCK_HEIGHT = max(V_WIDTH_AT_FACE + 6.0, 25.0)

# Z placement of the V apex on the inner face of the V-block
V_BLOCK_Z0 = MOUNT_H                                  # 5
V_BLOCK_Z_MID = V_BLOCK_Z0 + V_BLOCK_HEIGHT / 2.0     # center of V-block


def _v_block_body() -> bd.Shape:
    """Solid block extending upward from the mount rail (no V yet)."""
    block = bd.Box(MOUNT_W, MOUNT_L, V_BLOCK_HEIGHT, align=_align_ccm())
    block = bd.Pos(0.0, 0.0, V_BLOCK_Z0) * block
    return block


def _v_cutter(sign: int) -> bd.Shape:
    """Triangular-prism cutter that opens the V on the inner grip face.

    sign=+1 → right finger (V opens to +X)
    sign=-1 → left finger  (V opens to -X)
    """
    apex_x = sign * (MOUNT_W / 2.0 - V_DEPTH)
    face_x = sign * (MOUNT_W / 2.0)
    z_top = V_BLOCK_Z_MID + V_WIDTH_AT_FACE / 2.0
    z_bot = V_BLOCK_Z_MID - V_WIDTH_AT_FACE / 2.0

    with bd.BuildPart() as part:
        with bd.BuildSketch(bd.Plane.XY) as sketch:
            bd.Polygon(
                (face_x, z_top),
                (apex_x, V_BLOCK_Z_MID),
                (face_x, z_bot),
            )
        bd.extrude(amount=MOUNT_L, both=True)
    return part.part


def _add_mount_features(target: bd.Shape) -> bd.Shape:
    """Drill 2× M3 through-holes and 1× index-pin hole through the mount rail."""
    overshoot = MOUNT_H * 2.0
    for dx in (-M3_HOLE_PITCH / 2.0, +M3_HOLE_PITCH / 2.0):
        hole = bd.Cylinder(M3_HOLE_DIA / 2.0, overshoot, align=_align_ccm())
        hole = bd.Pos(dx, M3_HOLE_Y, 0.0) * hole
        target = target - hole

    pin = bd.Cylinder(INDEX_PIN_DIA / 2.0, overshoot, align=_align_ccm())
    pin = bd.Pos(0.0, INDEX_PIN_Y, 0.0) * pin
    target = target - pin
    return target


def _finger(sign: int, mirror: bool = False) -> bd.Shape:
    """One finished finger (mount + V + mount holes), in its local frame.

    sign=+1 → V opens in +X (right finger, before mirroring)
    sign=-1 → V opens in -X (left finger)
    mirror=True → reflect across YZ plane (for the left finger)
    """
    body = _v_block_body()
    body = body - _v_cutter(sign)
    body = _add_mount_features(body)
    if mirror:
        body = body.mirror(bd.Plane.YZ)
    body.label = "finger_right" if sign > 0 else "finger_left"
    return body


def _pipe_sample(y_extra: float = 2.0) -> bd.Shape:
    """DN25 pipe sample lying horizontally along Y (default cadgen cylinder is along Z)."""
    pipe = bd.Cylinder(PIPE_R, MOUNT_L + 2.0 * y_extra,
                       align=_align_ccm())
    pipe = bd.Rot(90, 0, 0) * pipe
    pipe = bd.Pos(0.0, (MOUNT_L + 2.0 * y_extra) / 2.0, V_BLOCK_Z_MID) * pipe
    pipe.label = "pipe_DN25"
    return pipe


@step("../STEP/robotiq_v_finger.step")
def v_finger_pair():
    """Right + left V-fingers + a DN25 pipe sample for context."""
    # Spread the two fingers so the pipe sits tangent to both V walls.
    # For right finger at X=+half_pitch: V apex at X = +half_pitch + (-V_DEPTH+MOUNT_W/2)
    #   = +half_pitch - (V_DEPTH - MOUNT_W/2).
    # For pipe center at X=0 tangent to right V walls (90° V): pipe center is at
    #   distance R/sin(V_HALF_ANGLE) from V apex, on the bisector (toward the face).
    # Set the V apex so the pipe center sits at that distance:
    #   +half_pitch - (V_DEPTH - MOUNT_W/2) = R/sin(V_HALF_ANGLE)
    #   => half_pitch = (V_DEPTH - MOUNT_W/2) + R/sin(V_HALF_ANGLE)
    half_pitch = (V_DEPTH - MOUNT_W / 2.0) + PIPE_R / math.sin(V_HALF_ANGLE)

    rf = _finger(+1)
    rf = bd.Pos(+half_pitch, 0.0, 0.0) * rf
    lf = _finger(-1, mirror=True)
    lf = bd.Pos(-half_pitch, 0.0, 0.0) * lf
    pipe = _pipe_sample()

    return bd.Compound(children=[rf, lf, pipe], label="robotiq_v_finger_pair")


@step("../STEP/robotiq_v_finger_single.step")
def single_finger_with_pipe():
    """One right-hand finger + a tangent DN25 pipe — for V-profile visualization."""
    half_pitch = (V_DEPTH - MOUNT_W / 2.0) + PIPE_R / math.sin(V_HALF_ANGLE)
    rf = _finger(+1)
    rf = bd.Pos(+half_pitch, 0.0, 0.0) * rf
    pipe = _pipe_sample(y_extra=10.0)
    return bd.Compound(children=[rf, pipe], label="robotiq_v_finger_single")


if __name__ == "__main__":
    v_finger_pair()
    single_finger_with_pipe()