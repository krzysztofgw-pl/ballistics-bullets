#!/usr/bin/env python3
"""Turns bullet suggestions sent from the app into pull requests.

The app writes suggestions to the Firestore collection `submissions` (see
firestore.rules in the app repository). This script, run daily by
.github/workflows/submissions.yml with a service account token:

1. reads up to MAX suggestions with status "new";
2. applies each one to a branch `submission/<id>` (a new bullet, or a correction
   when it names an existing id or matches one);
3. runs the validator: an invalid suggestion is marked "invalid" and gets no PR;
4. opens a pull request for review and marks the suggestion "pr".

Environment: FIRESTORE_TOKEN (OAuth access token), FIREBASE_PROJECT, GH_TOKEN.
"""
import hashlib, json, os, re, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validate  # noqa: E402

MAX = 20
PROJECT = os.environ.get('FIREBASE_PROJECT', 'ballistics-kgw')
BASE = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents'
TOKEN = os.environ['FIRESTORE_TOKEN']
DRY = '--dry-run' in sys.argv


def api(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise SystemExit(f'Firestore {method} {url}: {e.code} {e.read().decode()[:500]}')


def decode(v):
    if 'stringValue' in v: return v['stringValue']
    if 'integerValue' in v: return int(v['integerValue'])
    if 'doubleValue' in v: return v['doubleValue']
    if 'booleanValue' in v: return v['booleanValue']
    if 'mapValue' in v: return {k: decode(x) for k, x in v['mapValue'].get('fields', {}).items()}
    if 'arrayValue' in v: return [decode(x) for x in v['arrayValue'].get('values', [])]
    if 'timestampValue' in v: return v['timestampValue']
    return None


def encode(v):
    if isinstance(v, str): return {'stringValue': v}
    if isinstance(v, list): return {'arrayValue': {'values': [encode(x) for x in v]}}
    raise TypeError(v)


def new_submissions():
    query = {'structuredQuery': {
        'from': [{'collectionId': 'submissions'}],
        'where': {'fieldFilter': {'field': {'fieldPath': 'status'}, 'op': 'EQUAL', 'value': {'stringValue': 'new'}}},
        'limit': MAX,
    }}
    rows = api('POST', f'{BASE}:runQuery', query) or []
    out = []
    for r in rows:
        d = r.get('document')
        if d:
            out.append((d['name'].rsplit('/', 1)[1], {k: decode(v) for k, v in d.get('fields', {}).items()}))
    return sorted(out, key=lambda x: x[1].get('createdAt', ''))


def set_status(sid, status, **extra):
    fields = {'status': status, **extra}
    mask = '&'.join(f'updateMask.fieldPaths={k}' for k in fields)
    if DRY:
        print(f'  [dry run] {sid}: {fields}')
        return
    api('PATCH', f'{BASE}/submissions/{sid}?{mask}', {'fields': {k: encode(v) for k, v in fields.items()}})


def blocked(uid):
    return api('GET', f'{BASE}/blocked/{uid}') is not None


def git(*args, check=True):
    return subprocess.run(['git', *args], check=check, text=True, capture_output=True).stdout.strip()


def num(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def dia_id(d):
    return re.sub(r'^0\.', '', f'{d:.4f}'.rstrip('0').rstrip('.'))


def strip_maker(name, maker):
    """'RWS R50' from maker RWS becomes 'R50'; a name that is only the maker stays."""
    name = name.strip()
    rest = re.sub(rf'^{re.escape(maker.strip())}\b[\s\-:,]*', '', name, flags=re.IGNORECASE)
    return rest if rest else name


def bullet_from(s):
    b = {'name': strip_maker(s['name'], s['maker']), 'diameter_in': num(s['diameter_in']), 'weight_gr': num(s['weight_gr']),
         'bc': {k: num(v) for k, v in sorted(s['bc'].items())}}
    for k in ('length_in', 'twist_in'):
        if s.get(k) is not None:
            b[k] = num(s[k])
    b['source'] = {'type': s['source']['type'], 'ref': s['source']['ref'].strip()}
    return b


def find(bid):
    for f in sorted(Path('bullets').glob('*.json')):
        data = json.loads(f.read_text(encoding='utf-8'))
        for i, b in enumerate(data['bullets']):
            if b['id'] == bid:
                return f, data, i
    return None


def apply(s):
    """Edits bullets/ for suggestion s; returns (file, old entry or None, new entry)."""
    maker = s['maker'].strip()
    new = bullet_from(s)
    wid = str(new['weight_gr']).replace('.', '_')
    guess = f"{validate.slug(maker)}-{validate.slug(new['name'])}-{dia_id(new['diameter_in'])}-{wid}"
    hit = (s.get('replaces') and find(s['replaces'])) or find(guess)
    if hit:
        f, data, i = hit
        old = data['bullets'][i]
        # Optional fields the suggestion leaves out keep their current values.
        entry = {'id': old['id'], **new}
        for k in ('length_in', 'twist_in', 'discontinued'):
            if k in old and k not in entry:
                entry[k] = old[k]
        entry = {k: entry[k] for k in ('id', 'name', 'diameter_in', 'weight_gr', 'bc', 'length_in', 'twist_in', 'discontinued', 'source') if k in entry}
        data['bullets'][i] = entry
    else:
        f = Path('bullets') / f'{validate.slug(maker)}.json'
        data = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'maker': maker, 'bullets': []}
        old = None
        entry = {k: v for k, v in {'id': guess, **new}.items()}
        data['bullets'].append(entry)
    data['bullets'].sort(key=lambda b: (b['diameter_in'], b['weight_gr'], b['name']))
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return f, old, entry, data['maker']


def code(v):
    """Shows user text literally: no markdown, links or @mentions take effect inside a code span."""
    s = str(v).replace('`', "'").replace('\n', ' ')
    return f'`{s}`' if s else '–'


def body(sid, s, f, old, entry, maker, warnings):
    who = hashlib.sha256(s['uid'].encode()).hexdigest()[:12]
    rows = [('Maker', maker), ('Name', entry['name']), ('Diameter, in', entry['diameter_in']),
            ('Weight, gr', entry['weight_gr']), ('G1', entry['bc'].get('g1')), ('G7', entry['bc'].get('g7')),
            ('Length, in', entry.get('length_in')), ('Twist, in', entry.get('twist_in'))]
    prev = {'Name': (old or {}).get('name'), 'Diameter, in': (old or {}).get('diameter_in'),
            'Weight, gr': (old or {}).get('weight_gr'), 'G1': (old or {}).get('bc', {}).get('g1'),
            'G7': (old or {}).get('bc', {}).get('g7'), 'Length, in': (old or {}).get('length_in'),
            'Twist, in': (old or {}).get('twist_in'), 'Maker': maker if old else None}
    lines = [f"{'Correction of' if old else 'New bullet'} `{entry['id']}` in `{f.name}`, suggested from the app.", '',
             '| | Suggested |' + (' Now |' if old else ''), '|---|---|' + ('---|' if old else '')]
    for k, v in rows:
        if v is None and not (old and prev.get(k) is not None):
            continue
        lines.append(f'| {k} | {code(v if v is not None else "")} |' + (f' {code(prev.get(k) if prev.get(k) is not None else "")} |' if old else ''))
    lines += ['', f"**Source** ({s['source']['type']}): {code(s['source']['ref'])}"]
    if s.get('note'):
        lines += ['', f"**Note from the submitter:** {code(s['note'][:500])}"]
    if warnings:
        lines += ['', '**Validator warnings**', *[f'- {code(w)}' for w in warnings]]
    lines += ['', f"Submitter: `{who}` (hashed account id) · app {code(s.get('app', ''))} · submission `{sid}`", '',
              'Check the numbers against the source before approving. To block a spammer, create the document '
              f'`blocked/<uid>` in Firestore; the submission `{sid}` holds the uid.']
    return '\n'.join(lines)


def main():
    subs = new_submissions()
    print(f'{len(subs)} new submissions')
    git('config', 'user.name', 'bullet-suggestions[bot]')
    git('config', 'user.email', 'bullet-suggestions@users.noreply.github.com')
    for sid, s in subs:
        print(f'- {sid}: {s.get("maker")} {s.get("name")}')
        if blocked(s.get('uid', '')):
            set_status(sid, 'blocked')
            continue
        git('checkout', '-q', '-B', f'submission/{sid}', 'origin/main')
        try:
            f, old, entry, maker = apply(s)
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            set_status(sid, 'invalid', errors=[f'malformed: {e}'])
            continue
        errors, warnings, _ = validate.validate('bullets')
        if errors:
            print('  invalid:', errors)
            set_status(sid, 'invalid', errors=errors[:20])
            git('checkout', '-q', '--', '.')
            git('clean', '-qfd', 'bullets')
            continue
        if not git('status', '--porcelain'):
            set_status(sid, 'duplicate')
            continue
        warnings = [w for w in warnings if entry['id'] in w]
        title = f"{'Correct' if old else 'Add'} {maker} {entry['name']} {dia_id(entry['diameter_in'])} {entry['weight_gr']} gr"
        git('add', 'bullets')
        git('commit', '-q', '-m', f'{title}\n\nSuggested from the app, submission {sid}.')
        if DRY:
            print('  [dry run]', title)
            print(body(sid, s, f, old, entry, maker, warnings))
            continue
        git('push', '-q', '-f', 'origin', f'submission/{sid}')
        url = subprocess.run(['gh', 'pr', 'create', '--base', 'main', '--head', f'submission/{sid}', '--title', title,
                              '--body', body(sid, s, f, old, entry, maker, warnings)],
                             check=True, text=True, capture_output=True).stdout.strip()
        # Pull requests opened with the workflow token do not trigger workflows, so start the check by hand.
        subprocess.run(['gh', 'workflow', 'run', 'check.yml', '--ref', f'submission/{sid}'], check=False)
        set_status(sid, 'pr', pr=url)
        print('  ', url)
    git('checkout', '-q', 'main', check=False)


if __name__ == '__main__':
    main()
