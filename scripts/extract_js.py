# -*- coding: utf-8 -*-
"""Extract candidate UI string literals from Devin's hardcoded JS bundles."""
import re
import os
import collections
import json
import sys

from _paths import DEVIN_APP

LIT = re.compile(r"(['\"`])((?:\\.|(?!\1)[^\\])*?)\1")
SCHEME = re.compile(
    r"^(https?|wss?|vscode|devin|windsurf|file|mailto|data|command|cci|ssh|"
    r"untitled|vscode-[a-z-]+|urn|about|chrome|javascript|telnet|ftp|ws):", re.I)
CODEISH = re.compile(
    r"^[a-z_$][\w$]*(\.[\w$]+)+$"
    r"|^\S+\.(js|ts|tsx|jsx|json|css|scss|html|map|svg|png|jpg|woff2?|ttf|ico|lock|md|txt|yml|yaml|xml|sh|bat|cmd|ps1|py|rs|go|c|cpp|h|wasm|node|exe|dll|dylib|so)$"
    r"|^[\w./~-]+$")
CSSISH = re.compile(
    r"^[\w\s.,#%()\-+:;'\"<>*!=^$~\[\]&|/@]+$"  # css selector-ish
)
HEXISH = re.compile(r"^[\da-fA-F\-]{8,}$")

def candidates(path):
    src = open(path, encoding="utf-8", errors="ignore").read()
    cnt = collections.Counter()
    for m in LIT.finditer(src):
        s = m.group(2)
        if len(s) < 4 or len(s) > 200 or " " not in s:
            continue
        if not re.search(r"[A-Za-z]", s):
            continue
        if CODEISH.match(s) or SCHEME.match(s) or HEXISH.match(s):
            continue
        if re.search(r"\\x|\\u[0-9a-fA-F]{2,}|\\0", s):
            continue
        # css-ish: mostly selector characters and short
        if len(s) < 40 and CSSISH.match(s) and not re.search(r"[A-Za-z]{4,} [A-Za-z]{3,}", s):
            continue
        cnt[s] += 1
    return cnt


if __name__ == "__main__":
    files = sys.argv[1:] or [
        DEVIN_APP / "extensions" / "windsurf" / "dist" / "extension.js",
        DEVIN_APP / "node_modules" / "@exa" / "chat-client" / "index.js",
    ]
    for f in files:
        c = candidates(f)
        print("=" * 20, os.path.basename(os.path.dirname(f)),
              os.path.basename(f), "unique:", len(c))
        for s, n in c.most_common(60):
            print(f"  {n}x {s!r}")
