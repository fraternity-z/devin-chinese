"""Merge chat_patch_*.json chunks into nested zh dicts and validate against the
extracted English dictionaries.

Outputs:
  chat_zh_translation.json  - nested dict for the "translation" namespace
  chat_zh_review.json       - nested dict for the "review" namespace
"""
import json, re, sys, glob

from _paths import CHAT_BUILD_DIR, EXTRACTED_DIR, TRANSLATIONS_DIR

TOK = re.compile(r'(\{\{[^}]*\}\}|<[^>]+>)')

def flatten(d, prefix='', out=None):
    out = {} if out is None else out
    for k, v in d.items():
        kk = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            flatten(v, kk, out)
        else:
            out[kk] = v
    return out

def load_chunks(pattern):
    merged = {}
    def merge(dst, src, path=''):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v, f'{path}.{k}' if path else k)
            else:
                dst[k] = v
    for f in sorted(glob.glob(pattern)):
        d = json.load(open(f, encoding='utf-8'))
        merge(merged, d)
        print(f'  merged {f}')
    return merged

def tokens(s):
    return sorted(TOK.findall(str(s)))

def validate(zh_flat, en_flat, name):
    missing_src = [k for k in zh_flat if k not in en_flat]
    # _one variants are fine to omit in zh, but keys we provide must exist (allow
    # zh key without _one/_other suffix if en only has _other variant? - enforce strict)
    bad_tok = [k for k in zh_flat if k in en_flat and tokens(zh_flat[k]) != tokens(en_flat[k])]
    print(f'{name}: {len(zh_flat)} zh keys, {len(en_flat)} en keys')
    if missing_src:
        print(f'  WARN {len(missing_src)} zh keys not in source:')
        for k in missing_src[:20]:
            print('   ', k)
    if bad_tok:
        print(f'  WARN {len(bad_tok)} keys with mismatched placeholders/tags:')
        for k in bad_tok[:30]:
            print(f'    {k}\n      en={tokens(en_flat[k])}\n      zh={tokens(zh_flat[k])}')
    return not (missing_src or bad_tok)

def main():
    print('merging translation chunks...')
    tr = load_chunks(str(TRANSLATIONS_DIR / 'chat' / 'chat_patch_[0-9]*.json'))
    print('loading review chunk...')
    rv = json.load(open(TRANSLATIONS_DIR / 'chat' / 'chat_patch_review.json', encoding='utf-8'))

    en_tr = json.load(open(EXTRACTED_DIR / 'chat_translation_en.json', encoding='utf-8'))
    en_rv = json.load(open(EXTRACTED_DIR / 'chat_review_en.json', encoding='utf-8'))

    tr_flat = flatten(tr)
    rv_flat = flatten(rv)

    # zh plural handling: drop *_one forms we may have written (zh uses _other);
    # if en only has _one/_other and zh only has _other that's correct already.
    ok1 = validate(tr_flat, en_tr, 'translation')
    ok2 = validate(rv_flat, en_rv, 'review')

    CHAT_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(tr, open(CHAT_BUILD_DIR / 'chat_zh_translation.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(rv, open(CHAT_BUILD_DIR / 'chat_zh_review.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'coverage: translation {len(tr_flat)}/{len(en_tr)} ({100*len(tr_flat)/len(en_tr):.1f}%), review {len(rv_flat)}/{len(en_rv)} ({100*len(rv_flat)/len(en_rv):.1f}%)')
    sys.exit(0 if (ok1 and ok2) else 1)

if __name__ == '__main__':
    main()
