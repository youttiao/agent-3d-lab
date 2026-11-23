# 机器人描述与 URDF：怎么把数值调到物理上说得通

> 目标：**"看数模之间的关系，把 URDF 里的一些关键值调整到合理的位置"**
> 调研时间：2026-11-23 · 工具链：text-to-cad 0.11.16 的 `robot-simulation` skill

---

## 0. 先决定三件事

| 问题 | 决定 | 为什么 |
| --- | --- | --- |
| **用哪个格式当真相** | **URDF 1.0 手写**，旁边放 SRDF，MJCF 由它派生 | URDF 是唯一被所有消费者都理解的**树**语义：RViz、`robot_state_publisher`、MoveIt、Gazebo（`gz sdf -p`）、MuJoCo（`from_xml_path`）、PyBullet、Isaac、Genesis |
| **URDF 用哪个版本** | **1.0**（除非确定没人用 ROS-1 时代的 `urdf_parser_py`） | `urdfdom` 6.0 已支持 1.1（capsule、quat）/1.2（jerk），但 `urdf_parser_py` 和 ROS 2 的 `urdfdom_py` 1.2.1 **不支持** |
| **仿真器** | **MuJoCo**（本机已装） | Isaac 在 macOS 上**永远不会**有（要 Ubuntu/Windows + RTX 4080 起步，"没有 RT Core 的卡不支持"） |

> ⚠️ 一个例外：如果手是**欠驱动**（腱驱），URDF 单独表达不了耦合，
> 得同时写进 MJCF 的 `<equality><joint>` 和/或 SRDF 的 `<passive_joint>`。见 §6。

---

## 1. 五个物理门槛（**没有任何主流解析器完整覆盖**）

`urdfdom` 的 `check_urdf` 只检查六个惯性字段**存在且能解析**，不查物理。
MuJoCo 4.0 查了三角不等式（见 §3），但**权威的一般实现**是 iDynTree 的
`SpatialInertia::isPhysicallyConsistent()`：

> 设 `λ₁ ≤ λ₂ ≤ λ₃` 是关于质心的 3×3 惯性张量的特征值。刚体物理可实现 **当且仅当**
> ```
> Cxx = (λ₂ + λ₃ − λ₁)/2 ≥ 0
> Cyy = (λ₁ + λ₃ − λ₂)/2 ≥ 0
> Czz = (λ₁ + λ₂ − λ₃)/2 ≥ 0
> ```
> 因为 λ₁ ≤ λ₂ ≤ λ₃,约束最紧的是 `λ₁ + λ₂ ≥ λ₃` ——
> **主惯性矩上的三角不等式**。

> ⚠️ 正定性是**另一个更弱**的条件：三个正特征值的张量仍然可能物理上不可能。
> 这正是 `urdfdom` 会漏掉的那一类。

### 完整的五道门

| # | 检查 | 判据 |
| --- | --- | --- |
| 1 | 质量与基本合法性 | `mass > 0`，所有值有限，`ixx/iyy/izz > 0` |
| 2 | **主惯性矩三角不等式** | `λ₁+λ₂ ≥ λ₃`（有非对角项时先做特征分解） |
| 3 | **量级 vs 尺寸/质量** | 特征尺寸 `d`、质量 `m`，对角元应落在 `m·d²/10` 附近。**一个 0.5 kg、10 cm 的零件写 `ixx = 2.0` kg·m²，错了约 1000 倍** |
| 4 | 质心位置 | 在连杆包围盒内（或很接近） |
| 5 | 非对角项 | 除非零件在连杆系里本来就是歪的，`ixy/ixz/iyz` 相对对角元应该小。**大非对角项通常意味着张量写错了坐标系** |

**单位 bug 的特征**：CAD 质量属性出来的是 mm；kg·mm² 的惯性要**再乘 `1e-6`**
（长度进张量是平方、体积是立方），这还没算密度换算。
**门槛若恰好差一个 10 的整数次幂，先怀疑单位。**

### 可直接抄的检查器（只用 numpy）

```python
import numpy as np

def inertia_ok(m, I):
    if not (m > 0):
        return False, "mass<=0"
    I = np.asarray(I, float)
    if abs(I - I.T).max() > 1e-12:
        return False, "tensor not symmetric"
    lam = np.linalg.eigvalsh(I)
    if lam[0] <= 0:
        return False, f"non-positive eigenvalue {lam[0]}"
    if lam[0] + lam[1] < lam[2] * (1 - 1e-9):
        return False, f"triangle violated: {lam}"
    return True, f"principal moments {lam}"
```

### `cad urdf validate` 已经替你做的那部分

**报错**：树结构（一个根、名字唯一、父子存在）、关节类型、轴、限位、
mimic、每个 visual/collision 只有一个几何、本地网格缺失、**惯性不物理**（质量/对角元非正、张量非正定）。

**警告**：
- 省略 `<axis>`（读作 `1 0 0`）或轴不是单位向量
- 省略 `effort`/`velocity`
- fixed 关节上写 `<limit>`、continuous 关节上写 `lower`/`upper`
- 关节与连杆同名
- **有几何但没 `<inertial>` 的运动连杆**
- **主惯性矩违反三角不等式**
- **惯性与该连杆唯一图元碰撞体暗示的值相差 10 倍以上** ← 这就是第 3 道门的单位 bug 检测器
- 负的网格 `scale`、未知网格扩展名、`package://` 没解析
- `<robot>`/`<link>`/`<joint>`/`<visual>`/`<collision>`/`<inertial>` 下的未知元素
- 未定义的 `<material name>`

