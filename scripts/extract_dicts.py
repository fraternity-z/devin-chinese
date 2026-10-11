# -*- coding: utf-8 -*-
"""Extract the embedded i18next JSON.parse dicts from @exa/chat-client."""
import json
import re

from _paths import DEVIN_APP, EXTRACTED_DIR

SRC = DEVIN_APP / "node_modules" / "@exa" / "chat-client" / "index.js"

SIMPLE = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
          "v": "\v", "0": "\0", "'": "'", '"': '"', "`": "`",
          "\\": "\\", "$": "$"}


def js_unescape(s):
    """Interpret JS string escape sequences -> real text."""
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = s[i + 1]
        if nxt == "x":
            out.append(chr(int(s[i + 2:i + 4], 16)))
            i += 4
        elif nxt == "u" and s[i + 2] == "{":
            j = s.index("}", i + 2)
            out.append(chr(int(s[i + 3:j], 16)))
            i = j + 1
        elif nxt == "u":
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        elif nxt == "\n":
            i += 2  # line continuation
        else:
            out.append(SIMPLE.get(nxt, nxt))
            i += 2
    return "".join(out)


def js_escape(s):
    """Inverse of js_unescape for a single-quoted JS literal."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "'":
            out.append("\\'")
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20 or o > 0x7E:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    return "".join(out)


def extract_json_parse(src, pos):
    """pos = index of `X=JSON.parse` -> (obj, start, end_exclusive).
    start/end delimit the JSON text inside the quotes (raw JS-escaped)."""
    q = src.find("JSON.parse('", pos) + 11
    i = q + 1
    while True:
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'":
            break
        i += 1
    raw = src[q + 1:i]
    return json.loads(js_unescape(raw)), q + 1, i


def iter_leaves(d, pre=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from iter_leaves(v, pre + k + ".")
        else:
            yield pre + k, v


def main():
    src = open(SRC, encoding="utf-8", errors="ignore").read()
    jn, s1, e1 = extract_json_parse(src, src.find("jn=JSON.parse"))
    jr, s2, e2 = extract_json_parse(src, src.find("jr=JSON.parse"))
    jl = dict(iter_leaves(jn))
    rl = dict(iter_leaves(jr))
    print("translation keys:", len(jl), "span:", e1 - s1)
    print("review keys:", len(rl), "span:", e2 - s2)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(jl, open(EXTRACTED_DIR / "chat_translation_en.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(rl, open(EXTRACTED_DIR / "chat_review_en.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
