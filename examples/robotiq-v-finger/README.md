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
python src/robotiq_v_finger.py          # 重新生成 STEP
cadgen step snapshot STEP/robotiq_v_finger.step tmp/finger.png
cadgen viewer --host 127.0.0.1 --json   # 起本地查看器（从项目根起）
```

已生成的渲染图在 `img/`：

| 图 | 看什么 |
| --- | --- |
| `v_finger_iso.png` | 整体等轴视角 |
| `v_finger_front.png` | 正面（看 V 槽开口宽度） |
| `v_finger_side.png` | 侧视（看 38 mm 指轨长度和 V 深度） |
| `v_finger_top.png` | 俯视（看 M3 孔与定位销布局） |
| `gripper_*.png` | 另一套演示夹爪的四视图 |

## 厂商件为什么不在库里

`imported/robotiq_2f85_*.step` 是 Robotiq 官方 CAD（件号 `C-083-PAD_SURMOULE_85_defeature`）。
**再分发条款不明**，所以仓库里只留**我们自己写的源码和产出**，
厂商原件请自行从 Robotiq 官网下载后放到 `imported/`。

`checks/inspect_robotiq.py` 就是用来读这两个厂商件的：
它会打印场景结构、每个 shape 的包围盒，方便核对我们的重建件和原件对不对得上。

```bash
cd examples/robotiq-v-finger
python checks/inspect_robotiq.py
```

## 这个案例想说明什么

1. **参数化重建比抄 STEP 更有用** —— 拿到的是能改的 Python，不是死几何。
   换管径改一个 `PIPE_OD` 就行。
2. **分析厂商件是有套路的** —— `read_step` 拿场景树和包围盒，
   比在 GUI 里转着看快得多。
3. **出图是必须的验证环节** —— 尺寸对不代表形状对，
   每次改完必须 `snapshot` 出一张图看。
4. **尺寸全部提成常量** —— 别人接手时不用读几何代码就能改。

## 已知不足 / 下一步

- 目前只做了单指，没做双指装配体的干涉检查（`src/gripper.py` 是独立的演示件）
- V 槽没有做沟底圆角和排屑设计
- 没出 STL / 3MF，也没做可打印性检查（`dfam-check` skill 能做）
- 没写 URDF —— 这正是下一块拼图：夹爪作为机械臂末端要进 URDF
