"""Patch the installed Devin app files that a VSIX language pack cannot reach:

1. extensions/*/package.json        - literal display strings (pkg_patch.json)
2. extensions/*/dist/*.js           - hard-coded UI strings (extjs_patch.json)
3. chat-client bundles (3 copies):
   - node_modules/@exa/chat-client/index.js
   - out/vs/workbench/windsurf-chat-client/index.js
   - out/vs/sessions/sessions.desktop.main.js
   each: inject zh "translation" dict via the app's englishOverrides mechanism
   (deep-merged over the original overrides) + zh "review" dict via an added
   addResourceBundle call on the file's own i18n instance
4. bundle hard-coded UI strings (ui_patch.json): the chat-client copies above
   plus out/vs/workbench/workbench.desktop.main.js - literal replacement
   inside anchored regions only, guarded so ids/categories/values compared
   with === are left untouched

Idempotent and update-aware:
- a patched file is recognized by the /*devin-zh*/ marker; if a .devin-zh.bak
  exists the patch is re-applied from the (pristine) backup, so translation
  updates take effect on re-run
- if a file changed since the backup (Devin update replaced it), the backup is
  refreshed and the patch reapplied to the new file
- backups are never created/refreshed from a file that contains the marker

Requires Devin restart to take effect.
"""
import base64, hashlib, json, os, re, shutil, sys

from _paths import CHAT_BUILD_DIR, DEVIN_APP, TRANSLATIONS_DIR

APP = str(DEVIN_APP)
EXT = os.path.join(APP, 'extensions')
CHAT_BUNDLES = [
    'node_modules/@exa/chat-client/index.js',
    'out/vs/workbench/windsurf-chat-client/index.js',
    'out/vs/sessions/sessions.desktop.main.js',
]
BAK = '.devin-zh.bak'
MARK = '/*devin-zh*/'
I18N_ANCHOR = "englishOverrides:JSON.parse('"
I18N_ANCHOR_END = "')})"
RB_TAIL = re.compile(r'(\w+)&&([\w$]+)\.addResourceBundle\("en","translation",\1,!0,!0\),\2\}')


def pristine(path):
    """Return pristine source text for path, maintaining the .devin-zh.bak.

    Patched files (MARK present) are re-patched from their backup so updated
    translations apply; backups are never refreshed from a MARKed file.
    Returns None when the file cannot be safely re-patched.
    """
    text = open(path, encoding='utf-8').read()
    bak = path + BAK
    if MARK in text:
        if not os.path.exists(bak):
            print(f'  ERROR patched file without backup: {path}')
            return None
        return open(bak, encoding='utf-8').read()
    if os.path.exists(bak):
        old = open(bak, encoding='utf-8').read()
        if MARK in old:
            print(f'  ERROR backup contains marker, not refreshing: {bak}')
            return None
        if old != text:
            shutil.copy2(path, bak)  # file was replaced externally: refresh backup
            print(f'  backup refreshed (file changed): {path}')
    else:
        shutil.copy2(path, bak)
        print(f'  backup {path}')
    return text


def file_state(path, probe):
    """'patched' if probe already present; else refresh/create backup and return 'go'."""
    text = open(path, encoding='utf-8').read()
    if probe and probe in text:
        return 'patched', text
    if os.path.exists(path + BAK):
        bak = open(path + BAK, encoding='utf-8').read()
        if bak != text:
            shutil.copy2(path, path + BAK)  # file was replaced externally: refresh backup
            print(f'  backup refreshed (file changed): {path}')
    else:
        shutil.copy2(path, path + BAK)
        print(f'  backup {path}')
    return 'go', text


def js_str(json_text):
    """Encode a JSON text as a JS single-quoted string literal."""
    return "'" + json_text.replace('\\', '\\\\').replace("'", "\\'") + "'"


def deep_merge(base, over):
    """base dict overridden by over dict, recursively for nested dicts."""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def inject_i18n(text, tr, rv):
    """Merge zh translation dict into englishOverrides and add the review
    resource bundle on the file's own i18n instance. Returns None on failure."""
    i = text.find(I18N_ANCHOR)
    if i < 0:
        print('    ERROR englishOverrides anchor not found')
        return None
    j = text.find(I18N_ANCHOR_END, i + len(I18N_ANCHOR))
    if j < 0:
        print('    ERROR end of englishOverrides literal not found')
        return None
    try:
        merged = deep_merge(json.loads(text[i + len(I18N_ANCHOR):j]), tr)
    except json.JSONDecodeError:
        print('    ERROR englishOverrides literal is not valid JSON')
        return None
    merged_js = json.dumps(merged, ensure_ascii=False, separators=(',', ':'))
    text = text[:i + len(I18N_ANCHOR)] + js_str(merged_js)[1:-1] + text[j:]

    m = RB_TAIL.search(text)
    if not m:
        print('    ERROR addResourceBundle tail anchor not found')
        return None
    inst = m.group(2)
    rv_js = js_str(json.dumps(rv, ensure_ascii=False, separators=(',', ':')))
    inject = (m.group(0)[:-1]
              + f',{inst}.addResourceBundle("en","review",JSON.parse({rv_js}),!0,!0)'
              + '}')
    return text[:m.start()] + inject + text[m.end():]


