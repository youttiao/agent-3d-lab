# 一次完整的往返：CAD → URDF → MuJoCo

这份文档记录 2026-11-23 做的一次端到端实测：
从一个 **build123d 参数化模型**出发，导出 URDF 和 MJCF，交给 MuJoCo 加载、驱动、量尺寸。

结论先说：**两个格式都能加载、能运动，但它们不是等价的东西。**
URDF 丢质量、表达不了接触排除、不能带关键帧、也不能带执行器。
这不是 MuJoCo 的缺陷，是 URDF 这个格式的边界 —— 但**每一项都是静默的**，
`cad urdf validate` 一个都查不出来。

> 复现工程在 `~/100-Vibe/3D-stp`（模型 `src/gripper_mechanism.py`）。
> 本文所有数字都是那台机器上跑出来的，命令见文末「可复现清单」。

---

## 1. 被测对象：为什么选一个夹爪

夹爪是检验机器人描述的好样本，因为它同时踩中所有难点：

| 难点 | 夹爪上的体现 |
| --- | --- |
| 有真正的关节 | 两个手指各一个移动关节 |
| 有耦合 | 一个齿轮 + 两条齿条 → 两指联动 |
| 限位不来自几何 | 并行夹爪的钳口停在工件上，工件不在模型里 → 行程得来自驱动器 |
| 有质量分布 | 掌板 + 舵机（点质量）+ 手指 |
| 有接触 | 手指本来就贴着掌板滑 |

关键是第三条。**夹爪的行程不能靠几何算出来**：
`cad model ranges` 对两个滑轨都返回 `clear`，理由是
「沿导轨方向接触挡不住任何东西」—— 因为真正挡住它的是工件，工件不在模型里。

所以行程只能来自驱动器的数据手册。本例里 `CLOSE_TRAVEL = 6.8345 mm` 不是随手填的，
它是从 CAD 几何反推出来的：让两个 V 槽口平面正好合拢到 0。

实测验证（钳口 = 两个 V 槽口平面的世界间距）：

| 关节位置 | 右指世界 X | 左指世界 X | 钳口 |
| --- | --- | --- | --- |
| −6.8345 mm（闭合限位） | 11.0000 mm | −11.0000 mm | **0.0000 mm** |
| 0（gripping） | 17.8345 mm | −17.8345 mm | 13.6690 mm |
| +12 mm（张开限位） | 29.8345 mm | −29.8345 mm | 37.6690 mm |

MJCF 和 URDF 给出**逐位相同**的结果。

---

## 2. CAD 侧：声明式建模

0.11 版的建模接口是「声明关系」，不是「画图」：

```python
@model
def gripper():
    palm  = _palm()
    right = _finger_part("right")
    left  = _finger_part("left")

    r_axis = bd.Axis((half, 0.0, rail_z), (1, 0, 0))          # 右指沿 +X
    r_slide = bd.LinearJoint("right", palm, axis=r_axis,
                             linear_range=(-CLOSE_TRAVEL, OPEN_TRAVEL))
    bd.RigidJoint("right", right, bd.Location(r_axis.position))
    r_slide.connect_to(right.joints["right"], position=0)

    l_axis = bd.Axis((-half, 0.0, rail_z), (-1, 0, 0))         # 左指沿 −X
    l_slide = bd.LinearJoint("left", palm, axis=l_axis, ...)
    ...
    gripper = bd.Compound(children=[palm, right, left], label="gripper")

    rack_and_pinion_pair(gripper, "grip", pinion=1.0,
                          right=K_MM_PER_DEG, left=K_MM_PER_DEG)
    limits(gripper, "right", effort=DRIVE_FORCE_N, velocity=DRIVE_SPEED_MPS)
    mechanism_state(gripper, "home", grip=OPEN_TRAVEL / K_MM_PER_DEG)
```

几个值得记的坑：

- **`mass()` 是「总重」，不是「零件重」。**
  `mass(palm, 250)` 之后又 `point_mass(plate, 500)`，掌板的总重是 250 而不是 750。
  本例改用 `PALM_TOTAL_G = PALM_PLATE_G + SERVO_G` 显式写死。
