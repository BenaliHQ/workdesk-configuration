# Section: Agent name and worktree (only shown when active)
render_agent() {
    if [ -n "$sl_agent_name" ]; then
        append_line1 "${PURPLE}@${sl_agent_name}${R}"
    fi
    if [ -n "$sl_worktree_name" ]; then
        append_line1 "${ORANGE}⎇ ${sl_worktree_name}${R}"
    fi
}