SKIP_BEFORE = ('category:', 'id:', 'labelKey:', 'key:', 'value:',
               '!==', '===', '==', '=', 'case')


def _guard_skip(before, after):
    """True when the literal sits in a position that must not be translated:
    preceded (ignoring whitespace) by category:/id:/labelKey:/key:/value:/=/
    ==/===/!==/case, or followed by === / !== / : (object key)."""
    before = before.rstrip()
    for suf in SKIP_BEFORE:
        if before.endswith(suf):
            if suf == 'case' and re.search(r'[\w$]case$', before):
                continue
            return True
    return after.lstrip().startswith(('===', '!==', ':'))


def patch_region(text, group, name):
    """Apply a ui_patch.json group's strings/raw maps inside its anchored
    region. Returns None when anchors are missing."""
    start_anchor, end_anchor = group['region']
    a = text.find(start_anchor)
    if a < 0:
        print(f'    ERROR region start anchor not found in {name}: {start_anchor[:60]!r}')
        return None
    b = text.find(end_anchor, a + len(start_anchor))
    if b < 0:
        print(f'    ERROR region end anchor not found in {name}: {end_anchor[:60]!r}')
        return None
    head, seg, tail = text[:a], text[a:b], text[b:]
    hit = skipped = 0
    misses = []
    # raw snippets first: several cover guarded ternary branches whose second
    # operand would otherwise be eaten by the strings pass below
    for en, zh in group.get('raw', {}).items():
        n = seg.count(en)
        if n:
            seg = seg.replace(en, zh)
            hit += n
        else:
            misses.append('raw ' + en[:60])
    for en, zh in group.get('strings', {}).items():
        done = 0
        for form in ('"', '`'):
            if form == '`' and '${' in en:
                continue
            tok = form + en + form
            out = []
            p = 0
            while True:
                i = seg.find(tok, p)
                if i < 0:
                    out.append(seg[p:])
                    break
                out.append(seg[p:i])
                if _guard_skip(seg[:i], seg[i + len(tok):]):
                    out.append(tok)
                    skipped += 1
                else:
                    out.append(form + zh + form)
                    done += 1
                p = i + len(tok)
            seg = ''.join(out)
        if done:
            hit += done
        else:
            misses.append(en[:60])
    print(f'    {name}: replaced {hit}, skipped-by-guard {skipped}, {len(misses)} miss')
    for m_ in misses:
        print(f'      MISS {m_}')
    return head + seg + tail


def patch_bundles(ui_patch, tr_path=CHAT_BUILD_DIR / 'chat_zh_translation.json',
                  rv_path=CHAT_BUILD_DIR / 'chat_zh_review.json'):
    print('== bundles ==')
    tr = json.load(open(tr_path, encoding='utf-8'))
    rv = json.load(open(rv_path, encoding='utf-8'))
    chat_rels = {rel.replace('/', os.sep) for rel in CHAT_BUNDLES}
    by_file = {}
    for group in ui_patch['groups']:
        for rel in group['files']:
            by_file.setdefault(rel.replace('/', os.sep), []).append(group)
    for rel_os in sorted(chat_rels | set(by_file)):
        path = os.path.join(APP, rel_os)
        if not os.path.exists(path):
            print(f'  SKIP missing {path}')
            continue
        print(f'  {rel_os}')
        text = pristine(path)
        if text is None:
            continue
        if rel_os in chat_rels:
            text = inject_i18n(text, tr, rv)
            if text is None:
                continue
        for group in by_file.get(rel_os, []):
            patched = patch_region(text, group, rel_os)
            if patched is not None:
                text = patched
        open(path, 'w', encoding='utf-8').write(text + MARK)
    update_checksums()


def file_sha256(path):
    """base64(sha256(file bytes)) with trailing '=' stripped (product.json format)."""
    digest = hashlib.sha256(open(path, 'rb').read()).digest()
    return base64.b64encode(digest).decode().rstrip('=')


