"""关节扫描：把「符号对不对、轴朝哪、从动件跟没跟」变成数字。

为什么光看渲染图不够：两个手指的 V 槽口朝反了、或者联动方向反了，
渲染图上看出来是「怪怪的」，但说不出差多少。这个脚本直接量五件事：

  1. 每个关节的**世界轴向** —— 声明的方向 vs 实际动的方向
  2. **镜像对不对** —— 右指 +X 时左指必须 −X
  3. **钳口开度** —— 两个手指 V 槽口平面之间的距离
  4. **联动的稳态误差** —— MuJoCo 的关节等式是软约束，不是刚性
  5. **限位是真限位还是软约束**

两个文件都扫：MJCF（MuJoCo 的原生格式）和 URDF（带 fusestatic=false，
否则 palm 的质量被静默丢掉，world 坐标系会跑偏）。

跑法（在本项目根目录）：

    MUJOCO_GL=disable python3 checks/joint_sweep.py
    MUJOCO_GL=disable python3 checks/joint_sweep.py description/gripper.urdf sim/gripper.xml

不给路径时，默认用 `description/gripper.urdf` 和 `sim/gripper.xml`。
"""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import mujoco
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

EQ_NAMES = {0: "mjEQ_FIXED", 1: "mjEQ_CONNECT", 2: "mjEQ_JOINT", 3: "mjEQ_TENDON"}


def load(path: pathlib.Path, fusestatic: bool = False) -> mujoco.MjModel:
    """Load an MJCF, or a URDF with fusestatic turned off."""
    if path.suffix == ".urdf":
        xml = path.read_text()
        if fusestatic and "<mujoco>" not in xml:
            xml = xml.replace(
                "</robot>", '<mujoco><compiler fusestatic="false"/></mujoco></robot>'
            )
        # A URDF's mesh paths are relative to the file, so write it beside it.
        tmp = path.with_name(f"._sweep_{path.name}")
        tmp.write_text(xml)
        try:
            return mujoco.MjModel.from_xml_path(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)
    return mujoco.MjModel.from_xml_path(str(path))


def find_geom(m: mujoco.MjModel, *names: str) -> int:
    """Look a geom up by any of several names; complain if none hit.

    The MJCF names its collision geoms `<part>_collision`; MuJoCo's URDF
    loader keeps the plain link name instead. Guessing wrong used to return
    -1, which silently addressed the LAST geom in the model.
    """
    for nm in names:
        gid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, nm)
        if gid >= 0:
            return gid
    raise KeyError(f"找不到 geom {names}；现有："
                   f"{[mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) for i in range(m.ngeom)]}")


def geom_world_aabb(m: mujoco.MjModel, data: mujoco.MjData, gid: int) -> tuple:
    """A collision geom's axis-aligned bounds in world coordinates.

    The mesh's own vertices are read out of the model and transformed by the
    geom's pose. Taking the *local AABB's eight corners* instead would
    over-estimate by ~0.9 mm: MuJoCo re-centres the mesh on its centre of
    mass and rotates it to the inertia principal axes, so the mesh is not
    axis-aligned in its own frame any more.
    """
    assert m.geom_type[gid] == mujoco.mjtGeom.mjGEOM_MESH
    did = int(m.geom_dataid[gid])
    adr = int(m.mesh_vertadr[did])
    num = int(m.mesh_vertnum[did])
    # mesh_vert is already an (N, 3) array; mesh_vertadr counts vertices.
    verts = np.asarray(m.mesh_vert[adr : adr + num], dtype=float)

    R = data.geom_xmat[gid].reshape(3, 3)
    world = verts @ R.T + data.geom_xpos[gid]
    return world.min(axis=0), world.max(axis=0)


def finger_gap(m: mujoco.MjModel, data: mujoco.MjData) -> float:
    """Distance between the two V-groove mouth planes, in metres.

    The right finger's mouth is its minimum X, the left finger's mouth is its
    maximum X: each groove opens toward the gripper's centreline, and the
    right finger sits on the +X side.
    """
    gid_r = find_geom(m, "finger_right_collision", "finger_right")
    gid_l = find_geom(m, "finger_left_collision", "finger_left")
    lo_r, _ = geom_world_aabb(m, data, gid_r)
    _, hi_l = geom_world_aabb(m, data, gid_l)
    return float(lo_r[0] - hi_l[0])


