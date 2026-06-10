# ─── Helper Functions ────────────────────────────────────────────────────────

short_model() {
    case "$1" in
        *opus*|*Opus*)     echo "Opus" ;;
        *sonnet*|*Sonnet*) echo "Sonnet" ;;
        *haiku*|*Haiku*)   echo "Haiku" ;;
        *)                 echo "$1" ;;
    esac
}

format_duration() {
    local sec=$(($1 / 1000))
    if [ "$sec" -ge 3600 ]; then
        echo "$((sec / 3600))h$((sec % 3600 / 60))m"
    elif [ "$sec" -ge 60 ]; then
        echo "$((sec / 60))m$((sec % 60))s"
    else
        echo "${sec}s"
    fi
}

format_tokens() {
    local n=$1
    if [ "$n" -ge 1000000 ]; then
        echo "$((n / 1000000)).$((n % 1000000 / 100000))M"
    elif [ "$n" -ge 1000 ]; then
        echo "$((n / 1000)).$((n % 1000 / 100))K"
    else
        echo "$n"
    fi
}

format_cost() {
    echo "$1" | awk '{
        if ($1 >= 1) printf "$%.2f", $1
        else if ($1 >= 0.01) printf "$%.2f", $1
        else if ($1 > 0) printf "$%.3f", $1
        else printf "$0.00"
    }'
}

perm_label() {
    case "$1" in
        bypassPermissions) echo "BYPASS" ;;
        acceptEdits)       echo "ACCEPT" ;;
        plan)              echo "PLAN" ;;
        dontAsk|auto)      echo "AUTO" ;;
        *)                 echo "DEFAULT" ;;
    esac
}

perm_color() {
    case "$1" in
        bypassPermissions) echo "$RED" ;;
        acceptEdits)       echo "$YELLOW" ;;
        plan)              echo "$BLUE" ;;
        *)                 echo "$GREEN" ;;
    esac
}

tier_color() {
    local pct=$1
    if [ "$pct" -le 40 ]; then
        echo "$GREEN"
    elif [ "$pct" -le 70 ]; then
        echo "$YELLOW"
    else
        echo "$RED"
    fi
}

# Separator — initialized after theme loads, uses theme's SEP color
init_separator() {
    SL_SEP=" ${SEP}|${R} "
}
