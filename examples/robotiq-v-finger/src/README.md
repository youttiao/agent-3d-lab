# 模型目录（Model catalog）

| 模型 | 源文件 | 输出 | 说明 |
| --- | --- | --- | --- |
| `v_finger_pair` | `src/robotiq_v_finger.py` | `STEP/robotiq_v_finger.step` | 左右 V 型指尖 + DN25 管道样件（看双指与管子的关系） |
| `single_finger_with_pipe` | `src/robotiq_v_finger.py` | `STEP/robotiq_v_finger_single.step` | 单指 + 管道（看 V 槽断面） |
| `gripper` | `src/gripper.py` | `STEP/gripper.step` | 演示用两指平行夹爪（Festo 风格） |

## 跑一遍

```bash
cad run src/robotiq_v_finger.py     # 跑模型，STEP 随 run 写出
cad run src/gripper.py
```

出图（OCCT 无头渲染，1～2 秒，不用浏览器、不用 GPU）：

```bash
cad run src/robotiq_v_finger.py            # 打印文档 id
cad model snapshot <id> tmp/finger.png
```

## 检查脚本

```bash
cad run checks/inspect_robotiq.py          # 读厂商 STEP，打印每个零件的包围盒
cad run checks/compare_steps.py A.step B.step   # 比对两个 STEP 的几何
```

## 约定

- 单位 mm，坐标系 XY 平面 + Z 向上
- 源文件名与输出文件名同名主干
- `@step("../STEP/x.step")` 里的路径**相对脚本本身**
- 关键尺寸全部提成模块级常量
- **内核对象只在函数体里读**：`bd.Align.CENTER` 写在模块层会让脚本自己的进程
  也加载内核，每次 run 多花 2～3 秒

## 迁移说明

本项目从 text-to-cad **0.6.5 迁到 0.11.16**（2026-11-23）。
几何完全一致：`checks/compare_steps.py` 对三个模型逐一比对，
零件数、包围盒、标签集合全部相同，尺寸差 **0.000000 mm**。

API 变化见 [`../../agent-3d-lab/docs/05-升级到0.11.md`](../../agent-3d-lab/docs/05-升级到0.11.md)。
