# CAD 项目脚手架

复制这个目录当作新项目的起点：

```bash
cp -R templates/cad-project projects/my-part
cd projects/my-part
```

目录约定遵循 `cad` skill 的 [project-layout](../docs/03-工作流速查.md)：

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
from cadgen import build123d as bd
from cadgen import step

WIDTH = 60.0
DEPTH = 40.0
THICKNESS = 4.0


@step(out="../STEP/plate.step")
def plate():
    body = bd.Box(WIDTH, DEPTH, THICKNESS)
    body.label = "plate"
    return body


if __name__ == "__main__":
    plate()
```

## 三条命令跑通一轮

```bash
python src/plate.py                                    # 生成 STEP
cadgen step snapshot STEP/plate.step tmp/plate.png     # 出图看
cadgen viewer --host 127.0.0.1 --json                  # 起本地查看器
```

> **踩坑预警**：`build123d` 的 `Box` 默认 `align=CENTER`（几何中心在原点），
> 不是 `MIN`。想让底面贴在 Z=0，写 `align=(Align.CENTER, Align.CENTER, Align.MIN)`。
> 这是 `cad` skill 里专门写出来的一条，说明它坑过不少人。

## 命名约定

- 单位一律毫米（mm），坐标系 XY 平面 + Z 向上
- 源文件名与输出文件同名：`src/plate.py` → `STEP/plate.step`
- 装饰器 `out=` 路径**相对脚本本身**，不是相对 cwd
- 一个 `.py` 一个模型入口；公共几何写成普通工厂函数，不要塞进装饰函数
