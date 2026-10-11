# -*- coding: utf-8 -*-
"""Extract user-visible strings from codeium.* extension package.json files."""
import json
import os

from _paths import DEVIN_APP, EXTRACTED_DIR

BASE = DEVIN_APP / "extensions"
EXTS = ["windsurf", "windsurf-dev-containers", "windsurf-remote-devin",
        "windsurf-remote-openssh", "windsurf-remote-wsl"]

# fields that hold user-visible text
FIELDS = ("title", "description", "markdownDescription", "label", "name",
          "category", "prompt", "placeHolder", "detailedDescription")


def walk(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and k in FIELDS and v.strip():
                out.add(v)
            else:
                walk(v, out)
    elif isinstance(o, list):
        for v in o:
            walk(v, out)


def main():
    res = {}
    for ext in EXTS:
        p = os.path.join(BASE, ext, "package.json")
        d = json.load(open(p, encoding="utf-8"))
        out = set()
        if d.get("displayName"):
            out.add(d["displayName"])
        walk(d.get("contributes", {}), out)
        # drop pure ids / technical values
        out = {s for s in out if " " in s or len(s) > 12}
        res[ext] = sorted(out)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(EXTRACTED_DIR / "pkg_strings.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for k, v in res.items():
        print("==", k, len(v))


if __name__ == "__main__":
    main()
