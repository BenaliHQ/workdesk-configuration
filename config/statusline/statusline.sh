#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code Status Line
# ═══════════════════════════════════════════════════════════════════════════════
# A modular, configurable, team-distributable status line for Claude Code.
#
# Config: ~/.claude/statusline.conf (overrides defaults)
# Themes: dark | light | minimal
# Docs:   ~/.claude/statusline/README.md
# ═══════════════════════════════════════════════════════════════════════════════

set +e

STATUSLINE_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── Read stdin ──────────────────────────────────────────────────────────────
STATUSLINE_INPUT=$(cat)

# ─── Dependency check ────────────────────────────────────────────────────────
# The JSON parser requires jq. Degrade to a friendly hint instead of garbage.
if ! command -v jq >/dev/null 2>&1; then
    printf '── statusline needs jq — install with: brew install jq\n'
    exit 0
fi

# ─── Load config ─────────────────────────────────────────────────────────────
source "$STATUSLINE_DIR/statusline.defaults.conf"
[ -f "$HOME/.claude/statusline.conf" ] && source "$HOME/.claude/statusline.conf"

# ─── Load theme ──────────────────────────────────────────────────────────────
theme_file="$STATUSLINE_DIR/themes/${STATUSLINE_THEME}.sh"
[ -f "$theme_file" ] && source "$theme_file" || source "$STATUSLINE_DIR/themes/dark.sh"

# ─── Load libraries ─────────────────────────────────────────────────────────
source "$STATUSLINE_DIR/lib/cache.sh"
source "$STATUSLINE_DIR/lib/helpers.sh"
source "$STATUSLINE_DIR/lib/layout.sh"
source "$STATUSLINE_DIR/lib/parse.sh"

# ─── Init theme-dependent values ─────────────────────────────────────────────
init_separator

# ─── Parse and detect ───────────────────────────────────────────────────────
parse_json
detect_mode

# ─── Render sections ────────────────────────────────────────────────────────
IFS=',' read -ra sections <<< "$STATUSLINE_SECTIONS"
for section in "${sections[@]}"; do
    section=$(echo "$section" | tr -d ' ')
    section_file="$STATUSLINE_DIR/sections/${section}.sh"
    if [ -f "$section_file" ]; then
        source "$section_file"
        "render_${section}" 2>/dev/null || true
    fi
done

# ─── Output ─────────────────────────────────────────────────────────────────
print_statusline

exit 0
