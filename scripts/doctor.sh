#!/usr/bin/env bash
# 环境自检 —— 回答"用 Agent 做 3D 还缺什么"
# 用法: bash scripts/doctor.sh
# 退出码: 0 = 核心链路齐备; 1 = 核心链路缺件
#
# 适配 text-to-cad 0.11.x（命令是 `cad`，不是旧的 `cadgen`）

set -uo pipefail
MISS=0; OPT_MISS=0
C_OK=$'\033[32m'; C_MISS=$'\033[31m'; C_OPT=$'\033[33m'; C_OFF=$'\033[0m'

# 中日韩字符按 2 个显示宽度算，保证列对齐
dwidth() {
  printf '%s' "$1" | LC_ALL=C.UTF-8 awk '{
    n=0; for(i=1;i<=length($0);i++){ c=substr($0,i,1); n += (c ~ /[一-龥]/) ? 2 : 1 } print n }'
}
pad() { local w; w=$(dwidth "$1"); printf '%s%*s' "$1" $((36-w)) ''; }

chk() {
  local name="$1" cmd="$2" hint="$3"
  if eval "$cmd" >/dev/null 2>&1; then
    printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "$name")" "$hint"
  else
    printf "  %s✗%s %s %s\n" "$C_MISS" "$C_OFF" "$(pad "$name")" "$hint"
    MISS=$((MISS+1))
  fi
}

opt_chk() {
  local name="$1" cmd="$2" hint="$3"
  if eval "$cmd" >/dev/null 2>&1; then
    printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "$name")" "$hint"
  else
    printf "  %s○%s %s %s（可选）\n" "$C_OPT" "$C_OFF" "$(pad "$name")" "$hint"
    OPT_MISS=$((OPT_MISS+1))
  fi
}

# cad 可能不在 PATH（uv tool 装在 ~/.local/bin）
if ! command -v cad >/dev/null 2>&1 && [ -x "$HOME/.local/bin/cad" ]; then
  export PATH="$HOME/.local/bin:$PATH"
fi

echo
echo "══════════════════════════════════════════════════════════════════"
echo " Agent × 3D 环境自检（text-to-cad 0.11.x）"
echo "══════════════════════════════════════════════════════════════════"

echo
echo "▎核心链路（缺了就没法开工）"
chk "cad"                "command -v cad"                            "CAD 内核 + 命令（STEP/URDF/MJCF/出图）"
chk "cad 版本 ≥ 0.11"     "cad --version | grep -qE '0\.(1[1-9]|[2-9][0-9])'" "0.11 才有 CAD→URDF 和关节限位推导"
chk "cad server"         "cad server status"                         "常驻引擎；不跑 cad server start 会自动起"
chk "CAD 内核环境"        "ls ~/.cache/cad/base >/dev/null 2>&1"      "首次 build/view 时自动下载（约 240 MB）"
chk "git"                "command -v git"                            "版本管理"
chk "gh"                 "command -v gh"                             "GitHub CLI（建仓/协作）"

echo
echo "▎skill 插件"
if command -v cad >/dev/null 2>&1; then
  SKILLS=$(ls ~/.claude/plugins/marketplaces/earthtojake/skills 2>/dev/null | tr '\n' ' ')
  if [ -n "$SKILLS" ]; then
    printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "text-to-cad 插件")" "$SKILLS"
  else
    printf "  %s✗%s %s %s\n" "$C_MISS" "$C_OFF" "$(pad "text-to-cad 插件")" "未装：curl -fsSL https://texttocad.dev/install.sh | sh"
    MISS=$((MISS+1))
  fi
  ENABLED=$(python3 -c "
import json,os
d=json.load(open(os.path.expanduser('~/.claude/settings.json')))
print(d.get('enabledPlugins',{}).get('text-to-cad@earthtojake',''))
" 2>/dev/null)
  if [ "$ENABLED" = "True" ] || [ "$ENABLED" = "true" ]; then
    printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "Claude Code 已启用")" "text-to-cad@earthtojake"
  else
    printf "  %s!%s %s %s\n" "$C_OPT" "$C_OFF" "$(pad "Claude Code 已启用")" "需重启会话或查 settings.json 的 enabledPlugins"
  fi
fi

echo
echo "▎项目目录里不该留的旧 skill 镜像"
STALE=0
for d in .claude .agents .trae .windsurf .qoder .zcode .zencoder .pi .minimax; do
  for proj in "$HOME"/100-Vibe/*/; do
    proj="${proj%/}"
    case "$proj" in *.bak*|*.old*) continue ;; esac   # 备份目录不算
    p="$proj/$d/skills"
    [ -d "$p" ] || continue
    if grep -rql "text-to-cad" "$p"/*/SKILL.md 2>/dev/null; then
      printf "  %s!%s %s %s\n" "$C_OPT" "$C_OFF" "$(pad "$p")" "旧的 0.6 时代 skill 镜像，会盖住新插件"
      STALE=$((STALE+1))
    fi
  done
done
[ "$STALE" -eq 0 ] && printf "  %s✓%s %s %s\n" "$C_OK" "$C_OFF" "$(pad "无残留")" "干净"

echo
echo "▎扩展工具链（按用途选装，不装也能开工）"
opt_chk "uv / uvx"         "command -v uv"                    "跑 MCP server（Blender/FreeCAD…）"
opt_chk "node / npx"       "command -v node"                  "npx skills add 装 skill"
opt_chk "blender"          "command -v blender || ls -d /Applications/Blender.app 2>/dev/null" "有机体建模/场景；官方+社区 MCP"
opt_chk "freecad"          "command -v freecad || command -v FreeCADCmd"                       "GUI 参数化 CAD + 机器人装配"
opt_chk "切片器 orca"       "command -v orca-slicer"           "print3d skill 真正出片用"
opt_chk "切片器 prusa"      "command -v prusa-slicer"          "同上，二选一"
opt_chk "mujoco"           "python3 -c 'import mujoco'"       "URDF→仿真，验证关节限位与碰撞"
opt_chk "trimesh"          "python3 -c 'import trimesh'"      "网格分析/修整/凸包"
opt_chk "yourdfpy"         "python3 -c 'import yourdfpy'"     "URDF 解析与遍历"
opt_chk "pyvista / vtk"    "python3 -c 'import pyvista'"      "网格可视化"

echo
echo "══════════════════════════════════════════════════════════════════"
if [ "$MISS" -eq 0 ]; then
  printf " 核心链路 %s齐备%s —— 可选缺 %d 项，不阻塞\n" "$C_OK" "$C_OFF" "$OPT_MISS"
  echo "══════════════════════════════════════════════════════════════════"
  echo
  echo "下一步（以一个零件为例）："
  echo "  1. 建模   cad run src/<model>.py                # STEP 随 run 写出"
  echo "  2. 出图   cad model snapshot <id> tmp/x.png     # OCCT 无头渲染，1～2 秒"
  echo "  3. 看图   浏览器打开 cad run 打印的 view 链接"
  exit 0
else
  printf " 核心链路缺 %s%d%s 项 —— 先补齐\n" "$C_MISS" "$MISS" "$C_OFF"
  echo "══════════════════════════════════════════════════════════════════"
  echo
  echo "补齐命令：curl -fsSL https://texttocad.dev/install.sh | sh"
  exit 1
fi