> ⚠️ **`OK` 那一行本身就是一个检查**：
> 根节点错了、运动关节数不对、找到的网格比文件里写的少、总质量不是这个机器人的——
> **这些是没有任何 finding 会报告的故障。**

> ⚠️ **诚实的边界**（上游自己的话）：
> *"一次干净的检查是护栏，不是证明：它无法显示轴是否对得上这台机器、
> 网格单位是否和 `scale` 匹配、规划组是否适合任务、增益是否正确。"*

---

## 2. 碰撞几何规则

**实测结论（2026 抽样）**：UR10e 和 Robotiq 2F-140 的碰撞网格
**就是它们自己的凸包**（`mesh_volume / convex_hull_volume = 1.0000`）；
iiwa14 的是**凹的**（体积亏 21%，0.878 / 0.791 / 0.777 / 0.953）；
Franka 用**两级**方案（每连杆细凸包 + 自碰撞用粗胶囊，`safety_distance = 0.03 m`）。

**没有任何一个主流手臂/手的描述文件用了多凸包 V-HACD/CoACD 分解。**
主流做法是**每连杆一个凸包**，放在独立的 `collision/` 目录，和 `visual/` 分开。

- ROS Wiki 自己的建议：**每个连杆尽量少面，理想情况下 < 1000**。
- **手的碰撞体以图元为主**：Allegro V4 = 11 个 `<box>`；
  Drake 的 Allegro = 17 box + 4 sphere；dex-urdf 的 LEAP = **67 box + 4 mesh**。
- **为什么凸包比凹网格好**（各引擎的原文）：
  - MuJoCo：*"碰撞检测限于**凸**几何体……用户指定的网格可以是凹的，但为碰撞目的会**被替换成它们的凸包**"*
  - Bullet：*"如果需要移动的凹三角网格，建议用 HACD 做凸分解"*
  - PhysX/Isaac：需要 cooking（默认 32 凸包、64 顶点/凸包、50 万体素、10% 误差）

### 凸分解工具（2026 现状）

| 工具 | 状态 |
| --- | --- |
| **CoACD** | **现在的默认**。`SarahWeiii/CoACD` ★1221（不是 `huangjq/CoACD`，那个已经 404）。`pip install coacd` |
| **V-HACD** | ⚠️ **已废弃归档**：`kmammou/v-hacd` README 写着 *"DEPRECATED & ARCHIVED，所有新开发和修复都转到 CoACD"*。Python 绑定是 `vhacdx` 或 `pyVHACD` |
| CuACD | 2026 新出的 GPU 版（~80–100× 快），但**只支持 Linux/Win x86_64 + NVIDIA sm_70+** |

```python
import coacd, trimesh
mesh = trimesh.load("link3.stl", force="mesh")
m = coacd.Mesh(mesh.vertices, mesh.faces)
parts = coacd.run_coacd(m, threshold=0.005, real_metric=True,
                        max_convex_hull=16, max_ch_vertex=64)
```

> `real_metric=True`（2026-04 加的）是**机器人尺度 CAD 用的模式**——阈值按米算，不是相对量。

### 给手臂+手的推荐顺序

1. **图元优先**（box/cylinder/sphere/capsule 每连杆一个）—— 这是 IsaacLab 的 Franka 默认
2. 否则**每连杆一个凸包**，导出到独立的 `collision/*.stl`
3. **绝不发布凹的碰撞网格**（iiwa 那 21% 体积亏是潜伏问题：MuJoCo 会静默重新凸包化，Bullet 要求 HACD，PhysX 要 cooking）
4. CoACD 只留给真正凹的零件——而共识是**手臂和手不需要**
5. 环境碰撞和自碰撞分开（Franka 式：世界用细凸包，自碰撞用粗胶囊，~0.03 m 边距）

---

## 3. MuJoCo 的坑（**本机相关，都验证过**）

### 3.1 ⚠️ URDF 模式下 **固定在 world 上的体，质量被静默丢弃**

URDF 模式强制 `fusestatic=true`，而 `FuseStatic` 拒绝把质量融进 world。

> ⚠️ **不要只记住「base link」。**
> 丢的不是「base link」这**一个** link，是**所有固定在 world 上的体**。
> 2026-11-23 的夹爪实测里，base link 是空的（0 kg），
> 真正被丢的是**掌板**——它固定在 world 上，于是 0.75 kg 直接消失。
> 一个整机 URDF 里的配重块（电池、配重、传感器）全都会这样。

**修法**：在 URDF 里加

```xml
<mujoco>
  <compiler fusestatic="false"/>
</mujoco>
```

验证：base 1.0 kg + arm 2.0 kg，不加时 `body_mass=[0., 2.]`，加了是 `[0., 1., 2.]`。

> **这是我们这个任务里最重要的一条**：
> 不加它，你的读回结果会显示 `body_mass[0] == 0`，
> 然后你会"发现"一个其实并不存在的缺失惯性。

