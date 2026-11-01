#!/usr/bin/env python3
"""Builds the file the apps download: one flat list of all bullets.

Usage: python3 tools/build_bundle.py OUT_DIR
Writes OUT_DIR/v1/bullets.json. The "v1" in the path is the bundle format;
a change that older apps cannot read goes to v2 while v1 keeps being published.
"""
import json, subprocess, sys, datetime
from pathlib import Path

out = Path(sys.argv[1]) / 'v1'
out.mkdir(parents=True, exist_ok=True)
bullets = []
for f in sorted(Path('bullets').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    bullets += [{'maker': data['maker'], **b} for b in data['bullets']]
bullets.sort(key=lambda b: (b['diameter_in'], b['maker'], b['weight_gr'], b['name']))
try:
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], text=True).strip()
    when = int(subprocess.check_output(['git', 'log', '-1', '--format=%ct'], text=True))
except (subprocess.CalledProcessError, FileNotFoundError):
    commit, when = '', int(datetime.datetime.now(datetime.timezone.utc).timestamp())
bundle = {
    'format': 1,
    # Seconds since 1970 of the commit: a newer bundle always has a bigger version.
    'version': when,
    'commit': commit,
    'license': 'CC-BY-SA-4.0, https://github.com/krzysztofgw-pl/ballistics-bullets',
    'bullets': bullets,
}
(out / 'bullets.json').write_text(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'{len(bullets)} bullets, version {when}')
