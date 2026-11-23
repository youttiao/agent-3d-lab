"""URDF 体检：把 MuJoCo 最容易静默吃掉的东西显式查出来。

MuJoCo 在 URDF 模式下有两个"静默"行为，光看 `cad urdf validate` 查不出来：

1. **固定在 world 上的体的质量被丢弃**（URDF 模式强制 fusestatic=true，
   FuseStatic 拒绝把质量融进 world）。
   注意不是"只有 base link"——base link 是空的也照样丢，
   凡是固定在 world 上的体（掌板、配重块、传感器）全都会消失。
   → 修法：`<mujoco><compiler fusestatic="false"/></mujoco>`
2. **`<mimic>` 在 MuJoCo < 3.13 是静默无效的**（从动关节变成独立自由度，
   一句警告都不打）。≥ 3.13 才翻译成 `mjEQ_JOINT` 等式约束。

⚠️ URDF 模式下 `<mujoco>` 扩展块**只认 `<compiler>` 的属性**；
`<option>` `<size>` `<visual>` `<contact>` `<equality>` 全被静默忽略。

跑法（在本项目根目录）：

    MUJOCO_GL=disable python3 checks/urdf_probe.py robot.urdf
"""

from __future__ import annotations

import pathlib
import sys

import mujoco

# MuJoCo 的 eq_type 枚举（src/user/user_api.h 的 mjtEq）
EQ_NAMES = {0: "mjEQ_FIXED", 1: "mjEQ_CONNECT", 2: "mjEQ_JOINT", 3: "mjEQ_TENDON"}


def probe(path: str, with_fusestatic: bool = False) -> dict:
    xml = open(path).read()
    if with_fusestatic and "<mujoco>" not in xml:
        xml = xml.replace(
            "</robot>", '<mujoco><compiler fusestatic="false"/></mujoco></robot>'
        )
    # Written beside the original: a URDF's mesh paths are relative to it.
    src = pathlib.Path(path).resolve()
    tmp = src.with_name(f"._probe_{src.name}")
    with open(tmp, "w") as fh:
        fh.write(xml)

    try:
        m = mujoco.MjModel.from_xml_path(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    info = {
        "njnt": m.njnt,
        "nq": m.nq,
        "nu": m.nu,
        "neq": m.neq,
        "body_mass": [float(x) for x in m.body_mass],
        "total_mass": float(mujoco.mj_getTotalmass(m)),
        "equalities": [],
    }
    for i in range(m.neq):
        info["equalities"].append(
            {
                "type": EQ_NAMES.get(int(m.eq_type[i]), f"type={m.eq_type[i]}"),
                "obj1": int(m.eq_obj1id[i]),
                "obj2": int(m.eq_obj2id[i]),
                "polycoef": [round(float(x), 6) for x in m.eq_data[i][:5]],
            }
        )
    return info


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    path = sys.argv[1]

    print(f"=== {path} ===")
    for label, fuse in (("默认", False), ("fusestatic=false", True)):
        try:
            i = probe(path, fuse)
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: 加载失败 —— {exc}")
            continue
        print(f"  [{label}]")
        print(f"    njnt={i['njnt']}  nq={i['nq']}  nu={i['nu']}  neq={i['neq']}")
        print(f"    body_mass = {i['body_mass']}")
        print(f"    总质量    = {i['total_mass']:.4f} kg")
        for e in i["equalities"]:
            print(
                f"    等式: {e['type']}  obj1={e['obj1']} obj2={e['obj2']} "
                f"polycoef={e['polycoef']}"
            )
        if i["neq"] == 0:
            print("    ⚠️ 没有等式约束：若 URDF 里有 <mimic>，"
                  "说明 MuJoCo < 3.13 把它静默忽略了（升级到 ≥ 4.0.1）")
        if abs(i["total_mass"]) < 1e-9:
            print("    ⚠️ 总质量为 0")

    # 两次的差 = 被 fusestatic 丢掉的固定体的质量
    a = probe(path, False)
    b = probe(path, True)
    diff = b["total_mass"] - a["total_mass"]
    print()
    if abs(diff) > 1e-9:
        print(f"⚠️ 固定在 world 上的体共有 {diff:.4f} kg 被静默丢弃了。"
              f"加 <mujoco><compiler fusestatic=\"false\"/></mujoco> 可以保留。")
    else:
        print("✓ 固定体的质量没有被丢弃（要么没写，要么已经加了 fusestatic=false）")


if __name__ == "__main__":
    main()