- **`point_mass` 只能挂在 part 上，不能挂在 assembly 上**：
  `ValueError: point_mass 'servo': palm is an assembly; put the point mass on the part it is in`。
- **齿轮齿条耦合用 `rack_and_pinion_pair`**，两个齿条给同一个传动比。
- **`mechanism_state` 导出成 MJCF 的 keyframe**，URDF 里装不下（见 §4）。

导出：

```bash
cad run src/gripper_mechanism.py
# parts 5 · bounds 92 × 48 × 56 mm · joints 3
cad model export <id> description/gripper.urdf sim/gripper.xml
```

导出器自己会报告很多信息，这些信息本身就是文档：

```
robot gripper: 3 links (palm, finger_right, finger_left) bolted to the world;
  2 joints: 2 prismatic (right, left); 0.81 kg
  couplings left follows right x1;
  each part collides as its mesh, which MuJoCo collides as its convex hull;
  2 contact excludes (bodies touching at rest);
  keys closed, gripping, home, open
```

**「2 contact excludes (bodies touching at rest)」这一句，是后面最大一个坑的伏笔。**

---

## 3. 导出的 URDF 里有什么

4 KB，4 个 link，3 个关节，2 个可动。关键片段：

```xml
<link name="finger_right">
  <inertial>
    <origin xyz="0.0186101733 -2.06863179e-05 0.00216259031" rpy="0 0 0"/>
    <mass value="0.03"/>
    <inertia ixx="4.6282176e-06" ixy="-1.13941314e-08" ixz="-2.19924192e-07"
             iyy="7.08915022e-06" iyz="-1.34208092e-09" izz="9.69829583e-06"/>
  </inertial>
  <visual   name="finger_right"> … </visual>
  <collision name="finger_right"> … </collision>
</link>

<joint name="right" type="prismatic">
  <origin xyz="0.0178345238 0 0.0025" rpy="0 -1.57079633 -3.14159265"/>
  <axis xyz="0 0 1"/>
  <limit lower="-0.0068345" upper="0.012" effort="140" velocity="0.2"/>
  <parent link="palm"/><child link="finger_right"/>
</joint>

<mimic joint="right" multiplier="1" offset="0"/>
```

注意 `<inertia>` 里**有非零的 ixy / ixz / iyz** —— 导出器写的是完整的惯性张量，
不是只有对角线。MuJoCo 读 URDF 时会把它转成主轴表示，所以两个格式里
`body_inertia` 的**顺序不一样**（详见 §5.7），但物理量一样。

---

## 4. 六个实测发现

### 发现 1：URDF 在 MuJoCo 里丢掉 0.75 kg（占全模型的 93%）

| | 总质量 | `body_mass` |
| --- | --- | --- |
| URDF 声明的 | 0.81 kg | — |
| MuJoCo 加载 URDF 后 | **0.06 kg** | `[0, 0.03, 0.03]` |
| MuJoCo 加载 MJCF 后 | 0.81 kg ✓ | `[0, 0.75, 0.03, 0.03]` |

原因：MuJoCo 的 URDF 加载器强制 `fusestatic=true`。
`FuseStatic` **拒绝**把静态体的质量融进 world（world 是无限质量，融进去会破坏动力学），
于是那部分质量不是「算作静态」，是**直接扔掉**。

而 `cad urdf validate` 报的是：

```
OK description/gripper.urdf: robot 'gripper', root 'base_link', 4 links,
   3 joints (2 movable), 10 resolved mesh references, total mass 0.81 kg
```

**校验器看的是 URDF 文件本身，它看不到 MuJoCo 加载之后发生的事。**

修法只有一个：往 URDF 里塞 MuJoCo 的扩展块。

```xml
<mujoco><compiler fusestatic="false"/></mujoco>
```

实测总质量回到 0.81 kg。**这个块必须放在 `</robot>` 之前。**