> ✅ **本机实测（MuJoCo 4.0.1, 2026-11-23）**：
> ```
> [默认]              body_mass = [0. 2. 2.]   总质量 4.0000 kg
> [fusestatic=false] body_mass = [0. 1. 2. 2.] 总质量 5.0000 kg
> ⚠️ base link 的 1.0000 kg 被静默丢弃了
> ```
> 用 `checks/urdf_probe.py` 可以一键查出来（它会自动对比两种模式）。

> ✅ **夹爪实测（同日）**：URDF 声明 0.81 kg，MuJoCo 加载后只剩 **0.06 kg** —— 丢了 93%。
> 而 `cad urdf validate` 报的是 `total mass 0.81 kg`（它看的是 URDF 文件本身，
> 看不到加载之后发生的事）。**校验器查不出这一类问题。**

### 3.1b ⚠️ URDF 模式下 `<mujoco>` 扩展块**只认 `<compiler>` 的属性**

MuJoCo 允许在 URDF 里塞一个 `<mujoco>` 块来调 MuJoCo 专属设置。
但 4.0.1 实测下来，**只有 `<compiler>` 的属性会被读**，其余静默忽略：

| 塞进 `<mujoco>` 的 | 生效？ |
| --- | --- |
| `<compiler fusestatic="false"/>` | ✅ |
| `<compiler boundmass="0.5"/>` / `meshdir` / `autolimits` / `angle` | ✅ |
| `<option>` `<size>` `<visual>` | ❌ 静默忽略 |
| `<contact><exclude/></contact>` | ❌ 静默忽略 |
| `<equality>` `<worldbody>` `<actuator>` | ❌ 静默忽略 |
| 一个**根本不存在的标签** | ❌ 静默忽略（连乱写的都不报错） |

**这条很要紧**：很多教程教你用 `<mujoco><contact><exclude …/></contact></mujoco>`
来修 URDF 的接触问题 —— 在 MuJoCo 4.0.1 上它**不报错，也不生效**。

### 3.1c ⚠️ URDF **没有**「这两件不碰」的语法

并行夹爪、导轨滑块这类机构，手指本来就贴在掌板上。
MJCF 有 `<exclude>`，导出器会自动加：

```xml
<contact>
  <exclude body1="palm" body2="finger_right"/>
  <exclude body1="palm" body2="finger_left"/>
</contact>
```

URDF **完全没有这个概念**。实测静置时的接触数：MJCF 0 个，URDF 6 个
（掌板 × 每根手指，间距全为 0）。

后果不是「多算一点接触力」，是**机构动不了**：默认 μ=1，
0.5 N 的驱动力被摩擦直接抵消，60 步只移动 0.64 mm（MJCF 版本是 13.2 mm）。

> **结论：给 MuJoCo 用 MJCF，给 ROS 用 URDF。**
> 只剩 URDF 时只能靠改几何让两者错开 —— 见 [`07-CAD到URDF到MuJoCo.md`](07-CAD到URDF到MuJoCo.md)。

### 3.1d ⚠️ URDF 的 `<visual>` / `<collision>` 在 MuJoCo 里**塌成一个**

URDF 允许每个零件写两套几何（5 个 `<visual>` + 5 个 `<collision>`），
MuJoCo 的 URDF 加载器按名字去重 → 只生成 **5 个 geom**，一个零件一个碰撞几何。
MJCF 里是分开的（视觉组 `contype=0 conaffinity=0`，碰撞组正常）。

**后果**：一份 URDF 在 MuJoCo 里没法给同一个零件不同的视觉和碰撞形状。

### 3.1e ⚠️ 关节等式和关节限位**都是软约束**

| | 行为 |
| --- | --- |
| `<mimic>` / `<equality><joint>` | 软约束。稳态有残差（实测 0.26 mm @ MJCF、0.41 mm @ URDF）。要更硬调 `solref[0]`（建模指南建议 0.004～0.01） |
| 关节限位 | 软约束。`mj_forward` **不报错也不夹回**：把 qpos 直接设成 `-0.011835`（超限），右指照样在那个位置 |

> 做行程校核时不能指望 MuJoCo 帮你挡住越界值 —— 得自己查。


### 3.2 ⚠️ MuJoCo **4.0 之前静默忽略 URDF 的 `<mimic>`**

| MuJoCo 版本 | URDF `<mimic>` |
| --- | --- |
| ≤ 3.12.0（2026-08-20） | **静默忽略**。mimic 关节变成独立自由度，**不打印任何警告** |
| ≥ 3.13.0（2026-09-09） | 翻译成 `mjEQ_JOINT` 等式约束 |

> **本机已从 3.12.0 升到 4.0.1**（2026-11-23）。
>
> ⚠️ 升级踩了个坑：**4.0 把包拆开了**（`mujoco-core` / `mujoco-studio` / `mujoco`），
> 3.12 的残留目录会让 `import mujoco` 直接报
> `ModuleNotFoundError: No module named 'mujoco._specs'`。
> 修法：`pip install --force-reinstall --no-deps mujoco mujoco-core`

