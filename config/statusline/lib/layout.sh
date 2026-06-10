# ─── Layout Engine ───────────────────────────────────────────────────────────
# Manages terminal width detection, responsive modes, and line assembly.

detect_width() {
    local w=""
    w=$(stty size </dev/tty 2>/dev/null | awk '{print $2}') 2>/dev/null
    [ -z "$w" ] || [ "$w" = "0" ] && w=$(tput cols 2>/dev/null)
    [ -z "$w" ] || [ "$w" = "0" ] && w=${COLUMNS:-80}
    echo "$w"
}

detect_mode() {
    local w
    w=$(detect_width)
    SL_TERM_WIDTH="$w"
    if [ "$w" -lt 40 ]; then
        SL_MODE="nano"
    elif [ "$w" -lt 80 ]; then
        SL_MODE="compact"
    else
        SL_MODE="full"
    fi
}

# Get context bar width based on mode or config
context_bar_width() {
    if [ "$STATUSLINE_CONTEXT_BAR_WIDTH" = "auto" ]; then
        case "$SL_MODE" in
            nano)    echo 8 ;;
            compact) echo 12 ;;
            full)    echo 16 ;;
        esac
    else
        echo "$STATUSLINE_CONTEXT_BAR_WIDTH"
    fi
}

# Gradient context bar
render_bar() {
    local width=$1 pct=$2
    [ "$pct" -gt 100 ] && pct=100
    local filled=$((pct * width / 100))
    [ "$filled" -lt 0 ] && filled=0
    local output=""

    for i in $(seq 1 "$width"); do
        if [ "$i" -le "$filled" ]; then
            local pos_pct=$((i * 100 / width))
            local r g b
            if [ "$pos_pct" -le 50 ]; then
                r=$((91 + (212 - 91) * pos_pct / 50))
                g=$((185 + (160 - 185) * pos_pct / 50))
                b=$((140 + (74 - 140) * pos_pct / 50))
            else
                local t=$((pos_pct - 50))
                r=$((212 + (224 - 212) * t / 50))
                g=$((160 + (108 - 160) * t / 50))
                b=$((74 + (108 - 74) * t / 50))
            fi
            output="${output}$(printf '\033[38;2;%d;%d;%dm' "$r" "$g" "$b")━${R}"
        else
            output="${output}${CTX_EMPTY}╌${R}"
        fi
    done
    echo "$output"
}

# Line buffers — sections append to these
SL_LINE1=""
SL_LINE2=""
SL_LINE3=""

append_line1() {
    if [ -n "$SL_LINE1" ]; then
        SL_LINE1="${SL_LINE1}${SL_SEP}$1"
    else
        SL_LINE1="$1"
    fi
}

append_line2() {
    if [ -n "$SL_LINE2" ]; then
        SL_LINE2="${SL_LINE2}${SL_SEP}$1"
    else
        SL_LINE2="$1"
    fi
}

append_line3() {
    if [ -n "$SL_LINE3" ]; then
        SL_LINE3="${SL_LINE3}${SL_SEP}$1"
    else
        SL_LINE3="$1"
    fi
}

# Final output
print_statusline() {
    local prefix="${SEP}──${R} "
    [ "$SL_MODE" = "nano" ] && prefix="${SEP}─${R} "

    [ -n "$SL_LINE1" ] && printf '%s\n' "${prefix}${SL_LINE1}"
    [ -n "$SL_LINE2" ] && printf '%s\n' "${prefix}${SL_LINE2}"
    [ -n "$SL_LINE3" ] && printf '%s\n' "${prefix}${SL_LINE3}"
}
