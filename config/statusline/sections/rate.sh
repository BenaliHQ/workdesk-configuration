# Section: Rate limits (5-hour and 7-day)
# Displays used percentage and reset time. Reset = end of rolling window from
# now: +5h for the 5h window, +7d for 7d. Times render in the system's local
# timezone; set STATUSLINE_RATE_TZ (e.g. "America/Chicago") to override.
rate_date() {
    if [ -n "${STATUSLINE_RATE_TZ:-}" ]; then
        TZ="$STATUSLINE_RATE_TZ" date "$@" 2>/dev/null | tr '[:upper:]' '[:lower:]'
    else
        date "$@" 2>/dev/null | tr '[:upper:]' '[:lower:]'
    fi
}

render_rate() {
    local has_data=false

    if [ "$sl_rate_5h" -ge 0 ] 2>/dev/null; then
        has_data=true
        local c label reset_time
        c=$(tier_color "$sl_rate_5h")
        reset_time=$(rate_date -v+5H "+%-I:%M%p")
        label="5h:${sl_rate_5h}%"
        [ -n "$reset_time" ] && label="${label} rst:${reset_time}"
        append_line2 "${c}${label}${R}"
    fi

    if [ "$sl_rate_7d" -ge 0 ] 2>/dev/null; then
        has_data=true
        local c label reset_time
        c=$(tier_color "$sl_rate_7d")
        reset_time=$(rate_date -v+7d "+%a %-I:%M%p")
        label="7d:${sl_rate_7d}%"
        [ -n "$reset_time" ] && label="${label} rst:${reset_time}"
        append_line2 "${c}${label}${R}"
    fi
}
