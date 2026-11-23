# 模型目录（Model catalog）

这个文件列出项目里每个模型的**用途、输入、输出**，让 Agent（和新人）不看代码就知道该跑什么。

| 模型 | 源文件 | 输出 | 说明 |
| --- | --- | --- | --- |
| plate | `src/plate.py` | `STEP/plate.step` | 示例件，改成你自己的零件 |

## 约定

- 源文件名与输出文件名同名主干：`src/plate.py` → `STEP/plate.step`
- 嵌套目录镜像：`src/chassis/frame.py` → `STEP/chassis/frame.step`
- 同一模型的不同网格密度放变体子目录：`STL/draft/plate.stl`、`STL/print/plate.stl`
- 厂商原始件放 `imported/`，并用 `read_step` 包装成模型（不要直接改厂商件）

## 跑一遍

```bash
python src/plate.py                                    # 生成 STEP
cadgen step snapshot STEP/plate.step tmp/plate.png     # 出图
```
