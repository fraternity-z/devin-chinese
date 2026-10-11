# -*- coding: utf-8 -*-
"""Diff Devin's nls keys against the official VSCode zh-hans language pack.

Outputs:
  missing.json  - {module: {key: english_message}} for keys the pack doesn't cover
  extra.json    - pack entries that no longer exist in Devin (dead keys, kept anyway)
  report.txt    - human-readable summary
"""
import json
import os

from _paths import DEVIN_APP, EXTRACTED_DIR, PACK_DIR, REPORTS_DIR

DEVIN_OUT = DEVIN_APP / "out"


def load_devin_metadata():
    d = json.load(open(os.path.join(DEVIN_OUT, "nls.metadata.json"), encoding="utf-8"))
    out = {}
    for mod, keys in d["keys"].items():
        msgs = d["messages"][mod]
        m = {}
        for i, e in enumerate(keys):
            k = e["key"] if isinstance(e, dict) else e
            m[k] = msgs[i]
        out[mod] = m
    return out


def load_pack(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["contents"]


def main():
    devin = load_devin_metadata()
    pack = load_pack(os.path.join(PACK_DIR, "translations", "main.i18n.json"))

    missing, extra = {}, {}
    n_devin = sum(len(v) for v in devin.values())
    for mod, km in devin.items():
        pm = pack.get(mod, {})
        diff = {k: v for k, v in km.items() if k not in pm}
        if diff:
            missing[mod] = diff
    for mod, pm in pack.items():
        dm = devin.get(mod, {})
        diff = {k: v for k, v in pm.items() if k not in dm}
        if diff:
            extra[mod] = diff

    n_missing = sum(len(v) for v in missing.values())
    devin_mods = [m for m in missing if any(t in m.lower() for t in
                  ("devin", "windsurf", "cascade", "codeium"))]
    shared_mods = [m for m in missing if m not in devin_mods]

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(EXTRACTED_DIR / "missing.json", "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=1)
    with open(EXTRACTED_DIR / "extra.json", "w", encoding="utf-8") as f:
        json.dump(extra, f, ensure_ascii=False, indent=1)

    lines = [
        f"Devin core keys: {n_devin} across {len(devin)} modules",
        f"Missing from official pack: {n_missing} keys in {len(missing)} modules",
        f"  - devin/windsurf modules: {sum(len(missing[m]) for m in devin_mods)} keys in {len(devin_mods)} modules",
        f"  - shared modules (devin-added keys): {sum(len(missing[m]) for m in shared_mods)} keys in {len(shared_mods)} modules",
        f"Dead pack entries (kept anyway): {sum(len(v) for v in extra.values())}",
        "",
        "== modules with missing keys ==",
    ]
    for m in sorted(missing, key=lambda x: -len(missing[x])):
        lines.append(f"  {len(missing[m]):>4}  {m}")
    with open(REPORTS_DIR / "report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:8]))


if __name__ == "__main__":
    main()
