# 我们自己的工具链会怎么坑你（build123d / OCCT 8）

> 这份文档收集的是 **build123d 和 CadQuery 的 issue tracker 上实测出来的失败模式**，
> 以及一条被独立测量过的、能把静默失败率压掉 4 倍的工作方法。
>
> 调研时间：2026-11-23。仓库状态：build123d `gumyr/build123d` ★3,822（226 个 open issue）、
> CadQuery `CadQuery/cadquery` ★6,153（487 个 open issue）。
>
> 为什么单开一篇：这些不是「AI 不行」，是**几何内核会静默地给你错的东西**。
> 我们自己的 V 型槽案例就中了三发（见 §5）。

---

## 1. 一句话：贵的失败不是崩溃，是「看着挺对」

独立论文 **"Done Is Not Correct"**（arXiv **2611.10063**，2026-11），
**就是在 build123d / OpenCASCADE 上做的** —— 和我们同一套栈：

> single-shot agents claimed completion on **98% of attempts and were silently wrong on 14.1%**
> (task-cluster CI [5.8, 24.4]); a tool-use loop that enforces **measure-then-claim**
> cut silent failures to **3.2%** (McNemar p < 10⁻⁴)
> and raised **claim precision from 64% to 96%**.

论文里那句最该被抄下来的话：

> Crashes are cheap to catch: a spec that fails to execute announces itself.
> **The expensive failure is a part that builds and renders plausibly while its
> bolt circle sits on the wrong pitch diameter, delivered with 'done, confidence 0.97.'**

他们把 151 次失败拆开看：

> **95 次压根没产出有效实体**；**56 次产出了有效几何但没通过语义检查**。
> 后者里的主要特征是**内部特征缺失或尺寸错**（沉头孔的深度或面、孔的延伸范围、台阶截面）；
> **整体包络尺寸错**也很常见。

而且他们自己承认判官偏松：
> Hardening our own oracle flipped 18 of 519 regraded verdicts from pass to fail and none in reverse.

> 🔑 **最要紧的一句**：降到 4–5% 靠的是**声明契约**，不是更强的模型 ——
> "the reduction to 4–5% comes from the claim contract, not from capability."

**这句话直接定义了我们这个仓库的形状**：我们不是在写「更聪明的 CAD agent」，
我们是在写**声明契约**——「先量，再说做完了」。

---

## 2. 「它跑了但它是错的」—— build123d 的实测失败模式

### 2.1 布尔运算会**静默地不挖孔**

| issue | 原文要点 |
| --- | --- |
| **build123d #1363** | "Boolean subtraction fails for specific hole orientations and positions… Instead of creating a hole, the preview only displays the intersection edge where the cut should occur. **The exported model (either step or stl) matches the preview and also contains no hole.**" |
| **build123d #1568** | "the subtract seems to have **silently failed** and has a missing face too." |
| **build123d #1428** | `clean()` 在布尔运算后会删掉被曲面参数缝穿过的面，导致体积算错（`sphere - box` 给出 73.3038，期望 87.9646） |

**#1363 是最阴的**：预览和导出的 STEP **一致** —— 也就是说
**你看渲染图也发现不了这个孔不存在**，因为渲染的就是那个没孔的模型。

→ 唯一的防线是**量**：公共体积、最小距离、面的数量。

### 2.2 圆角 / 倒角

| issue | 原文要点 |
| --- | --- |
| **build123d #1506** | 失败信息只说 "try a smaller value"，**不告诉你是哪条边有问题**。"对于选了一打边的场景，用户只能手工二分排查，**这是最常见的卡点**" |
| **CadQuery #2114** | 圆角/倒角构建失败时 `Shape()` 会**在 OCCT 内部 segfault**，而不是抛 `StdFail_NotDone` —— **失败会把整个进程带走** |
| **build123d #1462** | 外向 `offset()` 返回的实体法向反转，圆角处理不了；倒角同样受影响 |
| **build123d #1296** | 二维圆角失败表现为 `ValueError: Face can only be created with closed wires`（信息完全对不上原因） |

### 2.3 选边 —— LLM 真正会崩的地方

| issue | 原文要点 |
| --- | --- |
| **CadQuery #2129** | 倒角跟在圆角后面，命中了**所有底边**，不是要的那几条 |
| **CadQuery #2039** | 链式 `.edges(...).fillet()` 选中了"额外多出来的一条边"。作者原话：*"I apparently don't understand how the selectors work."* —— 这条 issue 本身就是 LLM 写的 |
| **CadQuery #1959** | 用 `#Z` 选择器时圆角失败，但**全选所有边**时成功 |
| **build123d #1533** | `Extrude in wrong direction`（挤出方向反了） |
| **build123d #1453** | `Pos(5,0,0) * plate` 之后 `faces(Select.NEW)` 返回**全部 7 个面**而不是 `[]` —— 位置敏感的 `IsSame` 语义让选择失效 |
| **build123d #1452** | Algebra 模式下 `Select.LAST` 报错："Select.LAST needs a record of how this shape was made, and this one has none." |

