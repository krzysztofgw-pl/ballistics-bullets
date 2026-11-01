#!/usr/bin/env python3
"""Rewrites bullets/*.json in the standard layout: sorted, 2-space indent, UTF-8."""
import json, sys
from pathlib import Path

for f in sorted(Path(sys.argv[1] if len(sys.argv) > 1 else 'bullets').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    data = {'maker': data['maker'], 'bullets': sorted(data['bullets'], key=lambda b: (b['diameter_in'], b['weight_gr'], b['name']))}
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
