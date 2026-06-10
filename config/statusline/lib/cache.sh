# ─── Cache Helpers ───────────────────────────────────────────────────────────
# Fast file-based caching for expensive lookups.

STATUSLINE_CACHE_DIR="$HOME/.claude/statusline/cache"

# Read a cached value. Returns empty string if stale or missing.
# Usage: value=$(cache_read "key" 300)
cache_read() {
    local key="$1" ttl="${2:-$STATUSLINE_CACHE_TTL}"
    local file="$STATUSLINE_CACHE_DIR/$key"
    [ ! -f "$file" ] && return

    # Check freshness
    local now file_age mtime
    now=$(date +%s)
    mtime=$(stat -f %m "$file" 2>/dev/null || stat -c %Y "$file" 2>/dev/null || echo 0)
    file_age=$((now - mtime))

    if [ "$file_age" -le "$ttl" ]; then
        cat "$file"
    fi
}

# Write a value to cache.
# Usage: cache_write "key" "value"
cache_write() {
    local key="$1" value="$2"
    mkdir -p "$STATUSLINE_CACHE_DIR"
    echo "$value" > "$STATUSLINE_CACHE_DIR/$key"
}

# Count files matching a pattern, with caching based on directory mtime.
# Usage: count=$(cached_count "skills" "/path/to/dir" "find args...")
cached_count() {
    local cache_key="$1" dir="$2"
    shift 2
    local cached
    cached=$(cache_read "count-$cache_key" "$STATUSLINE_CACHE_TTL")
    if [ -n "$cached" ]; then
        echo "$cached"
        return
    fi
    local count
    count=$(eval "$@" 2>/dev/null | wc -l | tr -d ' ')
    cache_write "count-$cache_key" "$count"
    echo "$count"
}
