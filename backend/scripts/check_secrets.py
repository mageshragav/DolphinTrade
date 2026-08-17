#!/usr/bin/env python3
"""Pre-commit secrets guard: blocks commits containing live credentials.

Scans the staged diff for known secret patterns (olymp JWTs, telegram bot
tokens, env passwords). Wire it up as a git hook:

    ln -sf ../../scripts/check_secrets.py .git/hooks/pre-commit
    # or
    printf '#!/bin/sh\\nexec python3 scripts/check_secrets.py\\n' > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
"""

import re
import subprocess
import sys

PATTERNS = [
    # full RS256 JWTs with realistic-length segments (test fixtures like
    # 'eyJhbGciOiJSUzI1NiJ9.newaccess' are short payloads and never match)
    (r"eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
     'Olymp/RS256 JWT (access_token / refresh_token)'),
    (r"access_token=eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
     'access_token cookie value'),
    (r"refresh_token=eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
     'refresh_token cookie value'),
    (r"(?<![:A-Za-z0-9])\d{9,10}:[A-Za-z0-9_-]{30,}",
     'Telegram bot token'),
]


def main() -> int:
    diff = subprocess.run(
        ['git', 'diff', '--cached', '--diff-filter=ACMR'],
        capture_output=True, text=True).stdout
    if not diff.strip():
        return 0
    bad = []
    # only scan ADDED lines (removals are secrets leaving the repo); skip
    # commented example lines (# DT_OLYMP_...=...) - real values live only
    # in the gitignored .env
    for raw_line in diff.splitlines():
        if not raw_line.startswith('+'):
            continue
        line = raw_line[1:].lstrip()
        if line.startswith('#'):
            continue
        for pattern, label in PATTERNS:
            for m in re.finditer(pattern, line):
                bad.append((label, m.group(0)[:40] + '...'))
    if bad:
        print('SECRETS DETECTED in staged changes - commit blocked:')
        for label, snippet in bad:
            print(f'  [{label}] {snippet}')
        print('\nMove secrets to backend/.env (gitignored) and stage again.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