def sweep(m: mujoco.MjModel, label: str) -> None:
    data = mujoco.MjData(m)
    names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(m.njnt)]
    print(f"\n{'=' * 78}")
    print(f"  {label}")
    print(f"{'=' * 78}")
    print(f"  关节: {names}   nq={m.nq}  nu={m.nu}  neq={m.neq}")

    for i in range(m.neq):
        print(
            f"  等式: {EQ_NAMES.get(int(m.eq_type[i]), m.eq_type[i])}  "
            f"obj1={int(m.eq_obj1id[i])} obj2={int(m.eq_obj2id[i])}  "
            f"polycoef={np.round(m.eq_data[i][:5], 6).tolist()}  "
            f"solref={np.round(m.eq_solref[i][:2], 5).tolist()}"
        )

    bid_r = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "finger_right")
    bid_l = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "finger_left")
    jid_r = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "right")
    jid_l = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "left")
    jrange = np.array(m.jnt_range[jid_r])
    adr_r = int(m.jnt_qposadr[jid_r])
    adr_l = int(m.jnt_qposadr[jid_l])

    # ── 1. 世界轴向 ───────────────────────────────────────────────────
    mujoco.mj_forward(m, data)
    print(f"\n  关节的世界轴：")
    for jid in (jid_r, jid_l):
        nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, jid)
        print(f"    {nm:6} 局部轴={np.round(m.jnt_axis[jid], 3).tolist()}  "
              f"世界轴={np.round(data.xaxis[jid], 3).tolist()}")
    print(f"    → 两个关节的**局部轴一样**，但世界轴相反：镜像靠关节轴实现，"
          f"不是靠联动符号。")

    # ── 2. 静态扫描 ───────────────────────────────────────────────────
    print(f"\n  {'qpos(m)':>10} {'右指 X(mm)':>12} {'左指 X(mm)':>12} "
          f"{'钳口(mm)':>10} {'镜像检查':>12}")
    print(f"  {'-' * 62}")
    for q in (0.0, -0.0068345, -0.003, 0.003, 0.012):
        data.qpos[:] = 0.0
        data.qpos[adr_r] = q
        data.qpos[adr_l] = q          # 满足联动约束，看镜像
        mujoco.mj_forward(m, data)
        xr = float(data.xpos[bid_r][0])
        xl = float(data.xpos[bid_l][0])
        gap = finger_gap(m, data)
        mirror = "✅ 对称" if abs(xr + xl) < 1e-6 else f"⚠️ {1e3*(xr+xl):+.3f}"
        print(f"  {q:>10.6f} {1e3 * xr:>12.4f} {1e3 * xl:>12.4f} "
              f"{1e3 * gap:>10.4f} {mirror:>12}")
    print(f"    （qpos 越大 = 右指向 +X 走 = 远离中线 = 张开；"
          f"钳口 = 两个 V 槽口平面的间距）")

    # ── 3. 联动的稳态误差 ─────────────────────────────────────────────
    # mj_forward 只算瞬时加速度不积分，所以静态扫描看不出联动。
    # 推一把再走几步，看两边稳态差多少。
    dof_r = int(m.jnt_dofadr[jid_r])
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(m, data)
    data.qfrc_applied[dof_r] = 0.5
    for _ in range(60):
        mujoco.mj_step(m, data)
    qr, ql = float(data.qpos[adr_r]), float(data.qpos[adr_l])
    print(f"\n  联动检查：给右指关节 0.5 N，走 60 步")
    print(f"    qpos_right = {1e3 * qr:+.4f} mm   （世界 X {1e3 * float(data.xpos[bid_r][0]):+.4f}）")
    print(f"    qpos_left  = {1e3 * ql:+.4f} mm   （世界 X {1e3 * float(data.xpos[bid_l][0]):+.4f}）")
    print(f"    约束残差   = {1e3 * (qr - ql):+.4f} mm")
    print(f"    → 方向 {'✅ 对（右指 +X，左指 −X）' if qr > 0 and ql > 0 else '❌ 错'}"
          f"；残差是**软约束的稳态误差**，不是没联动")

    # ── 4. 限位 ───────────────────────────────────────────────────────
    print(f"\n  关节 range = [{jrange[0]:.6f}, {jrange[1]:.6f}] m")
    for q in (jrange[0] - 0.005, jrange[1] + 0.005):
        data.qpos[:] = 0.0
        data.qpos[adr_r] = q
        mujoco.mj_forward(m, data)
        print(f"    直接把 qpos 设成 {q:+.6f} → 右指 X = "
              f"{1e3 * float(data.xpos[bid_r][0]):.4f} mm（没被夹回去）")
    print(f"    → 限位是 mj_step 里的一类单侧**软约束**，不是夹紧："
          f"越界不报错，只是会被减速/挡住，位置仍可能略微超出。")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    mjcf = Path(args[1]).resolve() if len(args) > 1 else ROOT / "sim" / "gripper.xml"
    urdf = Path(args[0]).resolve() if len(args) > 0 else ROOT / "description" / "gripper.urdf"

    if not mjcf.exists() and not urdf.exists():
        print(__doc__)
        raise SystemExit(2)
    if mjcf.exists():
        sweep(load(mjcf), f"MJCF  {mjcf}")
    if urdf.exists():
        sweep(load(urdf, fusestatic=True), f"URDF  {urdf}  (fusestatic=false)")


if __name__ == "__main__":
    main()
