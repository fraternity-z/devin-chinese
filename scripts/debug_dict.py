# -*- coding: utf-8 -*-
from _paths import DEVIN_APP

src = open(DEVIN_APP / "node_modules" / "@exa" / "chat-client" / "index.js",
           encoding="utf-8", errors="ignore").read()
p = src.find("jn=JSON.parse")
seg = src[p:p + 60]
print("found jn=JSON.parse at", p)
print("bytes:", [hex(ord(c)) for c in seg[:20]])
print("text :", seg[:50])
# locate the quote that opens the JSON string
i = src.find("JSON.parse(", p) + 11
print("char at i:", repr(src[i]), "next:", repr(src[i:i + 30]))
# scan to find the closing unescaped quote
depth = i
buf_end = None
j = i
while j < len(src):
    ch = src[j]
    if ch == "\\":
        j += 2
        continue
    if ch == src[i - 1]:  # same quote char that opened JSON.parse(
        buf_end = j
        break
    j += 1
print("end at", buf_end, "next chars:", repr(src[buf_end:buf_end + 10]) if buf_end else None)