> ✅ **本机实测**：一个两关节、`j2` mimic `j1`（multiplier=1.5, offset=0.1）的 URDF：
> ```
> njnt=2  neq=1
> 等式: mjEQ_JOINT  obj1=1 obj2=0  polycoef=[0.1, 1.5, 0.0, 0.0, 0.0]
> ```
> 三件事一次证实：
> ① `<mimic>` 生效了（`neq=1`，3.12 时是 0）；
> ② **`polycoef` 是常数项在前**（0.1 = offset，1.5 = multiplier）；
> ③ **`obj1` 是从动关节**（obj1=1 是 j2，obj2=0 是 j1）。

### 3.3 MuJoCo 的 `<equality><joint>` 语义（实测，别信文档）

各社区文档互相矛盾，实测结论：

> **`name1 = d0 + d1·name2 + d2·name2² + d3·name2³ + d4·name2⁴`**
> —— `polycoef` 是**常数项在前**，`name1` 是**被动的那个关节**。

| `polycoef` | 收敛到的 `q1, q2` | 拟合 |
| --- | --- | --- |
| `0 1 0 0 0` | 0.00089, 0.00089 | `q1 = q2` ✔ |
| `0 -1 0 0 0` | −0.03833, +0.03833 | `q1 = −q2` ✔ |
| `0 3 0 0 0` | −0.02442, −0.00814 | `q1 = 3·q2` ✔ |
| `0 0 0 0 2` | 0.00000, −0.00342 | `q1 = 2·q2⁴` ✔ |
| `1 0 0 0 0` | `efc_pos[0] = −0.6` | 常数项是 `data[0]` ✔ |

> ⚠️ `mjtEq` 枚举里 **`mjEQ_JOINT = 2`**（不是 6）。
> `mjEQ_FIXED=0, mjEQ_CONNECT=1, mjEQ_JOINT=2, mjEQ_TENDON=3`。

### 3.4 其他会**静默**发生的行为

| 情况 | MuJoCo 的行为 |
| --- | --- |
| `<revolute>` **没有 `<limit>`** | `jnt_limited=[False]`，`jnt_range=[0,0]` —— **没有任何提示** |
| `<limit lower="-1">` **没有 upper** | `jnt_range=[-1,0]`，`jnt_limited=[False]` —— upper 静默变 0 |
| `<inertial>` 惯性全零 | `fullinertia[0] = mjNAN` → 回退到按几何密度推断，**没有提示** |
| **未知的 URDF 标签**（`<gazebo>` `<transmission>` `<material>`） | **静默忽略**。URDF **不做 schema 校验**，解析器只走 `link` 和 `joint` 元素 |
| `<limit velocity>` | 被忽略（"no maxvel in MuJoCo"） |

### 3.5 会命中的致命错误串（原文）

```
mass and inertia of moving bodies must be larger than mjMINVAL
mass and inertia cannot be negative
inertia must satisfy A + B >= C; use 'balanceinertia' to fix
inertia must have positive eigenvalues
range[0] should be smaller than range[1] in joint
axis too small in joint
fullinertia and diagonal inertia cannot both be specified
body mass is too small, cannot compute center of mass
mesh '%s' not found in geom %d
```

> ⚠️ **`balanceinertia="true"` 会把三个对角元静默设成平均值，把真实错误藏起来。
> 审计时永远不要开。**

### 3.6 macOS 专属

- **MuJoCo 4.0 在 import 时校验 `MUJOCO_GL`**。
  `osmesa` 和 `egl` 是 **Linux 专属**——在 macOS 上会直接
  `RuntimeError: invalid value for environment variable MUJOCO_GL: osmesa`。
  macOS 无头用 **`MUJOCO_GL=disable`**。
- `pip install pybullet` 在 arm64 上编译失败（内置 zlib 1.2.8，2007 年的）。
  要用就 `pip install pybullet-arm64==3.2.8`（**没有 cp314 wheel**）。
- Gazebo 在 macOS 上要用 **conda-forge**，Homebrew 那条已经死了。

---

## 4. 网格单位的坑（**"数模对不上"最常见的真实原因**）

| 格式 | 单位 |
| --- | --- |
| **URDF** | **米**，弧度 |
| **glTF 2.0 / GLB** | **米**（Khronos glTF 2.0 §3.4 原文） |
| **COLLADA (.dae)** | 文件里声明：`<asset><unit meter="…"/>` |
| **USD** | 可配，**默认厘米** —— 写 `metersPerUnit = 1.0` |

### ⚠️ COLLADA 的 0.01 陷阱（从代码证明）

`newton-physics/urdf-usd-converter` 的 `_impl/conversion_collada.py`：
默认值是 1.0，除非文件里说了别的；而该项目的测试夹具
`tests/data/assets/box_unit_cm.dae` 里就写着 `<unit name="meter" meter="0.01"/>`。

→ **从 Blender 默认设置导出的 DAE 小了 100 倍。**

修法：导出时 unit=1.0，或者在 `<mesh>` 上加 `scale="0.01 0.01 0.01"`
（Robotiq 的 URDF 就是给 mm 网格加 `scale="0.001 0.001 0.001"`）。

**最稳的做法：把修正后的 scale 烘进导出的网格**，这样下游完全不需要 `scale=` 属性——
一整类 bug 直接消失。

### 自动判断 scale

```python
import trimesh
m = trimesh.load("link3.stl", force="mesh")
ext = m.extents                      # 文件单位下的包围盒
ratio = ext.max() / 0.08             # 0.08 m = 你知道尺寸的腕部法兰
for f in (1.0, 1e-3, 1e-2, 1e2, 1e3):
    if abs(ratio * f - 1.0) < 0.15:
        print("likely scale:", f)
```

