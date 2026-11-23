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

def _align_ccm(): return (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)


def _align_c(): return (bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER)


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
    """The finger's solid: a 5 mm mount rail (Z 0..5) plus the V block (Z 5..44).

    The rail is what bolts onto the gripper's finger rail, and it is what the
    M3 holes and the index pin go through.
    """
    rail = bd.Box(MOUNT_W, MOUNT_L, MOUNT_H, align=_align_ccm())
    rail.label = "mount_rail"
    block = bd.Box(MOUNT_W, MOUNT_L, V_BLOCK_HEIGHT, align=_align_ccm())
    block = bd.Pos(0.0, 0.0, V_BLOCK_Z0) * block
    block.label = "v_block"
    return rail + block


def _v_cutter() -> bd.Shape:
    """Triangular-prism cutter that opens the V on the inner grip face.

    In the finger's local frame the V opens toward -X (the gripper centreline):
      * slot mouth (face)  at X = -MOUNT_W/2
      * apex               at X = -MOUNT_W/2 + V_DEPTH
      * opening width      V_WIDTH_AT_FACE, across Z (up/down)
      * extruded along Y — the finger's length, parallel to the pipe axis.

    The section is drawn on Plane.XZ so that (x, z) are the section's own
    coordinates and the prism runs along the finger's length.
    """
    face_x = -MOUNT_W / 2.0                   # slot mouth on the inner face
    apex_x = face_x + V_DEPTH                # apex retreats into the block
    z_top = V_BLOCK_Z_MID + V_WIDTH_AT_FACE / 2.0
    z_bot = V_BLOCK_Z_MID - V_WIDTH_AT_FACE / 2.0

    with bd.BuildPart() as part:
        with bd.BuildSketch(bd.Plane.XZ) as sketch:
            bd.Polygon(
                (face_x, z_top),
                (apex_x, V_BLOCK_Z_MID),
                (face_x, z_bot),
            )
        bd.extrude(amount=MOUNT_L, both=True)
    return part.part


def _add_mount_features(target: bd.Shape) -> bd.Shape:
    """Drill 2× M3 through-holes and 1× index-pin hole through the mount rail.

    The drill spans the rail's thickness (Z 0..MOUNT_H) and 0.5 mm past it, so
    the hole breaks cleanly out of the rail without drilling into the V block.
    """
    depth = MOUNT_H + 1.0
    for dx in (-M3_HOLE_PITCH / 2.0, +M3_HOLE_PITCH / 2.0):
        hole = bd.Cylinder(M3_HOLE_DIA / 2.0, depth, align=_align_c())
        hole = bd.Pos(dx, M3_HOLE_Y, MOUNT_H / 2.0) * hole
        target = target - hole

    pin = bd.Cylinder(INDEX_PIN_DIA / 2.0, depth, align=_align_c())
    pin = bd.Pos(0.0, INDEX_PIN_Y, MOUNT_H / 2.0) * pin
    target = target - pin
    return target


def _finger(side: str) -> bd.Shape:
    """One finished finger (mount + V + mount holes), in its local frame.

    side="right" → the V opens toward -X (towards the gripper centreline)
    side="left"  → the mirror of the right finger, so its V opens toward +X
    """
    body = _v_block_body()
    body = body - _v_cutter()
    body = _add_mount_features(body)
    if side == "left":
        body = body.mirror(bd.Plane.YZ)
    body.label = f"finger_{side}"
    return body


def _pipe_sample(y_extra: float = 2.0) -> bd.Shape:
    """DN25 pipe sample lying horizontally along Y (default cadgen cylinder is along Z)."""
    pipe = bd.Cylinder(PIPE_R, MOUNT_L + 2.0 * y_extra,
                       align=_align_ccm())
    pipe = bd.Rot(90, 0, 0) * pipe
    pipe = bd.Pos(0.0, (MOUNT_L + 2.0 * y_extra) / 2.0, V_BLOCK_Z_MID) * pipe
    pipe.label = "pipe_DN25"
    return pipe


def _half_pitch() -> float:
    """Half the distance between the two fingers, so the pipe sits in both V's.

    The pipe's centre is on the gripper's centreline (X=0). For a V of half
    angle `V_HALF_ANGLE`, the apex sits at R/sin(V_HALF_ANGLE) from that centre,
    along the V's bisector. The apex is `V_DEPTH - MOUNT_W/2` behind the
    finger's own centre, towards the centreline.
    """
    apex_offset = V_DEPTH - MOUNT_W / 2.0
    return PIPE_R / math.sin(V_HALF_ANGLE) - apex_offset


@step("../STEP/robotiq_v_finger.step")
def v_finger_pair():
    """Right + left V-fingers + a DN25 pipe sample for context."""
    half_pitch = _half_pitch()

    rf = bd.Pos(+half_pitch, 0.0, 0.0) * _finger("right")
    lf = bd.Pos(-half_pitch, 0.0, 0.0) * _finger("left")
    pipe = _pipe_sample()

    return bd.Compound(children=[rf, lf, pipe], label="robotiq_v_finger_pair")


@step("../STEP/robotiq_v_finger_single.step")
def single_finger_with_pipe():
    """One right-hand finger + a tangent DN25 pipe — for V-profile visualization."""
    rf = bd.Pos(+_half_pitch(), 0.0, 0.0) * _finger("right")
    pipe = _pipe_sample(y_extra=10.0)
    return bd.Compound(children=[rf, pipe], label="robotiq_v_finger_single")


if __name__ == "__main__":
    v_finger_pair()
    single_finger_with_pipe()