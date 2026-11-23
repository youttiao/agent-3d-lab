"""Robotiq-style parallel jaw gripper — a real mechanism, not a static shape.

This is the "CAD → URDF → MuJoCo" round trip's subject: a model with joints,
a coupling, materials and drive limits, from which `cad model export` writes a
URDF and an MJCF.

Mechanism
=========
Two fingers slide on rails along X (the closing axis), driven through one
pinion and two racks — the same arrangement the Robotiq 2F-85 uses. The
pinion is a reference axis that holds no part: a robot description has no
body for it, so the second finger is written as the first one's follower
(URDF `<mimic>`, MJCF `<equality><joint>`).

The fingers are the real V-groove fingertips from `robotiq_v_finger.py`.

Coordinate convention
=====================
  +X  = the closing axis (the right finger closes toward -X)
  +Y  = along the fingers, parallel to the gripped pipe
  +Z  = up; the fingers' mount rails (Z 0..5) sit on the palm's top face

Limits
======
The fingers' travel is set by the DRIVE, not by the geometry: a parallel
gripper's jaws stop on the workpiece, and the workpiece is not part of this
model. So `linear_range` here is the actuator's travel, and `limits()` carries
the drive's force and speed from its datasheet. `cad model ranges` reports the
geometric clashes (each finger against the other) — those are the workpiece's
business, not the joint's range.

The numbers below are placeholders to be replaced with the real drive's
datasheet; they are labelled as such on purpose.
"""

from __future__ import annotations

import math

import build123d as bd
from cad import model
from cad.build123d import (
    limits,
    mass,
    mechanism_state,
    point_mass,
    rack_and_pinion_pair,
)

from robotiq_v_finger import MOUNT_H, _finger, _half_pitch

# === Palm (a simplified carriage the fingers slide on) ===
PALM_X = 92.0
PALM_Y = 48.0
PALM_Z = 12.0          # below the fingers' mount faces
GUIDE_W = 4.0          # guide strip width in Y
GUIDE_H = 6.0          # guide strip height in Z
GUIDE_Y = PALM_Y / 2.0 - GUIDE_W / 2.0

# === Drive (PLACEHOLDERS — replace with the real actuator's datasheet) ===
PINION_R = 10.0                # pinion pitch radius, mm
K_MM_PER_DEG = 2 * math.pi * PINION_R / 360.0
CLOSE_TRAVEL = 6.8345          # mm, until the two fingers' inner faces touch
OPEN_TRAVEL = 12.0             # mm
DRIVE_FORCE_N = 140.0          # the drive's axial force, N
DRIVE_SPEED_MPS = 0.2          # m/s

# === Masses (grams) ===
# `mass()` says what a part weighs IN ALL, point masses included — so the palm's
# declaration is the plate plus the servo lump, not the plate alone.
PALM_PLATE_G = 250.0
SERVO_G = 500.0
PALM_TOTAL_G = PALM_PLATE_G + SERVO_G
FINGER_G = 30.0

# === Link names ===
LINK_PALM = "palm_link"
LINK_RIGHT = "finger_right_link"
LINK_LEFT = "finger_left_link"


def _palm() -> bd.Compound:
    """The carriage the fingers slide on: a plate and two guide strips."""
    plate = bd.Box(PALM_X, PALM_Y, PALM_Z,
                   align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    plate = bd.Pos(0.0, 0.0, -PALM_Z) * plate
    plate.label = "palm_plate"

    guides = []
    for sign, tag in ((-1, "guide_neg"), (1, "guide_pos")):
        g = bd.Box(PALM_X, GUIDE_W, GUIDE_H,
                  align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        g = bd.Pos(0.0, sign * GUIDE_Y, 0.0) * g
        g.label = tag
        guides.append(g)

    palm = bd.Compound(children=[plate, *guides], label="palm")
    mass(palm, PALM_TOTAL_G)
    # The drive sits under the plate, at the middle: a lump the CAD leaves out.
    # A point mass goes on a part, not on an assembly — and `at` is in the
    # part's own frame (before its placement), so the plate's mid-thickness.
    point_mass(plate, SERVO_G, bd.Pos(0.0, 0.0, PALM_Z / 2.0), name="servo")
    return palm


def _finger_part(side: str) -> bd.Compound:
    """One V-groove finger, built where it stands."""
    x = _half_pitch() if side == "right" else -_half_pitch()
    f = bd.Pos(x, 0.0, 0.0) * _finger(side)
    mass(f, FINGER_G)
    return f


@model
def gripper():
    """The whole gripper: a palm, two sliding fingers, one pinion, one coupling."""
    palm = _palm()
    right = _finger_part("right")
    left = _finger_part("left")

    # The slide's axis lies in the plane the fingers' mount rails slide in.
    rail_z = MOUNT_H / 2.0
    half = _half_pitch()

    # Right finger: slide axis along +X (outward), so a negative value closes it.
    r_axis = bd.Axis((half, 0.0, rail_z), (1, 0, 0))
    r_slide = bd.LinearJoint("right", palm, axis=r_axis,
                             linear_range=(-CLOSE_TRAVEL, OPEN_TRAVEL))
    bd.RigidJoint("right", right, bd.Location(r_axis.position))
    r_slide.connect_to(right.joints["right"], position=0)

    # Left finger: mirror, so the two move symmetrically.
    l_axis = bd.Axis((-half, 0.0, rail_z), (-1, 0, 0))
    l_slide = bd.LinearJoint("left", palm, axis=l_axis,
                             linear_range=(-CLOSE_TRAVEL, OPEN_TRAVEL))
    bd.RigidJoint("left", left, bd.Location(l_axis.position))
    l_slide.connect_to(left.joints["left"], position=0)

    # The pinion: a reference axis on the palm that holds no part.
    bd.RevoluteJoint("pinion", palm, axis=bd.Axis((0.0, 0.0, rail_z), (0, 1, 0)),
                     angular_range=(-45.0, 90.0))

    gripper = bd.Compound(children=[palm, right, left], label="gripper")

    # One pinion, two racks: the fingers move together and only through it.
    rack_and_pinion_pair(gripper, "grip", pinion=1.0,
                         right=K_MM_PER_DEG, left=K_MM_PER_DEG)

    # The drive's limits (PLACEHOLDERS from the datasheet).
    limits(gripper, "right", effort=DRIVE_FORCE_N, velocity=DRIVE_SPEED_MPS)
    limits(gripper, "left", effort=DRIVE_FORCE_N, velocity=DRIVE_SPEED_MPS)

    # Three named poses, exported as keyframes. "home" is the Menagerie
    # convention every MuJoCo model is expected to carry: the pose a tool
    # resets to. For a gripper that is fully open — the jaws are apart, so
    # nothing is being squeezed at rest.
    mechanism_state(gripper, "home", grip=OPEN_TRAVEL / K_MM_PER_DEG)
    mechanism_state(gripper, "gripping", grip=0.0)
    mechanism_state(gripper, "closed", grip=-CLOSE_TRAVEL / K_MM_PER_DEG)
    mechanism_state(gripper, "open", grip=OPEN_TRAVEL / K_MM_PER_DEG)

    return gripper


if __name__ == "__main__":
    gripper()
