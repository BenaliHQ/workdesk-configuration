#!/usr/bin/env bash
# gmail-draft.sh — create a Gmail draft with the operator's real Gmail signature.
#
# Gmail applies signatures client-side, in the compose window. Drafts created
# through the API are fully-formed messages, so the compose window never runs
# and the signature never gets attached. This script fetches the live signature
# from Gmail settings (settings.sendAs, the isDefault entry) and appends it to
# the HTML part of every draft it creates. It is never cached — editing the
# signature in Gmail settings flows through on the next draft.
#
# Usage:
#   config/scripts/gmail-draft.sh <spec.json>
#
# spec.json:
#   {
#     "to":         "Someone <someone@example.com>",     # required
#     "subject":    "Re: Thing",                          # required
#     "plain":      "plain-text body",                    # required
#     "html":       "<div dir=\"ltr\">body html</div>",   # required
#     "cc":         "optional",
#     "bcc":        "optional",
#     "threadId":   "optional — for a threaded reply",
#     "inReplyTo":  "optional — Message-ID being replied to",
#     "references": "optional — space-separated Message-ID chain"
#   }
#
# Body content goes in "html"/"plain" WITHOUT a signature; this script adds it.
#
# Prints the created draft's JSON on success.
#
# NOTE: this script only ever DRAFTS. Sending stays gated behind the operator's
# code phrase per the email-send safeguard in CLAUDE.md.

set -euo pipefail

SPEC="${1:-}"
if [[ -z "$SPEC" || ! -f "$SPEC" ]]; then
  echo "usage: gmail-draft.sh <spec.json>" >&2
  exit 2
fi

command -v gws >/dev/null 2>&1 || { echo "gws not found on PATH" >&2; exit 3; }

python3 - "$SPEC" <<'PY'
import base64, json, re, subprocess, sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def gws(*args):
    """Run a gws call and return its parsed JSON, tolerating banner output."""
    res = subprocess.run(('gws',) + args, capture_output=True, text=True)
    out = res.stdout
    if '{' not in out:
        raise SystemExit(f'gws call failed: {out}{res.stderr}')
    return json.loads(out[out.index('{'):])


def signature_html():
    """Live signature for the default send-as address. Never cached."""
    sendas = gws('gmail', 'users', 'settings', 'sendAs', 'list',
                 '--params', '{"userId":"me"}')['sendAs']
    default = next((s for s in sendas if s.get('isDefault')), None)
    if default is None:
        raise SystemExit('no default send-as address found')
    return default.get('signature', '') or ''


def html_to_text(html):
    """Rough HTML -> plain text, so the text/plain part carries a signature too."""
    if not html:
        return ''
    text = re.sub(r'(?i)<br\s*/?>', '\n', html)
    text = re.sub(r'(?i)</(div|p|tr|li)>', '\n', text)
    text = re.sub(r'(?i)<img[^>]*>', '', text)          # logos don't survive plain text
    text = re.sub(r'<[^>]+>', '', text)
    for entity, char in (('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'),
                         ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'"),
                         ('&rsquo;', "'"), ('&ldquo;', '"'), ('&rdquo;', '"'),
                         ('&mdash;', '--'), ('&ndash;', '-'), ('&divide;', '/')):
        text = text.replace(entity, char)
    lines = [ln.rstrip() for ln in text.splitlines()]
    out, blanks = [], 0
    for ln in lines:                                     # collapse runs of blank lines
        if ln.strip():
            out.append(ln.strip()); blanks = 0
        else:
            blanks += 1
            if blanks == 1 and out:
                out.append('')
    return '\n'.join(out).strip()


spec = json.load(open(sys.argv[1]))
for required in ('to', 'subject', 'plain', 'html'):
    if not spec.get(required):
        raise SystemExit(f'spec is missing required field: {required}')

sig_html = signature_html()
sig_text = html_to_text(sig_html)

msg = MIMEMultipart('alternative')
msg['To'] = spec['to']
msg['Subject'] = spec['subject']
for key, header in (('cc', 'Cc'), ('bcc', 'Bcc'),
                    ('inReplyTo', 'In-Reply-To'), ('references', 'References')):
    if spec.get(key):
        msg[header] = spec[key]

plain = spec['plain'].rstrip() + ('\n\n' + sig_text if sig_text else '') + '\n'
html = spec['html'] + '<div><br></div>' + sig_html

msg.attach(MIMEText(plain, 'plain', 'utf-8'))
msg.attach(MIMEText(html, 'html', 'utf-8'))

message = {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode()}
if spec.get('threadId'):
    message['threadId'] = spec['threadId']

# Body goes in --json; --params is query-only (body-in-params returns 411).
print(json.dumps(gws('gmail', 'users', 'drafts', 'create',
                     '--params', '{"userId":"me"}',
                     '--json', json.dumps({'message': message})), indent=2))
PY
