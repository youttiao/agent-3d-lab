# CAD 项目脚手架

复制这个目录当作新项目的起点：

```bash
cp -R templates/cad-project projects/my-part
cd projects/my-part
```

目录约定遵循 `cad` skill 的 [project-layout](../../docs/03-工作流速查.md)：

```
<project>/
  src/            # 一个模型一个入口文件，文件名 = 输出文件名主干
  STEP/           # STEP 输出 + imported/（外部原始件）
  STL/ GLB/ DXF/  # 其他格式
  checks/         # 可复用的校验脚本
  tmp/            # 探索性脚本与快照（不入库）
```

## 第一个模型长什么样

`src/plate.py`：

```python
from __future__ import annotations

import build123d as bd
from cad import step

WIDTH = 60.0


@step("../STEP/plate.step")
def plate():
    body = bd.Box(WIDTH, 40, 4)
    body.label = "plate"
    return body


if __name__ == "__main__":
    plate()
```

## 三条命令跑通一轮

```bash
cad run src/plate.py                                # 生成 STEP（随 run 写出）
cad model snapshot <id> tmp/plate.png               # 出图（OCCT 无头渲染，1～2 秒）
cad run src/plate.py                                # 打印文档 id 与浏览器 view 链接
```

> `cad run` 会打印一行 `id: <uuid>` 和一行 `view: http://127.0.0.1:3245/<id>?token=…`，
> **浏览器打开那个 view 链接**就能交互查看（转、剖、爆炸）。
> 纯看图不用开浏览器：`cad step snapshot STEP/plate.step tmp/plate.png`。

## 命名约定

- 单位一律毫米（mm），坐标系 XY 平面 + Z 向上
- 源文件名与输出文件同名：`src/plate.py` → `STEP/plate.step`
- `@step("../STEP/x.step")` 里的路径**相对脚本本身**，不是相对 cwd
- 一个 `.py` 一个模型入口；公共几何写成普通工厂函数
- **内核对象只在函数体里读**：`bd.Align.CENTER` 写在模块层会让脚本自己的进程
  也加载内核，每次 run 多花 2～3 秒

## 坑位速记

| 坑 | 说明 |
| --- | --- |
| `Box` 默认 `align=CENTER` | 几何中心在原点，不是 `MIN`。底面贴 Z=0 要显式写 |
| `out=` 没了 | 0.8 起 `@step(out=…)` 改成 `@step(…)` 位置参数 |
| `read_scene` 没了 | 0.8 起用 `step.read(path)` + `cad.build123d.leaves(tree)` |
| `from cadgen import build123d` 会炸 | 0.8 起 `build123d` 这个名字从 `cadgen` 里拿掉了，改成 `import build123d as bd` |
