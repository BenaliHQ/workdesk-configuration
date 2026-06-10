# Section: Working directory
render_dir() {
    local dir_name
    dir_name=$(basename "${sl_current_dir:-~}")
    append_line2 "${BLUE}${dir_name}${R}"
}
