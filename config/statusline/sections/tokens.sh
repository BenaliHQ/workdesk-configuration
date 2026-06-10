# Section: Token counts
render_tokens() {
    local in_display out_display
    in_display=$(format_tokens "$sl_total_in")
    out_display=$(format_tokens "$sl_total_out")

    case "$SL_MODE" in
        nano|compact)
            append_line2 "${LIGHT}${in_display}↓ ${out_display}↑${R}"
            ;;
        full)
            append_line1 "${LIGHT}${in_display} ↓  ${out_display} ↑${R}"
            ;;
    esac
}
