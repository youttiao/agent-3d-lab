# 案例：Robotiq 2F-85 夹爪 —— V 型槽指尖逆向重建

> 这是本仓库的第一个完整案例，用来证明 **"厂商 STEP → 拆解分析 → 参数化重建 → 验证出图"** 这条流水线在本机跑得通。
> 原始工作区：`~/100-Vibe/3D-stp`（本目录是它的可分享副本，日常改动仍在那边做）。

## 背景

给一台带 Robotiq 2F-85 两指夹爪的机械臂做维护。原厂指尖是硅胶垫
（AGC-TIP-204-085），抓水管之类的圆柱件时容易滑、也磨损得快。
目标是做一个**刚性 V 型槽指尖**，保留原厂安装接口，能直接装回原指轨。

## 做了什么

| 步骤 | 做法 | 产出 |
| --- | --- | --- |
| ① 拿参考件 | 从 Robotiq 官方 CAD 取指尖/body 的 STEP | `imported/`（不入库，见下） |
| ② 量尺寸 | 用 `cadgen read_step` 读包围盒、比对原厂安装孔位 | 安装接口尺寸表 |
| ③ 参数化重建 | build123d 写 `src/robotiq_v_finger.py`，尺寸全部提成常量 | `STEP/robotiq_v_finger.step` |
| ④ 验证 | `cadgen step snapshot` 出多视角 PNG，人眼核对 | `img/` |
| ⑤ 顺带 | 另写一个 Festo 风格的演示两指夹爪 `src/gripper.py` | `STEP/gripper.step` |
| ⑥ 量几何 | 写 `checks/check_v_pair.py` 量管子和手指的关系 | 三个真 bug（见下） |

## ⚠️ 量出来的三个 bug（2026-11-23）

**这一节是本案例最值钱的部分。** 上面那个流程跑通了，尺寸表也对，
但「尺寸对」不等于「形状对」——这三个 bug 是**靠量出来的，不是靠看出来的**：

| # | bug | 怎么发现的 | 后果 |
| --- | --- | --- | --- |
| 1 | V 槽的截面画在 `Plane.XY` 上，但顶点的 z 分量是槽口高度 | `check_v_pair.py` 量出管子与手指的最小距离 **1.3345 mm**（应为 0） | 槽沿 Z 挤而不是沿 Y，管子根本没卡进槽里 |
| 2 | 右指的 V 开口朝 +X，**背离**夹爪中线 | 同上（量 apex 到管心的距离） | 右手的槽和左手的槽对着开，中间的空腔是「V 对 V」而不是「V 对圆」 |
| 3 | 文档里写的 5 mm 安装轨**根本没建**，M3 孔是盲孔 | 数包围盒高度 | 装不上 |

修完之后：

```
管子 vs 右指 rf: 公共体积 = 0.0 mm^3   最小距离 = 0.0000 mm   ✅ 不穿模
管子 vs 左指 lf: 公共体积 = 0.0 mm^3   最小距离 = 0.0000 mm   ✅ 不穿模
apex 到管心的距离 = 23.3345（应为 R/sin(半角) = 23.3345）  ✅
```

**教训**：写完 CAD 立刻写一个「量」的脚本，别等肉眼发现。
本仓库现在有两个通用体检脚本：`checks/urdf_probe.py`（URDF）和
`checks/joint_sweep.py`（关节）。

## 关键设计

**接口完全复用原厂**，这是能不能装回去的前提：

| 参数 | 值 | 说明 |
| --- | --- | --- |
| 安装面 | 22 × 38 × 5 mm | 与 AGC-TIP-204-085 足迹一致 |
| M3 过孔 | ⌀3.2，X 向间距 16 mm | 直接用原厂螺钉 |
| 定位销 | ⌀3.0，Y 向偏移 −14 mm | 防呆，靠身体侧 |

**V 型槽按被夹物反推**，不是拍脑袋：

```python
PIPE_OD   = 33.0                    # DN25 水管外径
V_DEPTH   = PIPE_R                  # = 16.5，保证 33 mm 外径能卡进去
V_ANGLE   = 90.0                    # 全夹角
V_WIDTH_AT_FACE = 2 * V_DEPTH * tan(V_ANGLE/2)   # 槽口宽度由深度和角度算出
V_BLOCK_THICK   = V_DEPTH + 8.0     # 槽背后至少留 8 mm 壁，不然没材料
```

**坐标系**（单指）：`+X` 指向夹爪中线，`+Y` 沿指轨，`+Z` 出安装面。
左手的手指沿 YZ 面镜像，V 槽开口朝 −X。

## 怎么看

