# Section: Skills count (with optional name list)
render_skills() {
    local skills_dir="$HOME/.claude/skills"
    local num_skills=0

    if [ -d "$skills_dir" ]; then
        local top nested
        top=$(find "$skills_dir" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
        nested=$(find "$skills_dir" -mindepth 2 -name 'SKILL.md' 2>/dev/null | wc -l | tr -d ' ')
        num_skills=$((top + nested))
    fi

    case "$SL_MODE" in
        nano)
            append_line2 "${PURPLE}SK:${num_skills}${R}"
            ;;
        *)
            append_line2 "${PURPLE}${num_skills} skills${R}"
            ;;
    esac
}
