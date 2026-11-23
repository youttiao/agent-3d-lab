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
| 核心工具链 | ✅ 已就绪，本机不用再装就能开工（`cadgen` + `build123d` + playwright/chromium） |
| CAD skill 套件 | ⚠️ 装了 13 个，但**落后上游五个版本家族**（0.6.6 vs 0.11.16），命令已改名 `cadgen`→`cad` |
| 调研文档 | ✅ 见 [`docs/01-技术路线全景.md`](docs/01-技术路线全景.md) |
| 第一个完整案例 | ✅ [`examples/robotiq-v-finger`](examples/robotiq-v-finger/README.md)（Robotiq 2F-85 夹爪 V 型槽指尖逆向） |
| 升级到 0.11 | 📋 方案已写好，见 [`docs/05-升级到0.11.md`](docs/05-升级到0.11.md) —— **会砸掉现有项目代码，要手工改** |
| URDF / 机器人工作流 | ⬜ 下一块拼图。**0.11 新增了 CAD→URDF/MJCF 自动生成和关节限位自动推导**，升级后才用得上 |
| GUI 建模软件（Blender / FreeCAD） | ⬜ 待装，但现在**不需要** |

一句话结论：**机械件走「代码参数化」路线，AI 生成网格那条路在 Mac 上不划算。**
完整理由见 [`docs/01`](docs/01-技术路线全景.md)。

> **最重要的一个发现**：上游 text-to-cad 已经在做我们现在想做的事——
> 从 CAD 模型自动生成 URDF/MJCF，自动推导关节限位，
> 并跟 MuJoCo Menagerie 和厂商原版做对比（`models/mujoco/`）。
> 我们本机这版（0.6.5）完全没有这些能力。

---

## 快速开始

```bash
# 1. 自查环境（退出码 0 = 可开工）
bash scripts/doctor.sh

# 2. 跑一遍示例
cd examples/robotiq-v-finger
python src/robotiq_v_finger.py              # 生成 STEP
cadgen step snapshot STEP/robotiq_v_finger.step tmp/finger.png

# 3. 起本地查看器，浏览器里转着看
cd ~/100-Vibe/3D-stp && cadgen viewer --host 127.0.0.1 --json
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
│   └── 05-升级到0.11.md           # 升级方案：破坏性变更清单、迁移步骤、回滚
├── examples/
│   └── robotiq-v-finger/         # 第一个完整案例：厂商件逆向重建
├── templates/
│   └── cad-project/              # 新 CAD 项目脚手架
├── scripts/
│   └── doctor.sh                 # 环境自检
└── .github/                      # issue / PR 模板
```

---

## 核心概念（三分钟版）

**Agent 不操作鼠标，Agent 写代码。**

| 环节 | 谁做 | 产物 |
| --- | --- | --- |
| 建模 | Agent 写 build123d Python 脚本 | 可编辑、可复算的 STEP |
| 分析厂商件 | Agent 调 `read_step` 读场景树和包围盒 | 尺寸表 |
| 验证 | 内核算完 → **人看渲染图** | PNG |
| 机器人描述 | Agent 直接编辑 URDF XML | `.urdf` + 校验通过 |

关键前提：**几何由内核算，结论靠看图。**
尺寸对不代表形状对，每改一次就要出一张图看。

完整流程见 [`docs/03-工作流速查.md`](docs/03-工作流速查.md)。

---

## 本机环境速记

macOS (Apple Silicon) · Python 3.14.6 · 已装 `cadgen 0.6.5` / `build123d 0.11.1` /
`ezdxf 1.4.4` / `playwright 1.63.0`(+chromium) / `uv` / `node` / `gh` / `mujoco`。

日常开工作区：
- `~/100-Vibe/3D-stp` —— CAD 项目（skill 装在这里）
- `~/100-Vibe/dex-hand` —— 机器人方向

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