### 2.4 ⚠️ 同一个脚本，不同进程，**几何不一样**

**build123d PR #1505**：

> When adjoining edge endpoints differ by a tiny amount (for example, x=0 versus x=1e-20),
> **OCCT's list overload can choose a merged vertex based on memory address.
> The same script can therefore produce different geometry across processes.**

（还有 **build123d #119**：「从一个非平面面构造 Plane 应该失败……结果平面有点**非确定性**」。）

→ **推论**：CI 里跑出来的 STEP 和本地不一样，不一定是你的 bug。
→ **对策**：把 STEP 一起入库（我们就是这么做的），别只入库源码。

### 2.5 单位

| issue | 原文要点 |
| --- | --- |
| **build123d #874** | "Most 3d scans and software like Blender use **meters as the base unit while B3D uses mm. This causes most models to be imported way too small.**" |
| **build123d #1575** | 英制 `Draft` 配 `NumberDisplay.FRACTION`，`0.001"` 渲染成 `0/1"`。任何写 `18 * IN` 然后出图的 LLM 都会拿到垃圾标注 |

→ 单位陷阱的**另一半**在 [`06-机器人描述与URDF.md`](06-机器人描述与URDF.md)（URDF/glTF 用米、
COLLADA 按文件、USD 默认厘米）；build123d 本身是**毫米**。

### 2.6 工作平面选错（**我们踩过**）

BenchCAD §5.2 的实测：

> the generated code extrudes from the XY plane rather than the target XZ plane.
> **This error is common for geometries generated based on XZ and YZ workplanes.**

我们的 V 型槽案例**正是这一条**：`bd.BuildSketch(bd.Plane.XY)` 本该是 `bd.Plane.XZ`，
结果是 V 槽沿 Z 挤而不是沿 Y（见 §5）。

### 2.7 一条 AI 写的 issue 被人类合并了

**build123d #1425**：
> "Authored by AI (Claude - Opus 5 w. ultracode), approved by me - a human :)"

（发现了一个真实的 OCCT 契约 bug —— 少了 `IsDone()` 检查 —— 人类合并了它和它的修复 PR。
两个 tracker 里**唯一**一条 AI 署名的 issue。）

---

## 3. 「出图看」到底够不够？—— 两家在公开吵架

这是本次调研里最有意思的一段。两大明星创业公司**公开对立**，而且**没有受控对比**。

**Adam**（adam.new/blog/bitter-lesson-ai-cad，Zach Dive，2026-05-24）：

> **"Two tools. Code generation and view screenshot. That's all you need to make AI CAD work,
> because the models can see now."**
>
> "We built thousands of lines of abstractions wrapped around getting the models to spatially reason.
> A whole DSL we'd written so the model could get all the 3D information in a text-based format.
> **So we threw it out.**"
>
> "**Every abstraction we wrote was something the model had to fight around.
> Every helper was a failure mode we owned forever.**"
>
> "**The harder you work to build a CAD harness (or any specific harness),
> the more brittle your product is when the next model release lands.**"

**BuildCAD**（buildcad.ai/guides/cad-mcp-servers，2026-10-16）说正相反：

> **"A language model cannot see the geometry it makes.**
> Servers that send back pictures, measurements and validity checks let it catch a hole in the wrong place
> or a wall that came out 0.4 mm thick; **without them, you are the one checking.**"

### 那到底该信谁？—— 用消融实验说话

CADFather 的消融（**直接测了**）：

> removing deterministic proposals costs the most: it lowers the mean score by 0.012–0.110 …
> and raises IR from zero to 0.007–0.124, whereas **removing the optimizer lowers the mean score by only 0.004–0.006**.

CADMAGEDDON 从另一头得出同一个结论：

> **"The instruments, not model scale, carry much of the accuracy."**

→ **几何拟合工具扛精度，模型扛结构。**

→ **对我们：出图（看形状）必须有，但不够。**
**必须再有一套「量」的脚本把数字拿出来。**
出图回答「形状对不对」，量回答「数对不对」。

> ⚠️ 还有一个反面证据，说明**出图代替不了尺寸**：
> BenchCAD 说，
> "replacing the textual edit instruction with a target render **collapses every model to near-zero,
> since a render specifies geometry but not numbers**."
>
> 也就是说：**光给渲染图，模型连改都不会改了。**

---

## 4. 「先量，再说做完了」—— 这就是我们的声明契约

论文给的数字：把「完成声明」变成「先量再声明」，静默失败率 **14.1% → 3.2%**，
声明精度 **64% → 96%**。

我们这个仓库里对应的三样东西：

