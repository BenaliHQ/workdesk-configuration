# Section: Environment info — model, version, permissions, session time
render_env() {
    local model_short
    model_short=$(short_model "$sl_model_name")
    local time_display
    time_display=$(format_duration "$sl_duration_ms")
    local perm
    perm=$(perm_label "$sl_permission_mode")
    local perm_c
    perm_c=$(perm_color "$sl_permission_mode")

    case "$SL_MODE" in
        nano)
            append_line1 "${CYAN}${model_short}${R}"
            append_line1 "${MUTED}${time_display}${R}"
            append_line2 "${perm_c}${perm}${R}"
            ;;
        compact)
            append_line1 "${CYAN}${model_short}${R}"
            append_line1 "${perm_c}${perm}${R}"
            append_line1 "${MUTED}${time_display}${R}"
            ;;
        full)
            local ver_display=""
            [ "$sl_cc_version" != "?" ] && ver_display="${DIM}v${sl_cc_version}${R}$(sep)"
            append_line1 "${CYAN}${model_short}${R}"
            append_line1 "${perm_c}${perm}${R}"
            append_line1 "${MUTED}${time_display}${R}"
            ;;
    esac
}