def update_checksums():
    """Sync product.json checksums for patched bundles so Devin does not flag
    the installation as corrupt. Only entries whose file carries MARK are
    touched; entries for unpatched files are left alone."""
    path = os.path.join(APP, 'product.json')
    if not os.path.exists(path):
        print(f'  SKIP missing {path}')
        return
    text = open(path, encoding='utf-8').read()
    try:
        checksums = json.loads(text).get('checksums')
    except json.JSONDecodeError:
        print('  SKIP product.json is not valid JSON')
        return
    if not checksums:
        print('  SKIP no checksums in product.json')
        return
    bak = path + BAK
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f'  backup {path}')
    elif open(bak, encoding='utf-8').read() != text:
        # product.json changed externally (Devin update?): refresh the backup
        # only when it is still pristine, i.e. every checksum that covers a
        # patched bundle equals the hash of that bundle's pristine backup
        pristine_ = True
        for key, value in checksums.items():
            bundle_bak = os.path.join(APP, 'out', key) + BAK
            if os.path.exists(bundle_bak) and value != file_sha256(bundle_bak):
                pristine_ = False
        if pristine_:
            shutil.copy2(path, bak)
            print(f'  backup refreshed (product.json changed): {path}')
    updated = 0
    for key, old in list(checksums.items()):
        bundle = os.path.join(APP, 'out', key)
        if not os.path.exists(bundle):
            continue
        if MARK not in open(bundle, encoding='utf-8').read():
            continue
        new = file_sha256(bundle)
        if new == old:
            continue
        tok = f'"{old}"'
        if text.count(tok) != 1:
            print(f'  ERROR checksum value for {key} occurs {text.count(tok)} times, skipped')
            continue
        text = text.replace(tok, f'"{new}"')
        updated += 1
        print(f'  checksum updated {key}')
    if updated:
        open(path, 'w', encoding='utf-8').write(text)
    else:
        print('  checksums up to date')


def patch_package_json(patch):
    print('== package.json ==')
    for ext_dir, mapping in patch.items():
        path = os.path.join(EXT, ext_dir, 'package.json')
        if not os.path.exists(path):
            print(f'  SKIP missing {path}')
            continue
        probe = json.dumps(next(iter(mapping.values())), ensure_ascii=False)
        state, text = file_state(path, probe)
        if state == 'patched':
            print(f'  already patched {ext_dir}')
            continue
        hit = miss = 0
        for en, zh in mapping.items():
            tok = json.dumps(en, ensure_ascii=False)
            n = text.count(tok)
            if n:
                text = text.replace(tok, json.dumps(zh, ensure_ascii=False))
                hit += n
            else:
                miss += 1
        open(path, 'w', encoding='utf-8').write(text)
        print(f'  {ext_dir}: replaced {hit} occurrences, {miss} keys not found')


def patch_ext_js(patch):
    print('== extension js ==')
    for rel, mapping in patch.items():
        path = os.path.join(APP, rel.replace('/', os.sep))
        if not os.path.exists(path):
            print(f'  SKIP missing {path}')
            continue
        state, text = file_state(path, MARK)
        if state == 'patched':
            print(f'  already patched {rel}')
            continue
        hit = miss = 0
        misses = []
        for en, zh in mapping.items():
            variants = [
                ('`' + en + '`', '`' + zh + '`'),
                ('"' + en.replace('"', '\\"') + '"', '"' + zh.replace('"', '\\"') + '"'),
                ("'" + en.replace("'", "\\'") + "'", "'" + zh.replace("'", "\\'") + "'"),
            ]
            done = 0
            for old, new in variants:
                n = text.count(old)
                if n:
                    text = text.replace(old, new)
                    done += n
            if done:
                hit += done
            else:
                miss += 1
                misses.append(en[:60])
        text += MARK
        open(path, 'w', encoding='utf-8').write(text)
        print(f'  {rel}: replaced {hit} occurrences, {miss} not found')
        for m in misses:
            print(f'    MISS {m}')


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if only in ('all', 'pkg'):
        patch_package_json(json.load(open(TRANSLATIONS_DIR / 'extensions' / 'pkg_patch.json', encoding='utf-8')))
    if only in ('all', 'js'):
        patch_ext_js(json.load(open(TRANSLATIONS_DIR / 'extensions' / 'extjs_patch.json', encoding='utf-8')))
    if only in ('all', 'chat', 'ui'):
        patch_bundles(json.load(open(TRANSLATIONS_DIR / 'app' / 'ui_patch.json', encoding='utf-8')))
    print('done. restart Devin to apply.')


if __name__ == '__main__':
    main()
