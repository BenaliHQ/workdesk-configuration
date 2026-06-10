# Section: Loaded context files (CLAUDE.md, rules, etc.)
render_files() {
    [ "$STATUSLINE_FILES_ENABLED" != "true" ] && return

    local dir="${sl_current_dir:-$PWD}"
    local files=()

    # Check for common context files
    [ -f "$dir/CLAUDE.md" ] && files+=("CLAUDE.md")
    [ -f "$HOME/.claude/CLAUDE.md" ] && files+=("~CLAUDE.md")

    # Count rule files
    local rule_count=0
    [ -d "$dir/.claude/rules" ] && rule_count=$(find "$dir/.claude/rules" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')

    if [ "$SL_MODE" = "full" ]; then
        local file_list=""
        for f in "${files[@]}"; do
            [ -n "$file_list" ] && file_list="${file_list}, "
            file_list="${file_list}${f}"
        done
        if [ "$rule_count" -gt 0 ]; then
            [ -n "$file_list" ] && file_list="${file_list}, "
            file_list="${file_list}${rule_count} rules"
        fi
        if [ -n "$file_list" ]; then
            append_line3 "${LABEL}FILES:${R} ${MUTED}${file_list}${R}"
        fi
    else
        local total=${#files[@]}
        total=$((total + rule_count))
        if [ "$total" -gt 0 ]; then
            append_line2 "${MUTED}${total} files${R}"
        fi
    fi
}
