"""示例零件 —— 复制这个文件当起点，改尺寸、改名字。

约定（来自 cad skill 的 model-contract）：
  * 单位 mm，坐标系 XY 平面 + Z 向上
  * 一个文件一个模型入口，函数名 = 模型名
  * 关键尺寸提成模块级常量，方便别人改
  * 内核对象（bd.Align 等）只在函数体里读，不在模块层
"""

from __future__ import annotations

import build123d as bd
from cad import step

# === 尺寸 (mm) ===
WIDTH = 60.0
DEPTH = 40.0
THICKNESS = 4.0


def _box_align():
    """build123d 的 Box 默认几何居中（align=CENTER），想让底面贴 Z=0 必须显式写。

    放在函数里而不是模块层：模块层读 bd.Align 会让脚本自己的进程也加载内核，
    每次 run 多花 2～3 秒。
    """
    return (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)


@step("../STEP/plate.step")
def plate():
    body = bd.Box(WIDTH, DEPTH, THICKNESS, align=_box_align())
    body.label = "plate"
    return body


if __name__ == "__main__":
    plate()