| 脚本 | 量什么 | 对应论文里的失败类型 |
| --- | --- | --- |
| `checks/check_v_pair.py` | 管子和手指的公共体积 + 最小距离 + V 槽朝向 | 「内部特征缺失或尺寸错」（build123d #1363 的静默不挖孔就在这一类） |
| `checks/urdf_probe.py` | 质量有没有被静默吃掉、`<mimic>` 有没有生效 | 「校验器过了但引擎加载后不对」 |
| `checks/joint_sweep.py` | 关节世界轴向、镜像、钳口开度、联动残差、限位行为 | 「形状对但轴反了 / 符号反了」 |

以及通用的一条：

> **「它跑了」不等于「它对」。**
> 崩溃会自己说话；**贵的那种失败会一边笑一边给你错答案。**

所以这个仓库的规矩是：

1. 改完 CAD → **出图给人看**（形状）
2. 改完 CAD → **跑量脚本**（数字）
3. 两样都过了 → 才写「做完了」

---

## 5. 我们自己中招的记录（2026-11-23）

V 型槽指尖案例，**三个 bug，全是「不报错」的那种**：

| # | 现象 | 怎么发现的 | 对应上面哪一类 |
| --- | --- | --- | --- |
| 1 | V 槽截面画在 `Plane.XY`（该是 `XZ`），槽沿 Z 挤不沿 Y | 量出管子与手指的最小距离 **1.3345 mm**（应为 0） | §2.6 工作平面选错 |
| 2 | 右指的 V 开口朝 +X，**背离**夹爪中线 | 量 apex 到管心的距离 | §2.7 选边/方向 |
| 3 | 文档里写的 5 mm 安装轨**根本没建**，M3 孔是盲孔 | 数包围盒高度 | §2.1 特征缺失 |

修完后：

```
管子 vs 右指 rf: 公共体积 = 0.0 mm^3   最小距离 = 0.0000 mm   ✅ 不穿模
管子 vs 左指 lf: 公共体积 = 0.0 mm^3   最小距离 = 0.0000 mm   ✅ 不穿模
apex 到管心的距离 = 23.3345（应为 R/sin(半角) = 23.3345）  ✅
```

**注意第 1 条和第 3 条：渲染图都看不出来。**
图看着「就是个带槽的方块」，是量出来它跟管子差了 1.33 mm。

---

## 6. 一份实操清单（贴在墙上）

写完 build123d 之后，**按顺序**跑：

| # | 检查 | 抓什么 | 本仓库对应 |
| --- | --- | --- | --- |
| 1 | `cad run` 打印的 `bounds` 对不对 | 整体尺寸写错 | — |
| 2 | **量一个关键关系**（公差、间隙、贴合） | 特征尺寸错 / 缺失 | `check_v_pair.py` |
| 3 | **布尔运算后量体积** | `#1363` 静默不挖孔、`#1428` clean 删面 | — |
| 4 | 导出 STEP 后**重新读回来量** | 导出环节的问题 | `checks/compare_steps.py` |
| 5 | 出图，人眼看 | 形状、方向、朝向 | `cad step snapshot` |
| 6 | 装配/运动后**再量一次** | 轴向、符号、限位 | `checks/joint_sweep.py` |
| 7 | 交给目标引擎**真的加载一遍** | 校验器和引擎说的不是一回事 | `checks/urdf_probe.py` |

第 4 步特别值得强调：**STEP 要入库**。
§2.4 那条 OCCT 的内存地址不确定性，意味着同一份源码在不同进程里可能产出不同的几何 ——
入库 STEP 才是可复现的事实。

---

## 7. 相关文档

- [`07-CAD到URDF到MuJoCo.md`](07-CAD到URDF到MuJoCo.md) —— 一次端到端实测，6 个静默行为
- [`08-AI生成3D的现状.md`](08-AI生成3D的现状.md) —— 业界到哪一步了
- [`03-工作流速查.md`](03-工作流速查.md) —— 日常动作和检查清单

## 链接

- [gumyr/build123d](https://github.com/gumyr/build123d) ★3,822 ·
  [CadQuery/cadquery](https://github.com/CadQuery/cadquery) ★6,153
- [Done Is Not Correct（arXiv 2611.10063）](https://arxiv.org/abs/2611.10063)
- [BenchCAD（arXiv 2605.10865）](https://arxiv.org/abs/2605.10865)
- [CADFather（arXiv 2610.09127）](https://arxiv.org/abs/2610.09127)
- [CADMAGEDDON（arXiv 2611.22563）](https://arxiv.org/abs/2611.22563)
- [Adam: The Bitter Lesson of AI CAD](https://adam.new/blog/bitter-lesson-ai-cad) ·
  [BuildCAD CAD MCP servers 指南](https://buildcad.ai/guides/cad-mcp-servers)
