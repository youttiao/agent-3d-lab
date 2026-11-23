#!/usr/bin/env bash
# 环境自检 —— 回答"用 Agent 做 3D 还缺什么"
# 用法: bash scripts/doctor.sh
# 退出码: 0 = 核心链路齐备; 1 = 核心链路缺件

set -uo pipefail
MISS=0; OPT_MISS=0
C_OK=$'\033[32m'; C_MISS=$'\033[31m'; C_OPT=$'\033[33m'; C_OFF=$'\033[0m'

# 中日韩字符按 2 个显示宽度算，保证列对齐
dwidth() {
  printf '%s' "$1" | LC_ALL=C.UTF-8 awk '{
    n=0; for(i=1;i<=length($0);i++){ c=substr($0,i,1); n += (c ~ /[一-龥]/) ? 2 : 1 } print n }'
}
# 把名字补齐到 36 显示宽度
pad() {
  local w; w=$(dwidth "$1")
  printf '%s%*s' "$1" $((36-w)) ''
}

chk() {  # chk <名字> <探测命令> <说明>
  local name="$1" cmd="$2" hint="$3"
  if eval "$cmd" >/dev/null 2>&1; then
    printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "$name")" "$hint"
  else
    printf "  %s✗%s %s %s\n" "$C_MISS" "$C_OFF" "$(pad "$name")" "$hint"
    MISS=$((MISS+1))
  fi
}

opt_chk() {  # opt_chk <名字> <探测命令> <说明>
  local name="$1" cmd="$2" hint="$3"
  if eval "$cmd" >/dev/null 2>&1; then
    printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "$name")" "$hint"
  else
    printf "  %s○%s %s %s（可选）\n" "$C_OPT" "$C_OFF" "$(pad "$name")" "$hint"
    OPT_MISS=$((OPT_MISS+1))
  fi
}

echo
echo "══════════════════════════════════════════════════════════════════"
echo " Agent × 3D 环境自检"
echo "══════════════════════════════════════════════════════════════════"

echo
echo "▎核心链路（缺了就没法开工）"
chk "python3"            "command -v python3"                          "Python 解释器"
chk "cad / cadgen"       "command -v cad || command -v cadgen"        "CAD 内核封装：STEP/URDF/MJCF/出图"
chk "build123d"          "python3 -c 'import build123d'"                "参数化建模"
chk "OCP (OpenCascade)"  "python3 -c 'import OCP'"                     "几何内核绑定"
chk "playwright"         "python3 -c 'import playwright'"               "viewer 出图后端"
chk "chromium（渲染）"    "ls ~/Library/Caches/ms-playwright"           "无头浏览器，截图/出图依赖它"
chk "git"                "command -v git"                              "版本管理"
chk "gh"                 "command -v gh"                               "GitHub CLI（建仓/协作）"

echo
echo "▎核心链路版本"
if python3 -c 'import build123d' >/dev/null 2>&1; then
  python3 - <<'PY'
import importlib.metadata as m
for p in ("cad", "cadgen", "build123d", "ocpsvg", "ezdxf", "numpy", "playwright"):
    try:
        print(f"    · {p:14} {m.version(p)}")
    except Exception:
        print(f"    · {p:14} (未安装)")
PY
fi

# 版本漂移检查：skill 文档固定了 cadgen 版本，对不上时 skill 里的示例会和实际 CLI 打架
if command -v cadgen >/dev/null 2>&1 || command -v cad >/dev/null 2>&1; then
  DRIFT=""
  for d in "$HOME"/100-Vibe/*/.claude/skills/*/; do
    [ -f "$d/requirements.txt" ] || continue
    pin=$(grep -oE 'cadgen?(\[[a-z0-9,]+\])?==[0-9.]+' "$d/requirements.txt" 2>/dev/null | head -1 | grep -oE '[0-9.]+$')
    [ -n "$pin" ] || continue
    have=$(python3 -c "
import importlib.metadata as m
for p in ('cad','cadgen'):
    try:
        print(m.version(p)); break
    except Exception: pass
" 2>/dev/null)
    [ -n "$have" ] || continue
    if [ "$pin" != "$have" ]; then
      DRIFT="skill 固定 cadgen==${pin}，本机装的是 ${have} —— 文档与实际 CLI 已经对不上（见 docs/05-升级到0.11.md）"
      break
    fi
  done
  if [ -n "$DRIFT" ]; then
    printf "  %s!%s %s\n" "$C_OPT" "$C_OFF" "$DRIFT"
  fi
fi

echo
echo "▎扩展工具链（按用途选装，不装也能开工）"
opt_chk "uv / uvx"         "command -v uv"                              "跑 MCP server（Blender/FreeCAD…）"
opt_chk "node / npx"       "command -v node"                            "npx skills add 装 skill"
opt_chk "blender"          "command -v blender || ls -d /Applications/Blender.app 2>/dev/null" "有机体建模/场景；官方+社区 MCP"
opt_chk "freecad"          "command -v freecad || command -v FreeCADCmd"                       "GUI 参数化 CAD + 机器人装配"
opt_chk "openscad"         "command -v openscad"                        "纯代码建模（轻量）"
opt_chk "切片器 orca"       "command -v orca-slicer"                     "gcode skill 真正出片用"
opt_chk "切片器 prusa"      "command -v prusa-slicer"                    "同上，二选一"
opt_chk "mujoco"           "python3 -c 'import mujoco'"                 "URDF→仿真，验证关节限位与碰撞"
opt_chk "trimesh"          "python3 -c 'import trimesh'"                "网格分析/修整/凸包"
opt_chk "yourdfpy"         "python3 -c 'import yourdfpy'"               "URDF 解析与遍历"
opt_chk "pyvista / vtk"    "python3 -c 'import pyvista'"                "网格可视化"

echo
echo "══════════════════════════════════════════════════════════════════"
if [ "$MISS" -eq 0 ]; then
  printf " 核心链路 %s齐备%s —— 可选缺 %d 项，不阻塞\n" "$C_OK" "$C_OFF" "$OPT_MISS"
  echo "══════════════════════════════════════════════════════════════════"
  echo
  echo "下一步（以一个零件为例）："
  echo "  1. 建模   python src/<model>.py"
  echo "  2. 出图   cadgen step snapshot STEP/x.step tmp/x.png"
  echo "  3. 看图   cd <项目根> && cadgen viewer --host 127.0.0.1 --json"
  exit 0
else
  printf " 核心链路缺 %s%d%s 项 —— 先补齐\n" "$C_MISS" "$MISS" "$C_OFF"
  echo "══════════════════════════════════════════════════════════════════"
  echo
  echo "补齐命令见 docs/02-本机工具链.md"
  exit 1
fi
