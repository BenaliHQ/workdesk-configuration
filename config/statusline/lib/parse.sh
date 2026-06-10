# ─── JSON Parsing ────────────────────────────────────────────────────────────
# Single jq call to extract all fields from Claude Code's stdin JSON.
# Every section reads from these global variables.

parse_json() {
    eval "$(echo "$STATUSLINE_INPUT" | jq -r '
        "sl_current_dir=" + (.workspace.current_dir // .cwd // "~" | @sh) + "\n" +
        "sl_model_name=" + (.model.display_name // "unknown" | @sh) + "\n" +
        "sl_cc_version=" + (.version // "?" | @sh) + "\n" +
        "sl_duration_ms=" + (.cost.total_duration_ms // 0 | tostring) + "\n" +
        "sl_total_cost=" + (.cost.total_cost_usd // 0 | tostring) + "\n" +
        "sl_cache_read=" + ((.context_window.current_usage.cache_read_input_tokens // 0) | tostring) + "\n" +
        "sl_input_tokens=" + ((.context_window.current_usage.input_tokens // 0) | tostring) + "\n" +
        "sl_cache_creation=" + ((.context_window.current_usage.cache_creation_input_tokens // 0) | tostring) + "\n" +
        "sl_output_tokens=" + ((.context_window.current_usage.output_tokens // 0) | tostring) + "\n" +
        "sl_context_max=" + (.context_window.context_window_size // 200000 | tostring) + "\n" +
        "sl_permission_mode=" + (.permissions.mode // "default" | @sh) + "\n" +
        "sl_rate_5h=" + (.rate_limits.five_hour.used_percentage // -1 | tostring) + "\n" +
        "sl_rate_7d=" + (.rate_limits.seven_day.used_percentage // -1 | tostring) + "\n" +
        "sl_rate_5h_reset=" + (.rate_limits.five_hour.reset_at // "" | @sh) + "\n" +
        "sl_rate_7d_reset=" + (.rate_limits.seven_day.reset_at // "" | @sh) + "\n" +
        "sl_agent_name=" + (.agent.name // "" | @sh) + "\n" +
        "sl_worktree_name=" + (.worktree.name // "" | @sh) + "\n" +
        "sl_conversation_id=" + (.conversation_id // "" | @sh)
    ' 2>/dev/null)" || true

    # Fallbacks
    sl_model_name="${sl_model_name:-unknown}"
    sl_cc_version="${sl_cc_version:-?}"
    sl_duration_ms="${sl_duration_ms:-0}"
    sl_total_cost="${sl_total_cost:-0}"
    sl_context_max="${sl_context_max:-200000}"
    sl_permission_mode="${sl_permission_mode:-default}"
    sl_rate_5h="${sl_rate_5h:--1}"
    sl_rate_7d="${sl_rate_7d:--1}"
    sl_agent_name="${sl_agent_name:-}"
    sl_worktree_name="${sl_worktree_name:-}"

    # Computed values
    sl_total_in=$((sl_cache_read + sl_input_tokens + sl_cache_creation))
    sl_total_out=$((sl_output_tokens))
    sl_context_used=$((sl_total_in + sl_total_out + 22000))
    if [ "$sl_context_max" -gt 0 ] && [ "$sl_context_used" -gt 0 ]; then
        sl_context_pct=$((sl_context_used * 100 / sl_context_max))
    else
        sl_context_pct=0
    fi
    [ "$sl_context_pct" -gt 100 ] && sl_context_pct=100
}