两个交叉验证：**包围盒 vs 密度**（mm 网格算出的"密度"会差 10⁶ 倍，一眼可见）、
**包围盒 vs URDF 自己的 `<collision>`**（`<cylinder radius="0.06">` 旁边一个 120 单位宽的网格 ⇒ mm）。

---

## 5. 关节原点、轴、限位、零位

### 原点

关节的 `<origin>` 必须落在**物理转轴**上（子连杆坐标系与关节坐标系重合）。
如果网格质心不在转轴上，误差会被视觉原点吸收掉——
**这是最常见的 URDF bug，而且所有检查器都看不见。**

### 轴

存在、三个有限数、非零、单位长度、在关节系里表达、**并且正方向有文档**。
记住：省略的轴 MuJoCo 读作 `1 0 0`，只有一条警告。

### 限位

- `lower < upper`
- `effort` = 执行器连续扭矩（N·m），从数据手册来
- `velocity` 用 rad/s（MuJoCo 忽略它；IsaacLab 和 MoveIt 不忽略）
- **绝不存角度** —— URDF 是弧度

### 零位约定（最容易踩且没人提醒）

> **装配位就是每个关节的零位。**
> 关节限位 = 关节量程 − 装配时的角度：
> 一个指头在 0°~40° 量程里以 30° 装配，写出去就是 **−30°…+10°**，**不报警告**。

有控制器的，描述文件的零位应该对齐**控制器的零位**。

### 从 CAD 自动推限位

```bash
cad model ranges "$ID" [--step 1] [--clearance 0.3] [--joint NAME]
```

> *"每个关节的止点，从几何找出来：它的零件第一次碰到另一个零件的地方"*
> —— 按角度（转动）或毫米（滑动）扫，默认间隙 0.3 mm。

**这算出来的是几何限位。舵机自己的行程更窄时，以数据手册为准。**
（这就是 MicroDuck 那个 XL330 的情况。）

---

## 6. 手：腱驱 vs 独立自由度

| 机制 | 怎么写 | 在哪 |
| --- | --- | --- |
| **MuJoCo `<fixed>` 腱** | `<fixed name="rh_FFJ0"><joint joint="rh_FFJ1" coef="1"/><joint joint="rh_FFJ2" coef="1"/></fixed>` + `<motor name="rh_FFJ0" tendon="rh_FFJ0" ctrlrange="0 3.1416"/>` | Shadow `sr_common`、Menagerie `shadow_hand` |
| **MuJoCo `<spatial>` 腱** | 带滑轮、弹簧的缆绳走向 | Menagerie `tetheria_aero_hand_open` |
| **MuJoCo `<equality><joint>`** | `<equality><joint joint1="Gripper" joint2="Gripper_mimic" polycoef="0 1 0 0 0"/></equality>` | Aero Hand、ROBOTIS Menagerie 分支 |
| **URDF `<mimic>`** | `<mimic joint="index_proximal_joint" multiplier="1.06399" offset="-0.04545"/>` | dex-urdf Inspire、Unitree Inspire、RH56DFX、OpenManipulator-X |

### `<mimic>` 支持矩阵

| 仿真器 | `<mimic>` |
| --- | --- |
| MuJoCo ≤ 3.12.0 | ❌ 静默无效（**本机就是这个**） |
| MuJoCo ≥ 3.13.0 | ✅ → `mjEQ_JOINT` |
| Isaac Sim / Omniverse | ❌(2021) → ✅4.5+ → ✅ via **Newton** in 6.0；但 **PhysX 生产路径不写 `PhysX MimicAPI`** |
| MoveIt 2 | 部分。**SRDF 没有 mimic 概念**，用 `<passive_joint>` |
| Gazebo | 只能靠插件（`gazebo_plugins/mimic_plugin.h`） |
| PyBullet | 部分。读 `<mimic>`，但正解是显式约束 |

> **实用规则**：耦合**只写一次**（URDF `<mimic>`），然后检查目标。
> 如果是 MuJoCo < 3.13、Isaac 的 PhysX 路径、或者要做 MoveIt 规划，
> 就**必须再**用 `<equality><joint>`（MuJoCo）、`<passive_joint>`（SRDF）、
> 或两个关节都放显式执行器表达一遍。

### 四个经典失败

**(a) 过驱动 vs 正确的欠驱动。**
URDF 没法说"一个执行器带两个关节"。Shadow 是教科书案例：24 关节、20 执行器。
你的选择：每关节独立执行器（指尖力量就不对了），
或把从动关节标成 mimic/passive（多数仿真器会丢掉耦合）。
MuJoCo 的答案是腱：从动关节仍有自己的 `qpos`（`nq` 保持 24），
但广义力来自腱而不是执行器。
**检测技巧：明知欠驱动的手，如果 `nu == nq`，耦合丢了。**

> 务实的行业默认：**Menagerie 的 Allegro 是 16 关节 / 16 个独立执行器，
> 拇指的耦合被当成独立的建模。只在耦合会改变抓取时才建模耦合。**

