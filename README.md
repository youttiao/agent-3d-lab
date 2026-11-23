# agent-3d-lab

**用 Agent 做 3D：知识库 + 工作流 + 案例库**

这个仓库记录「让编码 Agent 参与三维工作」这件事的落地过程：
用什么工具、怎么装、怎么把一件事从"想法"推到"能打印/能上机器人"的 STEP 文件，
以及踩过的坑。

> 目标读者：想用 Agent 做三维、但没做过的工程师。
> 文档用中文写，代码和标识符用英文。

---

## 为什么会有这个仓库

之前一直在用 Agent 写代码，三维这事一直没碰。想开始做 3D 模型分析、
重新设计零件、把手上的机器人描述（URDF）调成物理上说得通的样子。
但一开始什么都不知道：Agent 做 3D 需要装什么 skill？需要什么软件？
现在别人做到了什么程度？

所以先建个地方把**调研结论**和**可复用的做法**沉淀下来，
以后有朋友一起贡献。

---

## 现在到哪一步

| | 状态 |
| --- | --- |
| 核心工具链 | ✅ **已升级到 text-to-cad 0.11.16**，本机不用再装就能开工 |
| CAD skill 套件 | ✅ 新版 8 个（`cad` `robot-simulation` `fea` `pcb` `print3d` `render` `engineering-drawing` `sendcutsend`），旧的 13 个已并入 |
| 调研文档 | ✅ 见 [`docs/01-技术路线全景.md`](docs/01-技术路线全景.md) |
| 第一个完整案例 | ✅ [`examples/robotiq-v-finger`](examples/robotiq-v-finger/README.md)（Robotiq 2F-85 夹爪 V 型槽指尖逆向），**已迁到新 API，几何零差异**，并**量出并修掉 3 个真 bug** |
| 升级到 0.11 | ✅ 已执行，方案与实际结果见 [`docs/05-升级到0.11.md`](docs/05-升级到0.11.md) |
| 出图验证 | ✅ OCCT 无头渲染本机可用，**0.07～2 秒出图，不用浏览器不用 GPU** |
| **CAD → URDF → MuJoCo** | ✅ **跑通了一整轮**，见 [`examples/gripper-mechanism`](examples/gripper-mechanism/README.md) 和 [`docs/07-CAD到URDF到MuJoCo.md`](docs/07-CAD到URDF到MuJoCo.md)。查出 **6 个静默行为**（质量丢 93%、接触无法排除、`<mimic>`/限位是软约束…） |
| GUI 建模软件（Blender / FreeCAD） | ⬜ 待装，但现在**不需要** |

一句话结论：**机械件走「代码参数化」路线，AI 生成网格那条路在 Mac 上不划算。**
完整理由见 [`docs/01`](docs/01-技术路线全景.md)。

> **调研里最大的不确定项已经落地**：macOS 的 OpenGL 从 10.14 起就废弃了，
> OCCT 8 自带的无头光栅器能不能在无头 arm64 上初始化，原本没人验证过。
> **本机实测：能。** 1600×1200 出图 0.07～2 秒。

> ⚠️ **这一轮最值钱的一条结论**：
> `cad urdf validate` 只检查 URDF **文件本身**，
> 看不到 MuJoCo **加载之后**发生的事。
> 凡是跨格式的检查，都得让目标引擎真的加载一遍。
> 本仓库因此有了两个通用体检脚本：[`checks/urdf_probe.py`](checks/urdf_probe.py)
> 和 [`checks/joint_sweep.py`](checks/joint_sweep.py)。

---

## 快速开始

```bash
# 1. 自查环境（退出码 0 = 可开工）
bash scripts/doctor.sh

# 2. 跑一遍示例
cd examples/robotiq-v-finger
cad run src/robotiq_v_finger.py          # 生成 STEP，并打印 id 和浏览器 view 链接
cad step snapshot STEP/robotiq_v_finger.step tmp/finger.png   # 出图，1～2 秒

# 3. 想交互看：浏览器打开上面打印的 view 链接
```

新开一个 CAD 项目：

```bash
cp -R templates/cad-project projects/my-part
```

---

## 仓库结构