> ⚠️ 这条要推广：之前只知道「base link 的质量被丢」，
> 这次发现是**所有固定在 world 上的体**都丢 —— 掌板也是固定体，也丢了。
> 一个整机 URDF 里如果有配重块（配电池、配重、传感器），全都会消失。

### 发现 2：URDF 表达不了「这两件不碰」→ 手指被掌板摩擦卡住

导出器在 MJCF 里自动加了两条排除：

```xml
<contact>
  <exclude body1="palm" body2="finger_right"/>
  <exclude body1="palm" body2="finger_left"/>
</contact>
```

因为手指的安装轨底面（z=0）和掌板顶面（z=0）**共面贴合**，一装上就在接触。

实测静置时的接触数：

| | 接触数 | 接触对 |
| --- | --- | --- |
| MJCF | **0** | （被 exclude 掉了） |
| URDF | **6** | `palm_plate × finger_right` ×3，`palm_plate × finger_left` ×3，间距全为 0 |

URDF 没有排除接触的语法。后果不是「多算一点接触力」，而是**手指动不了**：

给右指关节 0.5 N，走 60 步：

| | 右指移动 | 约束残差 |
| --- | --- | --- |
| MJCF（0 接触） | 13.21 mm | 0.26 mm |
| URDF（6 接触，μ=1） | **0.64 mm** | 0.41 mm |

URDF 版本里，手指底面贴着掌板顶面，摩擦系数默认 μ=1，
0.5 N 的驱动力被摩擦力直接抵消 —— 驱动器推不动手指。

**这是真实机器人最常见的坑之一**，而且在 URDF 里无解：
你只能靠几何挪开（让两者不相贴），或者走 MJCF。

### 发现 3：URDF 模式下 `<mujoco>` 扩展块只认 `<compiler>` 的属性

把各种东西塞进 `<mujoco>` 块实测：

| 塞进去的 | 生效？ |
| --- | --- |
| `<compiler fusestatic="false"/>` | ✅ 质量 0.06 → 0.81 kg |
| `<compiler boundmass="0.5"/>` | ✅ 质量 0.06 → 1.00 kg |
| `<compiler meshdir="meshes"/>` | ✅ 报错信息里路径变了 |
| `<compiler autolimits="false"/>` | ✅ 报错信息点名了它 |
| `<option gravity="0 0 -9.81"/>` | ❌ 静默忽略 |
| `<size njmax="600"/>` | ❌ 静默忽略 |
| `<visual><map znear="0.01"/></visual>` | ❌ 静默忽略 |
| `<contact><exclude …/></contact>` | ❌ **静默忽略** |
| `<equality><joint …/></equality>` | ❌ 静默忽略 |
| `<worldbody><geom …/></worldbody>` | ❌ 静默忽略 |
| `<definitely_not_a_tag/>` | ❌ 静默忽略（连乱写的都不报错） |

结论：**只有 `<compiler>` 的属性会被读。**
想用 `<mujoco><contact><exclude/></contact>` 补上发现 2 的坑 —— 做不到，它会被静默丢掉。

### 发现 4：关节等式是软约束，稳态有 0.26～0.41 mm 残差

URDF 的 `<mimic>` / MJCF 的 `<equality><joint>` 都被 MuJoCo 转成 `mjEQ_JOINT`：

```
eq_type = mjEQ_JOINT (2), obj1=1 (left), obj2=0 (right), polycoef=[0, 1, 0, 0, 0]
solref = [0.02, 1.0], solimp = [0.9, 0.95, 0.001, 0.5, 2.0]
```

`polycoef` 是**常数项在前**的：`poly(x) = 0 + 1·x + 0·x² + 0·x³ + 0·x⁴`。
`obj1` 是**从动**的那个关节 → `left = right`。

但这是软约束，不是刚性连接。稳态时两边差 0.26 mm（MJCF）/ 0.41 mm（URDF）：

```
MJCF: qpos_right = +13.2053 mm, qpos_left = +12.9418 mm, 残差 0.2635 mm
URDF: qpos_right = +0.6418 mm,  qpos_left = +0.2342 mm,  残差 0.4076 mm
```