**(b) 闭合运动链。**
URDF 是严格的**树**（每连杆至多一个父节点），闭合环（带连杆的平行夹爪、四连杆腱回路）表达不了。
变通：**剪开环**（把一个关节做成被动），把耦合用 `<mimic>`/`<equality>`/腱表达。
MoveIt Setup Assistant 在闭合链 URDF 上有文档记载会挂起或死循环。

**(c) 相邻手指连杆之间的自碰撞 —— 手部仿真的头号问题。**
三个成熟方案：

- **SRDF `<disable_collisions>`**（MoveIt）。
  Shadow DEX-EE 的生产 SRDF 里有 **120 对**（15 `Adjacent`、41 `Never`、64 `User`）：
  ```xml
  <disable_collisions link1="h0_F0_J0_link" link2="h0_F0_base" reason="Adjacent"/>
  <disable_collisions link1="h0_F0_J0_link" link2="h0_F0_distal" reason="Never"/>
  ```
  `reason` 的四种：Adjacent（永远关）、Never（几何上不可能）、
  Default（home 位姿重叠）、Always（永久重叠）。
  ⚠️ *"Never in Collision 是**采样**出来的，所以没有保证"* —— 要手工调。
  ⚠️ *"别为了消 setup_assistant 的红字盲关——删掉一对真实存在的碰撞，
  planner 会生成穿模轨迹。"*
- **MJCF `<contact><exclude>`**。实测数量：`wonik_allegro` **5** ·
  `shadow_hand` **2** · `leap_hand` **18** · `tetheria_aero_hand_open` **46** ·
  `sharpa_wave` **26** · `shadow_dexee` **6**
- **把碰撞几何换成图元/凸包** —— 这也让 (b) 变得可解

**(d) 非最小坐标 / 手部协同。**
URDF 原生表达不了协同。三种做法：
(1) 控制器里的**零空间投影**（不动 URDF）；
(2) MJCF 的**缩减坐标**（几个"协同"关节 + `<equality>`）；
(3) MoveIt SRDF 的 `<passive_joint>`。

> 协同子空间**到不了奇怪的姿态或精确的指尖位置**——
> 这是全关节空间抓取生成器现在大多放弃纯 eigengrasp 参数化的原因。

---

## 7. 操作顺序（针对我们那个具体任务）

> *"拿一个机械臂 + 手的 URDF,检查数值是否物理上说得通,
> 修关节原点和限位,让网格和运动学树对上。"*

### Step 0 —— 定目标、定版本

URDF 1.0 / 1.1 / 1.2？列出消费者：RViz / `robot_state_publisher` / MoveIt /
Gazebo / MuJoCo / Isaac。**有 ROS-1 时代的消费者就留在 1.0。**

### Step 1 —— 冻结基线，先读树，不要改

先展开 xacro（没有 ROS 就用 `pip install xacrodoc`，
`XacroDoc.from_file(p).to_urdf_file()`），然后**把连杆/关节表打印出来**：

```bash
cad urdf validate model.urdf --json > baseline.json
```

```python
from yourdfpy import URDF
u = URDF.load("model.urdf", mesh_dir="<package root>")
u.validate()                       # bool；细节在 u.errors
for j in u.robot.joints:
    print(j.name, j.type, j.parent, "->", j.child, j.origin, j.axis, j.limit)
```

> **之后每个名字都必须从这个表里复制，绝不能凭记忆敲。**

### Step 2 —— 先查网格，再动任何数字

对每个 `<mesh>`：读文件原生单位（DAE 的 `<unit meter>`、glTF 是米、STL 无单位）、
量包围盒、和你**确实知道**的尺寸对比。
**把修正后的 scale 烘进导出的几何。**
永远不要在一个模型里混 `scale="0.001"` 的 DAE 和 `scale="1.0"` 的 STL。

> **"网格和运动学树对上"其实是在这一步决定的**——
> 1000 倍的 scale bug 会让后面所有数字都失去意义。

### Step 3 —— 修碰撞几何

每连杆：一个图元，或者**一个凸包**，导到独立的 `collision/`。
目标 **< 1000 三角形**。CoACD 留给真正凹的零件。

### Step 4 —— 从修正后的几何重算惯性

```python
import trimesh
m = trimesh.load("collision/link3.stl", force="mesh")
m.merge_vertices(); m.fill_holes(); assert m.is_watertight
m.density = 2700.0                                  # 文档化的假定密度
mp = m.mass_properties
I, com = mp.inertia, mp.center_mass                # 关于质心，kg·m²
print(f'ixx="{I[0,0]}" ixy="{I[0,1]}" ixz="{I[0,2]}" '
      f'iyy="{I[1,1]}" iyz="{I[1,2]}" izz="{I[2,2]}"')
```

> `mp.inertia` 是**关于质心的**（已经做了平行轴平移）并且**乘过密度** → kg·m²。
> **非对角项自带负的惯性积符号**（`inertia[0,1] = -(…)`）——这正是 URDF 期望的，
> 所以 `ixy = I[0][1]` 可以直接写。

写 `<inertial>` 时，**把 `rpy` 对齐到主惯性轴**，这样所有惯性积都是零，
ROBOTIS/ROS Wiki 推荐的"负惯性积约定"问题直接消失。

**如果每连杆的质量未知**：拿数据手册的总质量，按体积分，
**然后把每个执行器的质量加在它自己的关节上**——
硬件的质量在电机和减速箱里，在关节上；纯按体积分会让长连杆的惯量偏几十个百分点。

