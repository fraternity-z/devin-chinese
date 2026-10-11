# -*- coding: utf-8 -*-
"""Diff Devin bundled extensions' l10n keys vs the official zh-hans pack.

For each extension:
  - 'package' keys come from package.nls.json
  - 'bundle' keys are literal first-args of l10n.t(...) / nls.localize(...) in *.js

Outputs ext_missing.json + report appended to ext_report.txt
"""
import json
import os
import re

from _paths import DEVIN_APP, EXTRACTED_DIR, PACK_DIR, REPORTS_DIR

EXT_DIR = DEVIN_APP / "extensions"
PACK_EXT_DIR = PACK_DIR / "translations" / "extensions"

# literal string arg: l10n.t("...") / l10n.t('...') / l10n.t(`...`) / localize("...", ...)
STR_RE = re.compile(
    r'''(?:l10n\.t|\.localize|nls\.localize)\(\s*([`'"])(.*?)\1\s*[,)]''', re.S)


def ext_id(pkg):
    return f"{pkg.get('publisher','')}.{pkg.get('name','')}".lower()


def js_keys(root):
    keys = set()
    for dp, _, fns in os.walk(root):
        if "node_modules" in dp:
            continue
        for fn in fns:
            if not fn.endswith(".js"):
                continue
            try:
                src = open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for m in STR_RE.finditer(src):
                s = m.group(2)
                # skip non-translatable junk: very short, no letters
                if re.search(r"[A-Za-z]{2,}", s):
                    keys.add(s)
    return keys


def main():
    pack_files = {f[:-10]: os.path.join(PACK_EXT_DIR, f)
                  for f in os.listdir(PACK_EXT_DIR) if f.endswith(".i18n.json")}
    report, missing_all = [], {}
    for ext in sorted(os.listdir(EXT_DIR)):
        ed = os.path.join(EXT_DIR, ext)
        pj = os.path.join(ed, "package.json")
        if not os.path.isfile(pj):
            continue
        pkg = json.load(open(pj, encoding="utf-8"))
        eid = ext_id(pkg)
        pf = pack_files.get(eid)

        # gather english keys
        pkg_keys = set()
        nlsf = os.path.join(ed, "package.nls.json")
        if os.path.isfile(nlsf):
            pkg_keys = set(json.load(open(nlsf, encoding="utf-8")).keys())
        bkeys = js_keys(ed)

        if pf:
            pk = json.load(open(pf, encoding="utf-8"))["contents"]
            pack_pkg = set(pk.get("package", {}).keys())
            pack_other = set()
            for m, kv in pk.items():
                if m != "package":
                    pack_other.update(kv.keys())
            mp = pkg_keys - pack_pkg
            mb = bkeys - pack_other
        else:
            mp, mb = pkg_keys, bkeys

        if mp or mb:
            missing_all[eid] = {
                "ext_dir": ed,
                "has_pack_file": bool(pf),
                "package_missing": sorted(mp),
                "bundle_missing_count": len(mb),
            }
            report.append(f"{eid}: pack={'yes' if pf else 'NO'} "
                          f"pkg_missing={len(mp)} bundle_missing={len(mb)}")

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(EXTRACTED_DIR / "ext_missing.json", "w", encoding="utf-8") as f:
        json.dump(missing_all, f, ensure_ascii=False, indent=1)
    with open(REPORTS_DIR / "ext_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("\n".join(report) if report else "all covered")


if __name__ == "__main__":
    main()
