# Section: MCP server count
render_mcps() {
    local num_mcps=0
    for f in "${sl_current_dir:-.}/.mcp.json" "$HOME/.mcp.json"; do
        if [ -f "$f" ]; then
            local n
            n=$(jq '[.mcpServers // {} | keys[]] | length' "$f" 2>/dev/null || echo 0)
            num_mcps=$((num_mcps + n))
        fi
    done

    case "$SL_MODE" in
        nano)
            append_line2 "${CYAN}MCP:${num_mcps}${R}"
            ;;
        *)
            append_line2 "${CYAN}${num_mcps} mcp${R}"
            ;;
    esac
}
