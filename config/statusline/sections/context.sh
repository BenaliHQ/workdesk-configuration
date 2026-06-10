# Section: Context bar with percentage
render_context() {
    local bar_w
    bar_w=$(context_bar_width)
    local bar
    bar=$(render_bar "$bar_w" "$sl_context_pct")
    local pct_c
    pct_c=$(tier_color "$sl_context_pct")

    append_line1 "${bar} ${pct_c}${sl_context_pct}%${R}"
}
