#!/usr/bin/env bash
# gws-layout.sh — detect which on-disk OAuth state layout the installed gws
# CLI uses, and where it lives. Source this; do not execute.
#
# googleworkspace-cli changed its storage model in 0.22:
#
#   legacy (pre-0.22)                       xdg (0.22+)
#   ~/Library/Application Support/gws       ~/.config/gws (XDG_CONFIG_HOME)
#   credentials.<b64-email>.enc (per acct)  credentials.enc (single file)
#   .encryption_key file on disk            key in the macOS Keychain (gws-cli)
#   accounts.json                           (no accounts.json)
#
# (0.22 layout field-verified on gws 0.22.5 by a downstream operator,
# 2026-08-03; legacy layout verified on gws 0.4.1.)
#
# wd_gws_detect_layout
#   Sets and exports:
#     GWS_LAYOUT     legacy | xdg | none
#     GWS_STATE_DIR  the state directory for the detected layout ("" if none)
#   Detection is state-presence-based: whichever directory actually holds
#   credentials wins; a directory holding only client_secret.json counts as
#   that layout with no credentials yet.
#
# wd_gws_state_present
#   Returns 0 iff a detected layout has BOTH client_secret.json and at least
#   one credential blob — i.e. gws has been fully set up on this machine.

wd_gws_detect_layout() {
  local legacy_dir="${HOME}/Library/Application Support/gws"
  local xdg_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/gws"

  GWS_LAYOUT="none"
  GWS_STATE_DIR=""

  if compgen -G "${legacy_dir}/credentials.*.enc" >/dev/null; then
    GWS_LAYOUT="legacy"; GWS_STATE_DIR="${legacy_dir}"
  elif [[ -s "${xdg_dir}/credentials.enc" ]]; then
    GWS_LAYOUT="xdg"; GWS_STATE_DIR="${xdg_dir}"
  elif [[ -s "${legacy_dir}/client_secret.json" ]]; then
    GWS_LAYOUT="legacy"; GWS_STATE_DIR="${legacy_dir}"
  elif [[ -s "${xdg_dir}/client_secret.json" ]]; then
    GWS_LAYOUT="xdg"; GWS_STATE_DIR="${xdg_dir}"
  fi

  export GWS_LAYOUT GWS_STATE_DIR
}

wd_gws_state_present() {
  wd_gws_detect_layout
  [[ "${GWS_LAYOUT}" == "none" ]] && return 1
  [[ -s "${GWS_STATE_DIR}/client_secret.json" ]] || return 1
  if [[ "${GWS_LAYOUT}" == "xdg" ]]; then
    [[ -s "${GWS_STATE_DIR}/credentials.enc" ]]
  else
    compgen -G "${GWS_STATE_DIR}/credentials.*.enc" >/dev/null
  fi
}
