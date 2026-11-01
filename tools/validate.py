#!/usr/bin/env python3
"""Checks every file in bullets/ against the format in CONTRIBUTING.md.

Runs on every pull request. Errors fail the check; warnings are printed for the
reviewer and point at numbers worth a second look against the source.
Usage: python3 tools/validate.py [bullets-dir]
"""
import json, re, sys
from pathlib import Path

ID = re.compile(r'^[a-z0-9]+(-[a-z0-9_]+)+$')
SOURCE_TYPES = {'catalogue', 'website', 'box', 'doppler', 'dataset'}
BULLET_KEYS = {'id', 'name', 'diameter_in', 'weight_gr', 'bc', 'length_in', 'twist_in', 'source', 'discontinued'}
REQUIRED = {'id', 'name', 'diameter_in', 'weight_gr', 'bc', 'source'}
BC_MODELS = {'g1', 'g7'}


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_bullet(b, where, err, warn):
    if not isinstance(b, dict):
        return err(f'{where}: not an object')
    for k in REQUIRED - b.keys():
        err(f'{where}: missing "{k}"')
    for k in b.keys() - BULLET_KEYS:
        err(f'{where}: unknown field "{k}"')
    if not isinstance(b.get('id'), str) or not ID.match(b.get('id', '')):
        err(f'{where}: id must be lowercase letters, digits, "-" and "_"')
    name = b.get('name')
    if not isinstance(name, str) or not 1 <= len(name) <= 60 or name != name.strip():
        err(f'{where}: name must be 1-60 characters without leading or trailing spaces')
    elif re.search(r'https?://|www\.|[<>{}]', name):
        err(f'{where}: name must not contain links or markup')
    d, w = b.get('diameter_in'), b.get('weight_gr')
    if not is_num(d) or not 0.1 <= d <= 0.75:
        err(f'{where}: diameter_in must be a number between 0.1 and 0.75 inches')
    if not is_num(w) or not 10 <= w <= 1000:
        err(f'{where}: weight_gr must be a number between 10 and 1000 grains')
    bc = b.get('bc')
    if not isinstance(bc, dict) or not bc:
        err(f'{where}: bc needs at least one of g1, g7')
    else:
        for k, v in bc.items():
            if k not in BC_MODELS:
                err(f'{where}: unknown drag model "{k}" in bc')
            elif not is_num(v) or not 0.02 <= v <= 1.3:
                err(f'{where}: bc.{k} must be between 0.02 and 1.3')
        g1, g7 = bc.get('g1'), bc.get('g7')
        if is_num(g1) and is_num(g7) and g1 > 0 and not 1.6 <= g1 / g7 <= 2.4:
            warn(f'{where}: G1/G7 ratio {g1 / g7:.2f} is outside the usual 1.6-2.4')
        if is_num(d) and is_num(w) and d > 0 and is_num(g7):
            sd = w / 7000 / d ** 2
            if not 0.6 <= g7 / sd <= 1.5:
                warn(f'{where}: G7 {g7} is unusual for sectional density {sd:.3f} (form factor {sd / g7:.2f})')
    ln = b.get('length_in')
    if ln is not None and (not is_num(ln) or not is_num(d) or not 2 * d <= ln <= 7 * d):
        err(f'{where}: length_in must be between 2 and 7 calibers')
    tw = b.get('twist_in')
    if tw is not None and (not is_num(tw) or not 5 <= tw <= 20):
        err(f'{where}: twist_in must be between 5 and 20 inches per turn')
    if 'discontinued' in b and not isinstance(b['discontinued'], bool):
        err(f'{where}: discontinued must be true or false')
    s = b.get('source')
    if not isinstance(s, dict) or s.get('type') not in SOURCE_TYPES or not isinstance(s.get('ref'), str) or not s['ref'].strip():
        err(f'{where}: source needs a type ({", ".join(sorted(SOURCE_TYPES))}) and a ref')
    elif set(s) - {'type', 'ref', 'note'}:
        err(f'{where}: source has unknown fields {sorted(set(s) - {"type", "ref", "note"})}')


def validate(root):
    errors, warnings = [], []
    ids, keys, diameters = {}, {}, {}
    files = sorted(Path(root).glob('*.json'))
    if not files:
        errors.append(f'{root}: no bullet files')
    for f in files:
        err = lambda m, f=f: errors.append(f'{f.name}: {m}')
        warn = lambda m, f=f: warnings.append(f'{f.name}: {m}')
        try:
            text = f.read_text(encoding='utf-8')
            data = json.loads(text)
        except (ValueError, UnicodeDecodeError) as e:
            err(f'not valid JSON: {e}')
            continue
        if not isinstance(data, dict) or set(data) != {'maker', 'bullets'} or not isinstance(data['bullets'], list):
            err('must be {"maker": ..., "bullets": [...]}')
            continue
        maker = data['maker']
        if not isinstance(maker, str) or slug(maker) != f.stem:
            err(f'file name must be {slug(str(maker))}.json for maker "{maker}"')
        expected = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        if text != expected:
            err('formatting differs from the standard; run python3 tools/format.py')
        prev = None
        for i, b in enumerate(data['bullets']):
            where = f'{b.get("id", f"#{i}") if isinstance(b, dict) else f"#{i}"}'
            check_bullet(b, where, err, warn)
            if not isinstance(b, dict):
                continue
            bid = b.get('id')
            if bid in ids:
                err(f'{where}: id also used in {ids[bid]}')
            ids[bid] = f.name
            try:
                key = (b['diameter_in'], b['weight_gr'], b['name'])
                if prev is not None and key < prev:
                    err(f'{where}: bullets must be sorted by diameter, weight, name; run python3 tools/format.py')
                prev = key
                same = (maker, b['name'].lower(), round(b['diameter_in'], 3), b['weight_gr'])
                if same in keys:
                    err(f'{where}: same bullet as {keys[same]}')
                keys[same] = bid
                diameters.setdefault(round(b['diameter_in'], 3), []).append(f'{f.name}: {bid}')
            except (KeyError, TypeError):
                pass
    for d, where in diameters.items():
        if len(where) == 1:
            warnings.append(f'{where[0]}: no other bullet has diameter {d}"; check the units')
    return errors, warnings, len(ids)


if __name__ == '__main__':
    errors, warnings, n = validate(sys.argv[1] if len(sys.argv) > 1 else 'bullets')
    for w in warnings:
        print(f'::warning::{w}' if 'GITHUB_ACTIONS' in __import__('os').environ else f'warning: {w}')
    for e in errors:
        print(f'::error::{e}' if 'GITHUB_ACTIONS' in __import__('os').environ else f'error: {e}')
    print(f'{n} bullets, {len(errors)} errors, {len(warnings)} warnings')
    sys.exit(1 if errors else 0)
