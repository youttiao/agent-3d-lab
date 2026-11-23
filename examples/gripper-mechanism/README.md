# 案例：两指夹爪机构 —— 一次「CAD → URDF → MuJoCo」的全流程

> 这个案例不是为了设计一个好夹爪，是为了**跑通并验证整条链路**：
> 一个带关节、带耦合、带质量分布的参数化模型，如何变成 MuJoCo 能跑的机器人描述，
> 以及过程中**哪些东西会静默地丢**。
>
> 详细分析见 [`docs/07-CAD到URDF到MuJoCo.md`](../../docs/07-CAD到URDF到MuJoCo.md)。

## 这个模型是什么

一个 Robotiq 2F-85 风格的平行钳口夹爪：

| | |
| --- | --- |
| 掌板 | 92 × 48 × 12 mm 的滑座，带两条导轨条 |
| 手指 | 两根，从 [`robotiq-v-finger`](../robotiq-v-finger/) 来的 V 型槽指尖 |
| 关节 | 两个移动关节（prismatic），沿 ±X |
| 耦合 | 一个齿轮 + 两条齿条 → 两指联动 |
| 限位 | 来自驱动器（**不是几何**）——平行夹爪的钳口停在工件上，工件不在模型里 |

`CLOSE_TRAVEL = 6.8345 mm` 是从几何反推的：让两个 V 槽口平面正好合拢到 0。
`OPEN_TRAVEL = 12 mm`、`DRIVE_FORCE_N = 140 N`、`DRIVE_SPEED_MPS = 0.2 m/s`
是**占位符**，得换成真实驱动器的手册值。

## 目录

```
gripper-mechanism/
├── src/
│   ├── gripper_mechanism.py     # 机构本体（掌板 + 两指 + 关节 + 耦合）
│   └── robotiq_v_finger.py      # 手指（与另一个案例同一份文件）
├── checks/
│   └── check_v_pair.py          # 量管子有没有卡在 V 槽里
├── description/                 # 导出的 URDF + 网格
│   ├── gripper.urdf
│   └── meshes/*.stl
├── sim/                         # 导出的 MJCF + 网格
│   ├── gripper.xml
│   └── assets/*.stl
└── img/                         # 各姿态渲染图
```

## 怎么跑

```bash
export PATH="$HOME/.local/bin:$PATH"
cd examples/gripper-mechanism

# 1. 建模（会打印文档 id 和浏览器 view 链接）
cad run src/gripper_mechanism.py
# → parts 5 · bounds 92 × 48 × 56 mm · joints 3

# 2. 导出 URDF 和 MJCF（id 用上一步打印的）
cad model export <id> description/gripper.urdf sim/gripper.xml

# 3. 格式层检查
cad urdf validate description/gripper.urdf
cad mujoco check sim/gripper.xml

# 4. 体检脚本（在仓库根目录）
MUJOCO_GL=disable python3 ../../checks/urdf_probe.py description/gripper.urdf
MUJOCO_GL=disable python3 ../../checks/joint_sweep.py description/gripper.urdf sim/gripper.xml

# 5. 出图（几何对了，形状也得对）
cad urdf snapshot description/gripper.urdf img/closed.png \
    --camera front --pose '{"right": -0.0068345}'
```

## 跑出来的数字

### 运动学（MJCF 与 URDF 逐位相同）

| 关节位置 | 右指世界 X | 左指世界 X | 钳口 | 镜像 |
| --- | --- | --- | --- | --- |
| −6.8345 mm（闭合限位） | 11.0000 mm | −11.0000 mm | **0.0000 mm** | ✅ |
| 0（gripping） | 17.8345 mm | −17.8345 mm | 13.6690 mm | ✅ |
| +12 mm（张开限位） | 29.8345 mm | −29.8345 mm | 37.6690 mm | ✅ |

### 三个静默行为（都在 `docs/07` 里展开）

| | 现象 | 后果 |
| --- | --- | --- |
| 质量 | URDF 在 MuJoCo 里丢掉固定体的质量 | 声明 0.81 kg → 实际 **0.06 kg**（丢 93%）。`cad urdf validate` 报 0.81 kg，看不出来 |
| 接触 | URDF 没有「这两件不碰」的语法 | 掌板与手指静置时就产生 6 个接触，摩擦把手指**卡住**（0.64 mm vs MJCF 的 13.2 mm） |
| `<mimic>` / 限位 | 都是**软约束** | 联动稳态残差 0.26～0.41 mm；限位越界不报错也不夹回 |

### 镜像靠的是关节轴，不是联动符号

两个关节在各自的体坐标系里局部轴都是 `0 0 1`，但世界轴相反：

```
right  局部轴=[0,0,1]  世界轴=[ 1,0,0]
left   局部轴=[0,0,1]  世界轴=[-1,0,0]
```

所以联动写成 `left = right`（**同号**）才对。
谁要是顺手把左指的轴也写成世界 +X，夹爪就会**一边张一边合**，而且不报任何错。

## 渲染图

| 图 | 看什么 |
| --- | --- |
| `img/gripping.png` | 正面：两个 V 槽口相对形成的菱形空腔 |
| `img/closed.png` | 正面：闭合限位，钳口正好 0 |
| `img/open.png` | 正面：张开 |
| `img/closed_iso.png` / `img/open_iso.png` | 等轴视角 |

## 这个案例想说明什么

1. **`cad urdf validate` 只检查文件本身**，看不到 MuJoCo 加载之后发生的事。
   凡是「跨格式」的检查，都得**让目标引擎真的加载一遍**。
2. **URDF 和 MJCF 不是等价物**。给 MuJoCo 用 MJCF，给 ROS 用 URDF。
3. **关节要扫，不能看**。符号反了、轴写反了，渲染图上只是「怪怪的」，
   变成数字才知道差多少 —— 见 `checks/joint_sweep.py`。
4. **联动是软约束**。要刚性就调 `solref`，别指望它默认就是刚的。

## 已知不足 / 下一步

- 手指（38 mm）**够不到**掌板的导轨条（y = ±22），所以手指其实没搭在导轨上，
  只是浮在掌板顶面。这就是 URDF 里那个假接触的来源。
- 掌板是个简化块，没有真正的直线导轨。
- **没有执行器**（`nu = 0`）。`limits()` 给出了力矩上限，但要驱动得自己加
  `<actuator><motor joint="right" …/></actuator>`。
- MuJoCo 建模指南建议 `cone="elliptic"` + 更小的 `solref[0]`，
  `cad mujoco check` 会提示，等模型定稿后再调。