要更硬就调 `solref[0]`（时间常数，越小越硬；MuJoCo 建模指南建议 0.004～0.01）。

> 顺带：`mjEQ_JOINT` 的枚举值是 **2**，不是 6。
> 网上（包括某些中文博客）流传过 6，那是 `mjtEq` 里的别的项。

### 发现 5：关节限位是软约束，不是夹紧

把 qpos 直接设成超限值，MuJoCo **不报错，也不夹回去**：

```
直接把 qpos 设成 -0.011835 → 右指 X = 6.0000 mm（没被夹回去）
直接把 qpos 设成 +0.017000 → 右指 X = 34.8345 mm（没被夹回去）
```

限位是 `mj_step` 里的一类**单侧软约束**：越界时求解器会给一个减速/阻挡的力，
但位置仍可能略微超出。做行程校核时不能指望 MuJoCo 帮你挡住。

### 发现 6：URDF 的 `<visual>` / `<collision>` 在 MuJoCo 里塌成一个

URDF 里写了 5 个 `<visual>` + 5 个 `<collision>`（每个零件两套几何），
MuJoCo 加载后只有 **5 个 geom** —— 按名字去重，一个零件一个碰撞几何。

MJCF 里是分开的（10 个 geom：视觉组 `contype=0 conaffinity=0`，碰撞组正常）。

**后果**：一份 URDF 在 MuJoCo 里没法给同一个零件不同的视觉和碰撞形状。

### 发现 7：不是 bug —— 两个加载器的主轴约定不同，惯性张量一致

初看像是导出器搞错了：

```
MJCF body_inertia palm = [5.7986e-05, 1.80678e-04, 2.29974e-04]
URDF body_inertia palm = [2.29974e-04, 1.80678e-04, 5.7986e-05]     ← 顺序反了
```

但 `body_iquat` 也跟着不同（MJCF 是单位四元数，URDF 是个 90° 旋转）。
把主轴变换回体坐标系重算张量：

```
palm          ✅ 一致   最大差 = 1.8e-18
finger_right  ✅ 一致   最大差 = 3.9e-15
finger_left   ✅ 一致   最大差 = 3.9e-15
```

**同一具刚体，只是内部表示不同，物理完全一样。** 别去「修」它。

### 发现 8：导出的模型没有执行器（nu = 0）

`cad.build123d` 的 API 里有 `limits()`（给出 effort / velocity），
但没有电机声明。导出结果：

```
nq=2  nu=0  neq=1
```

`jnt_actfrcrange = [[-140, 140], [-140, 140]]` —— 力矩上限带过去了，
但没有 `<motor>` / `<position>` 执行器，模型只能被动地被推。

要驱动，得自己在 MJCF 里加：

```xml
<actuator>
  <motor joint="right" gear="1" ctrlrange="-140 140"/>
  <motor joint="left"  gear="1" ctrlrange="-140 140"/>
</actuator>
```

（左右各一个电机是刻意的：联动靠等式约束，驱动靠两个电机，
这样和真实夹爪一样 —— 一个电机 + 齿条耦合。）

---

## 5. 一个容易搞反的地方：镜像靠的是关节轴，不是联动符号

两个手指的关节在各自的体坐标系里，**局部轴都是 `0 0 1`**，
但世界轴相反：

```
right  局部轴=[0, 0, 1]  世界轴=[ 1, 0, 0]
left   局部轴=[0, 0, 1]  世界轴=[-1, 0, 0]
```

所以联动写成 `left = right`（**同号**）才是对的：

```
右指世界 X = 17.8345 + qpos_right
左指世界 X = -17.8345 − qpos_left      （qpos_left = qpos_right 时）
```

两边对称地朝中线走。如果谁「顺手」把左指的轴也写成世界 +X，
那么同号的联动会让夹爪**一边张一边合** —— 而且不报任何错。

**这就是为什么必须做关节扫描，而不是看一眼就放心。**

---

## 6. 建议的分工

