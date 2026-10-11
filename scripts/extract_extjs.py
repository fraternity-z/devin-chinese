# -*- coding: utf-8 -*-
"""Extract UI-API string literals from codeium extension JS bundles."""
import re
import json
import os

from _paths import DEVIN_APP, EXTRACTED_DIR

PAT = re.compile(
    r"(?:showInformationMessage|showErrorMessage|showWarningMessage|"
    r"showQuickPick|showInputBox|withProgress|setStatusBarMessage|"
    r"createQuickPick|showOpenDialog|showSaveDialog|showWorkspaceFolderPick|"
    r"showModal|createOutputChannel)\s*\(\s*([`\"'])")

FILES = [DEVIN_APP / "extensions" / rel for rel in (
    "windsurf/dist/extension.js",
    "windsurf/dist/458.js",
    "windsurf-dev-containers/dist/extension.js",
    "windsurf-remote-openssh/dist/extension.js",
    "windsurf-remote-wsl/dist/extension.js",
    "windsurf-remote-devin/dist/extension.js",
)]


def literals_after(src, pos, q):
    i = pos
    buf = []
    while i < len(src):
        ch = src[i]
        if ch == "\\":
            buf.append(src[i:i + 2])
            i += 2
            continue
        if ch == q:
            break
        buf.append(ch)
        i += 1
    return "".join(buf)


def main():
    out = {}
    for f in FILES:
        if not os.path.exists(f):
            continue
        src = open(f, encoding="utf-8", errors="ignore").read()
        found = set()
        for m in PAT.finditer(src):
            s = literals_after(src, m.end(), m.group(1))
            if 3 < len(s) < 200 and re.search(r"[A-Za-z]{2,} [A-Za-z]", s) \
                    and not s.startswith(("http", "/", ".", "${")):
                found.add(s)
        if found:
            out[os.path.basename(os.path.dirname(f)) + "/" +
               os.path.basename(f)] = sorted(found)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(EXTRACTED_DIR / "extjs_strings.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for k, v in out.items():
        print("==", k, len(v))
        for s in v[:60]:
            print("   ", repr(s))


if __name__ == "__main__":
    main()