```
agent-3d-lab/
├── README.md                     # 你在读的这份
├── docs/
│   ├── 01-技术路线全景.md         # 调研：现在业界有哪几条路，各自到什么程度
│   ├── 02-本机工具链.md           # 本机装了什么、还缺什么、怎么补
│   ├── 03-工作流速查.md           # 建模 / 看图 / 分析 / URDF 的标准动作
│   ├── 04-我们的现场.md           # 手头三件具体的事（夹爪 / 标定支架 / 鸭子的数模）
│   ├── 05-升级到0.11.md           # 升级方案与执行记录
│   ├── 06-机器人描述与URDF.md     # URDF 怎么调到物理上说得通（惯性门槛 / MuJoCo 的坑 / 单位陷阱）
│   └── 07-CAD到URDF到MuJoCo.md   # 一次端到端实测：6 个静默行为、两个格式的分工
├── examples/
│   ├── robotiq-v-finger/         # 案例一：厂商件逆向重建（Robotiq 2F-85 V 型槽指尖）
│   └── gripper-mechanism/        # 案例二：CAD → URDF → MuJoCo 全流程（两指夹爪机构）
├── templates/
│   └── cad-project/              # 新 CAD 项目脚手架
├── checks/
│   ├── urdf_probe.py             # URDF 体检：揪出 MuJoCo 静默吃掉的质量
│   └── joint_sweep.py            # 关节扫描：世界轴向 / 镜像 / 钳口 / 联动残差 / 限位
├── scripts/
│   └── doctor.sh                 # 环境自检
└── .github/                      # issue / PR 模板
```

---

## 路线图

| 阶段 | 做什么 | 状态 |
| --- | --- | --- |
| ① 摸地形 | 盘点本机、调研业界、建仓 | ✅ 完成 |
| ② 升级 | 升到 text-to-cad 0.11，迁移 Robotiq 案例 | ✅ **已完成**，几何零差异 |
| ③ 接机器人 | 用新能力做一次「CAD → URDF → MuJoCo → 对比」 | ✅ **已完成**，查出 6 个静默行为，见 [`docs/07`](docs/07-CAD到URDF到MuJoCo.md) |
| ④ 真活① | 标定支架的 A/B 两方案参数化建模 + 数字对比 | ⬜ 待办 |
| ⑤ 真活② | MicroDuck 关节限位逐条对回 XL330 舵机规格 | ⬜ 待办 |
| ⑥ 分享 | 转公开，邀朋友贡献 | ⬜ 待办 |

**关于转公开**：现在仓库是 private。要公开：

```bash
gh repo edit youttiao/agent-3d-lab --visibility public
```

在转公开之前建议先清一遍：厂商件和别人的模型都不该入库（现在没放），
`examples/` 里的图是我们自己渲的（可以放）。

---

## 核心概念（三分钟版）

**Agent 不操作鼠标，Agent 写代码。**

| 环节 | 谁做 | 产物 |
| --- | --- | --- |
| 建模 | Agent 写 build123d Python 脚本 | 可编辑、可复算的 STEP |
| 分析厂商件 | Agent 调 `step.read()` + `leaves()` | 尺寸表 |
| 验证 | 内核算完 → **人看渲染图** | PNG |
| 机器人描述 | 从 CAD 模型导出 URDF + MJCF | `.urdf` / `.xml` |
| 体检 | 通用脚本量，不靠肉眼 | 数字 |

关键前提：**几何由内核算，结论靠看图。**
尺寸对不代表形状对，每改一次就要出一张图看。

完整流程见 [`docs/03-工作流速查.md`](docs/03-工作流速查.md)。

---

## 本机环境速记

macOS (Apple Silicon) · **text-to-cad 0.11.16**（uv tool 装在 `~/.local/bin/cad`）·
`build123d 0.13.0` + `cadquery-ocp-novtk 8.0.1.1`（跑在 `~/.cache/cad/base/` 的内核环境里）·
`uv 0.13.9` / `node` / `gh` / `mujoco`。

日常开工作区：
- `~/100-Vibe/3D-stp` —— CAD 项目（已迁到 0.11）
- `~/100-Vibe/dex-hand` —— 机器人方向
- `~/100-Vibe/3D-stp.bak-0.6.5` —— 升级前完整备份

---

## 参与

欢迎朋友一起贡献。三种参与方式：

1. **补文档** —— 把你踩过的坑写进 `docs/`，尤其是某一类软件的实操细节
2. **加案例** —— 放一个你做过的零件到 `examples/`，按现有格式写 README
3. **改进工具链** —— 如果你写了自定义 skill，放 `skills/` 并在 README 里说明

约定：
- 文档中文，代码/标识符英文
- 案例必须**可复现**：README 里写清怎么跑、跑出什么
- 厂商件、他人模型**不入库**，只放自研源码和产出，说明出处即可

---

## 上游

工具链 skill 全部来自 [`earthtojake/text-to-cad`](https://github.com/earthtojake/text-to-cad)（MIT）。
本仓库是自己的一套用法和案例，不改上游代码。

调研中提到的其他项目会在 `docs/01-技术路线全景.md` 里逐个给链接。
