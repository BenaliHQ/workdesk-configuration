# Section: Session cost
render_cost() {
    local cost_display
    cost_display=$(format_cost "$sl_total_cost")
    append_line1 "${GREEN}${cost_display}${R}"
}