```bash
cd examples/robotiq-v-finger

# 重建 STEP（顺带打印 id 和浏览器 view 链接）
cad run src/robotiq_v_finger.py

# 出图（OCCT 无头渲染，1～2 秒，不用浏览器）
cad step snapshot STEP/robotiq_v_finger.step tmp/finger.png
cad step snapshot STEP/robotiq_v_finger.step tmp/top.png --camera top

# 起本地查看器，浏览器里转着看
cad run src/robotiq_v_finger.py     # 抄它打印的 view 链接
```

已生成的渲染图在 `img/`：

| 图 | 看什么 |
| --- | --- |
| `v_finger_iso.png` | 整体等轴视角 |
| `v_finger_front.png` | 正面 —— **两个 V 槽相对，DN25 管子正好卡在中间**（修好之后的样子） |
| `v_finger_side.png` | 侧视（看 38 mm 指轨长度和 V 深度） |
| `v_finger_top.png` | 俯视（看 M3 孔与定位销布局） |
| `single_iso.png` / `single_top.png` | 单指 + 管道的断面关系 |
| `gripper_*.png` | 另一套演示夹爪的四视图 |

> ⚠️ `cad step snapshot --camera` 的预设只有
> `back / bottom / front / iso / left / right / top` —— **没有 `side`**。
> 侧视要用 `--camera right`（从 +X 看）。

## 迁移记录（0.6.5 → 0.11.16）

本案例 2026-11-23 从 text-to-cad 0.6.5 迁到 0.11.16。改动只有三处 API：

```python
# 旧                                    # 新
from cadgen import build123d as bd   →   import build123d as bd
from cadgen import step              →   from cad import step
@step(out="../STEP/x.step")          →   @step("../STEP/x.step")
```

读文件同理：`read_scene(p)` / `read_step(p)` → `step.read(p)` + `cad.build123d.leaves(tree)`。

**几何零差异**——`checks/compare_steps.py` 逐个比对三个模型，
零件数、包围盒、标签集合全同，尺寸差 **0.000000 mm**。

## 厂商件为什么不在库里

`imported/robotiq_2f85_*.step` 是 Robotiq 官方 CAD（件号 `C-083-PAD_SURMOULE_85_defeature`）。
**再分发条款不明**，所以仓库里只留**我们自己写的源码和产出**，
厂商原件请自行从 Robotiq 官网下载后放到 `imported/`。

`checks/inspect_robotiq.py` 就是用来读这两个厂商件的：

```bash
cd examples/robotiq-v-finger
cad run checks/inspect_robotiq.py
```

实测输出（2026-11-23）：

```
=== robotiq_2f85_body.step (size=20,640,977 bytes) ===
  leaves: 11
    [ 0] NAUO1    size=( 84.89 × 93.40 × 75.00)
    ...
    [ 5] NAUO6    size=( 19.16 × 38.00 × 22.00)   ← 硅胶指尖
    [10] NAUO11   size=( 19.16 × 38.00 × 22.00)   ← 硅胶指尖
  overall bbox: 152.48 × 152.74 × 75.00 mm

=== robotiq_2f85_fingertip.step (size=175,396 bytes) ===
  leaves: 1
    [ 0] C-083-PAD_SURMOULE_85_defeature  size=( 22.00 × 38.00 × 19.16)
```

**交叉印证**：厂商 body 上的两片硅胶指尖是 38.00 mm 长，
独立指尖件也是 38.00 mm 长、22.00 mm 宽——
和当初逆向重建时定的 `MOUNT_L = 38.0` / `MOUNT_W = 22.0` 完全对上。

## 这个案例想说明什么

1. **参数化重建比抄 STEP 更有用** —— 拿到的是能改的 Python，不是死几何。
   换管径改一个 `PIPE_OD` 就行。
2. **分析厂商件是有套路的** —— `read_step` 拿场景树和包围盒，
   比在 GUI 里转着看快得多。
3. **出图是必须的验证环节** —— 尺寸对不代表形状对，
   每次改完必须 `snapshot` 出一张图看。
4. **尺寸全部提成常量** —— 别人接手时不用读几何代码就能改。
5. **更要紧的是「量」** —— 尺寸表对了、图看着也不一定对。
   三个 bug 全是靠 `check_v_pair.py` 量出来的。

## 已知不足 / 下一步

- V 槽没有做沟底圆角和排屑设计
- 没出 STL / 3MF，也没做可打印性检查（`dfam-check` skill 能做）
- 双指装配体的干涉检查和 URDF 导出在
  [`gripper-mechanism`](../gripper-mechanism/) 案例里做了 ——
  这个案例只做单指