### Step 5 —— 跑五道门

用 §1 的检查器 + `cad urdf validate`。
⚠️ **网格连杆的"量级"检查 `cad urdf validate` 不覆盖——那道门得自己写。**

### Step 6 —— 修关节原点和限位

见 §5。**如果你有 CAD**：

```bash
cad model ranges "$ID"                        # 几何限位
cad model export "$ID" robot.urdf --zero home  # 整个文件从模型重新生成
```

> **永远不要手改生成出来的文件**——改模型，然后重新导出。
> 这是本仓库路线图第 ③ 项，也是"让网格和运动学树对上"最短的路。

### Step 7 —— 逐个关节扫

```bash
cad urdf snapshot robot.urdf shoulder.png --camera front --pose '{"shoulder_pitch": 60}'
```

> *"只有把每个关节都动一遍，才会暴露符号反了、轴错了、原点偏了、或者限位太宽。"*
> 正转是从轴的正端看过去的逆时针。**每个可动关节，两个极限都要扫。**
> **这是唯一能抓出符号反了的步骤，没有任何校验器能做到。**

### Step 8 —— 用第二个独立工具交叉验证

```bash
MUJOCO_GL=disable python - <<'PY'
import mujoco
m = mujoco.MjSpec.from_file("model.urdf")   # 先加 <mujoco><compiler fusestatic="false"/></mujoco>
m2 = m.compile()
print(m2.body_mass, m2.body_inertia, m2.body_ipos, mujoco.mj_getTotalmass(m2))
PY
```

或者 `cad mujoco check scene.xml --json`。

### Step 9 —— SRDF（如果 MoveIt 在范围内）

从**证据**（URDF 邻接 + MoveIt Setup Assistant 采样）生成禁碰对，不要凭想象。
mimic 关节列成 `<passive_joint>`。`cad srdf validate --strict` 逐个名字、链、状态、对子交叉核对。

### Step 10 —— 出报告

按上游 `guardrails.md` 的约定：哪个文件、给哪个消费者、哪个版本；
**每项检查都写了名字**；每项跳过的检查和原因；假设和占位值（标出来）；
没解决的资源路径。**跳过的检查是要知道的风险，不是通过。**

---

## 8. 命令速查

```bash
cad --version                                   # 0.11.16
cad urdf validate robot.urdf [--strict] [--packages NAME=PATH] [--json]
cad srdf validate robot.srdf --strict
cad mujoco check scene.xml [--strict] [--json]
cad urdf snapshot robot.urdf review.png --camera front --pose '{"shoulder_pitch": 60}'
cad model ranges "$ID" [--step 1] [--clearance 0.3] [--joint NAME]
cad model export "$ID" robot.urdf [--zero home]
cad run src/gripper_mujoco.py                  # 跑一个 MuJoCo function
cad run mujoco-studio --model path/to/scene.xml
cad mcp                                          # MCP server (stdin/stdout)
```

**CAD → URDF 的映射**（`from-cad.md`）：

| 模型里 | 写成 |
| --- | --- |
| build123d 的 joint，`connect_to` | 连杆 + 关节，量程围绕**装配位 = 零位** |
| `mechanism_state(...)`，起名 `home` | MJCF keys |
| `gear_pair`、`rack_and_pinion_pair` | `<equality><joint>`；`<mimic>` |
| `part.material`、`mass()`、`point_mass()` | 精确的 `<inertial>`（内核算的，kg·m²） |
| `frame(part, name, location)` | 一个 site；一个空连杆 |
| `body(part, name)` | 子 body；fixed joint 上的连杆 |
| `limits(assembly, joint, effort=, velocity=)` | `actuatorfrcrange`；`<limit>` |
| `free(assembly)` | `<freejoint>` |

---

## 9. 手和手臂的开源资源