| 用途 | 用哪个 | 为什么 |
| --- | --- | --- |
| MuJoCo 仿真 | **MJCF** | 保留接触排除、关键帧；可以加执行器；质量不会被丢 |
| ROS / ROS 2 | **URDF** | ROS 不关心 fusestatic，也没有接触排除的概念 |
| 两者都要 | 都导，**以 MJCF 为准** | URDF 是 URDF 格式能力范围内的近似 |

如果某条流水线只能用 URDF 喂给 MuJoCo，那么必须做两件事：

1. 加 `<mujoco><compiler fusestatic="false"/></mujoco>`（否则质量丢 93%）
2. 检查有没有「本来贴着、但不该互相算接触」的零件对，
   有的话只能改几何让它们错开 —— URDF 里没法排除

---

## 7. 可复现清单

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/100-Vibe/3D-stp

# 1. 建模 + 导出
cad run src/gripper_mechanism.py
cad model export <id> description/gripper.urdf sim/gripper.xml

# 2. 格式层面的检查（注意：它看不到 MuJoCo 的静默行为）
cad urdf validate description/gripper.urdf
cad mujoco check sim/gripper.xml

# 3. URDF 体检：质量有没有被静默吃掉
MUJOCO_GL=disable python3 checks/urdf_probe.py description/gripper.urdf

# 4. 关节扫描：轴向 / 镜像 / 钳口 / 限位
MUJOCO_GL=disable python3 checks/joint_sweep.py

# 5. 出图（几何对了，形状也得对）
cad urdf snapshot description/gripper.urdf tmp/closed.png \
    --camera front --pose '{"right": -0.0068345}'
```

`checks/urdf_probe.py` 和 `checks/joint_sweep.py` 都可以直接抄进别的项目。

---

## 8. 下一轮要改的

这一轮暴露出来的模型本身的问题（不是格式问题）：

- **手指够不着导轨。** 掌板 48 mm 深，导轨条在 y = ±22，
  而手指（受 Robotiq 2F-85 接口约束）只有 38 mm 长（y = ±19）。
  结果手指根本没搭在导轨上，只是浮在掌板顶面上。
  要么把掌板改窄，要么加长手指安装轨。
- **滑块没有真正的直线导轨。** 掌板只是个简化块，
  导轨条的高度（z 0～6）和手指安装轨（z 0～5）在同一高度，
  真要搭上去必须让导轨在手指轨底面**以下**。
- **行程数值的来源要写清楚。** `CLOSE_TRAVEL = 6.8345` 是从几何反推的
  （让两个 V 槽口正好合拢），`OPEN_TRAVEL = 12` 和
  `DRIVE_FORCE_N = 140` 是**占位符**，得换成真实驱动器的手册值。
- **`home` 关键帧是新加的。** MuJoCo Menagerie 的约定是每个模型带一个 `home` key，
  工具和人都会用它复位。夹爪的 home = 完全张开（复位时不要夹着东西）。

---

## 9. 顺带记录的两个 API 细节

给以后写脚本的人：

- **MuJoCo 的 `m.mesh_vert` 已经是 `(N, 3)` 数组了**，
  `mesh_vertadr` / `mesh_vertnum` 数的是**顶点**，不要再乘 3。
- **MuJoCo 会把网格重定心到质心、并旋转到惯性主轴**，
  所以 `mesh_vert` 在自己的坐标系里**不再轴对齐**。
  想算网格的世界包围盒，要变换**真实顶点**；
  拿局部 AABB 的 8 个角去变换会多算 ~0.9 mm（实测）。
  同一件事的另一个证据：MuJoCo 的 `mesh_pos` / `mesh_quat` 存的就是这个修正。

---

## 相关文档

- [`06-机器人描述与URDF.md`](06-机器人描述与URDF.md) —— 惯性的物理可行性门槛、单位陷阱、`<mimic>` 支持矩阵
- [`03-工作流速查.md`](03-工作流速查.md) —— 日常动作
- [`05-升级到0.11.md`](05-升级到0.11.md) —— 新 API 从哪来
