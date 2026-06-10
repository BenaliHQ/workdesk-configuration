# Section: Quote of the day
render_quote() {
    [ "$STATUSLINE_QUOTE_ENABLED" != "true" ] && return

    local quote=""
    if [ -f "$STATUSLINE_QUOTE_FILE" ]; then
        quote=$(cat "$STATUSLINE_QUOTE_FILE" 2>/dev/null)
    fi

    [ -z "$quote" ] && return

    # Only show in full mode
    if [ "$SL_MODE" = "full" ]; then
        append_line3 "${ORANGE}*${R} ${DIM}${quote}${R}"
    fi
}