| 资源 | ★ | 适合什么 |
| --- | --- | --- |
| [`dexsuite/dex-urdf`](https://github.com/dexsuite/dex-urdf) | 389 | **最佳起点**。9 只手（allegro / shadow / schunk / ability / leap / barrett / inspire / dclaw / panda_gripper），纯 URDF + 相对路径网格 + 独立的 visual/collision |
| [`mujoco_menagerie`](https://github.com/google-deepmind/mujoco_menagerie) | 4.4k | MJCF 基准。每个模型都有 **README 写着编号的"URDF → MJCF 推导步骤"**、CHANGELOG、单独的 LICENSE。已上 PyPI（`mujoco-menagerie`） |
| [`shadow-robot/sr_common`](https://github.com/shadow-robot/sr_common) | 36 | **最被低估的资产**：一整套 MJCF，含**欠驱动变体**和真实的腱定义。24 关节 / 20 执行器 |
| [`ookkshirsagar/rh56dfx_description`](https://github.com/ookkshirsagar/rh56dfx_description) | 16 | **mimic 语义最好的文档**。8 个主动 + 6 个 mimic，附 MoveIt 的 `<passive_joint>` 配方 |
| [`robot_descriptions.py`](https://github.com/robot-descriptions/robot_descriptions.py) | 851 | **取件器**，226 个描述模块。`uvx robot_descriptions pull <name>`。含 `robotiq_2f85`、`leap_hand_v1`、`allegro_hand`、`ur10e` |
| [`arounamounchili/linkforge`](https://github.com/arounamounchili/linkforge) | 294 | "机器人描述的 LLVM"。Blender 扩展 + 无依赖的 `linkforge-core`，带**运动学 linter**（拓扑错误、断链、**非物理惯性**），导出 URDF/XACRO/SRDF |
| [`dfki-ric/phobos`](https://github.com/dfki-ric/phobos) | 914 | Blender 插件，**从质量和形状自动生成惯性张量**、合并连杆惯性、自动生成碰撞体。⚠️ Blender 5.0 兼容性有 open issue |
| [`OpenLegged/URDF-Studio`](https://github.com/OpenLegged/URDF-Studio) | 503 | 浏览器里的 URDF 工作台，导出 URDF/MJCF/USD/SDF/Xacro |
| [`Democratizing-Dexterous/step2urdf`](https://github.com/Democratizing-Dexterous/step2urdf) | 234 | **STEP → URDF**（2026-03 新建） |
| [`adamheins/xacrodoc`](https://github.com/adamheins/xacrodoc) | 75 | xacro → URDF **和** MJCF，**不需要 ROS** |

**一个明确的"别去查"**：
**没有开源的 DLR 手**——`dlr-rm/hand_system`、`hw_hand`、`HAND-I`、`hitech`、`HAWI` 全部 404，
DLR-RM 组织（~140 个仓库）里没有手相关的仓库。别让 Agent 去那儿找。

**踩坑提醒**：
- `dex-urdf` 有个 0★ 的过期 fork 会 301 重定向过去（`tesollo-admin/dex-urdf`）——认准 `dexsuite/dex-urdf`。
- **Inspire 手没有官方仓库**，三个替代品对 mimic 比例的写法互相矛盾
  （thumb ×1.334 / ×1.6 / ×1.1425）——这是个真实的坑。
- Unitree 的 MJCF `g1_body29_hand14.xml` **把 URDF 的关节范围取了负**
  （URDF `0…1.5708` → MJCF `range="-1.5708 0"`）。把 URDF 限位抄进 MJCF 会把卷曲方向反过来。
- **Allegro 的某些非官方分支的惯性矩阵不是 SPD**——Drake 重算过全部。
  看到明显不合理的惯性先怀疑这个。

---

## 10. 本机的准备状态

```bash
# ✅ 已完成（2026-11-23）
python3 -m pip install "mujoco==4.0.1"     # 从 3.12.0 升上来；4.0 拆包了，
                                            # 3.x 残留要 --force-reinstall --no-deps
python3 -m pip install trimesh yourdfpy

# 可选：Gazebo 的惯性读回（gz sdf --inertial-stats）
conda create -n gzjetty -c conda-forge gz-jetty

# 可选：PyBullet（DIRECT 模式，不碰 OpenGL）
python3 -m pip install pybullet-arm64==3.2.8    # ⚠️ 没有 cp314 wheel
```

> ⚠️ **MuJoCo 4.0 拆包**：`mujoco-core` / `mujoco-studio` / `mujoco`。
> 从 3.x 升上来若报 `ModuleNotFoundError: No module named 'mujoco._specs'`，
> 用 `pip install --force-reinstall --no-deps mujoco mujoco-core` 修。

`check_urdf` 和 `ros2` 在 macOS 上没有 —— 报告时**写成"跳过"，不要写成"通过"**。

**体检脚本**（本仓库 `checks/urdf_probe.py`）：把 MuJoCo 最容易静默吃掉的东西显式查出来。

```bash
MUJOCO_GL=disable python3 checks/urdf_probe.py robot.urdf
```

**关节扫描脚本**（本仓库 `checks/joint_sweep.py`）：
量关节的世界轴向、镜像是否对称、钳口开度、联动残差、限位行为。
MJCF 和 URDF 各扫一遍，两边的数字应该逐位一致。

```bash
MUJOCO_GL=disable python3 checks/joint_sweep.py
```

---

## 链接

- [MuJoCo](https://github.com/google-deepmind/mujoco) ★18.4k · [4.0.1 发布说明](https://github.com/google-deepmind/mujoco/releases)
- [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) ★4.4k
- [ros/urdfdom](https://github.com/ros/urdfdom) ★138（6.0.2，URDF 1.2 支持）
- [iDynTree](https://github.com/gbionics/idyntree) ★237（`isPhysicallyConsistent`）
- [newton-physics/urdf-usd-converter](https://github.com/newton-physics/urdf-usd-converter) ★78
  —— **`docs/concept_mapping.md` 是能找到的最好的 URDF 语义参考**
- [SarahWeiii/CoACD](https://github.com/SarahWeiii/CoACD) ★1221
- [dexsuite/dex-urdf](https://github.com/dexsuite/dex-urdf) ★389
- [shadow-robot/sr_common](https://github.com/shadow-robot/sr_common)
- [robot_descriptions.py](https://github.com/robot-descriptions/robot_descriptions.py) ★851

---

## 相关文档

- [`07-CAD到URDF到MuJoCo.md`](07-CAD到URDF到MuJoCo.md) —— 一次端到端的实测记录，
  含 MJCF/URDF 的分工建议、镜像为什么靠关节轴、两个 MuJoCo 的 API 细节

