"""Patch the installed Devin app files that a VSIX language pack cannot reach:

1. extensions/*/package.json        - literal display strings (pkg_patch.json)
2. extensions/*/dist/*.js           - hard-coded UI strings (extjs_patch.json)
3. node_modules/@exa/chat-client/index.js
   - inject zh "translation" dict via the app's englishOverrides mechanism
   - inject zh "review" dict via an added addResourceBundle call

Idempotent and update-aware:
- patched files are detected by a marker/probe and skipped
- if a file changed since the backup (Devin update replaced it), the backup is
  refreshed and the patch reapplied to the new file

Requires Devin restart to take effect.
"""
import json, os, shutil, sys

from _paths import CHAT_BUILD_DIR, DEVIN_APP, TRANSLATIONS_DIR

APP = str(DEVIN_APP)
EXT = os.path.join(APP, 'extensions')
CHAT = os.path.join(APP, 'node_modules', '@exa', 'chat-client', 'index.js')
BAK = '.devin-zh.bak'
MARK = '/*devin-zh*/'


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


def patch_chat_client(tr_path=CHAT_BUILD_DIR / 'chat_zh_translation.json',
                      rv_path=CHAT_BUILD_DIR / 'chat_zh_review.json'):
    print('== chat-client index.js ==')
    if not os.path.exists(CHAT):
        print(f'  SKIP missing {CHAT}')
        return
    tr = open(tr_path, encoding='utf-8').read().strip()
    rv = open(rv_path, encoding='utf-8').read().strip()
    probe = json.loads(tr)['transcript']['cancel']
    state, text = file_state(CHAT, probe)
    if state == 'patched':
        print('  already patched')
        return

    anchor = "englishOverrides:JSON.parse('"
    i = text.find(anchor)
    if i < 0:
        print('  FATAL: englishOverrides anchor not found')
        sys.exit(1)
    j = text.find("')})", i + len(anchor))
    if j < 0:
        print('  FATAL: end of englishOverrides literal not found')
        sys.exit(1)
    text = text[:i + len(anchor)] + js_str(tr)[1:-1] + text[j:]

    tail_anchor = 'addResourceBundle("en","translation",t,!0,!0),Uo}'
    k = text.find(tail_anchor)
    if k < 0:
        print('  FATAL: addResourceBundle tail anchor not found')
        sys.exit(1)
    inject = ('addResourceBundle("en","translation",t,!0,!0),'
              'Uo.addResourceBundle("en","review",JSON.parse(' + js_str(rv) + '),!0,!0),Uo}/*devin-zh*/')
    text = text[:k] + inject + text[k + len(tail_anchor):]

    open(CHAT, 'w', encoding='utf-8').write(text)
    print(f'  injected translation ({len(tr)//1024}KB) + review ({len(rv)//1024}KB) dicts')


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if only in ('all', 'pkg'):
        patch_package_json(json.load(open(TRANSLATIONS_DIR / 'extensions' / 'pkg_patch.json', encoding='utf-8')))
    if only in ('all', 'js'):
        patch_ext_js(json.load(open(TRANSLATIONS_DIR / 'extensions' / 'extjs_patch.json', encoding='utf-8')))
    if only in ('all', 'chat'):
        patch_chat_client()
    print('done. restart Devin to apply.')


if __name__ == '__main__':
    main()
