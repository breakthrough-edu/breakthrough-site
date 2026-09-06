#!/usr/bin/env python3
"""Refresh build/events.json from the vault's event date SOT.

Run from the site root:   python3 build/sync-events.py [--vault PATH] [--today YYYY-MM-DD] [--check]

Reads the Event Prep skill's month-graphic/overrides.json (the explicit event list), follows each event's
`brief` to its occurrence brief and takes the date from that brief's frontmatter (`started`/`due`), exactly
as the month graphic does (decision 2026-09-02-event-date-sot-is-per-brief-not-combined-table). Writes the
`upcoming` list, `synced` and `now` into events.json; `history` and `planned` (hand-typed tape entries) are kept as
they are. Prints what changed so the change can be confirmed before `build.py` + push.
`--check` only reports, writes nothing.
"""
import argparse, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = os.path.join(HERE, 'events.json')
VAULT = os.path.expanduser('~/Documents/breakthrough-vault')
OVERRIDES = '99_Meta/Skills/breakthrough-event-prep/month-graphic/overrides.json'
KINDS = {'BREAKTHROUGH LIVE': 'live', 'BUILD DAY': 'buildday', '2ND BRAIN INTENSIVE': 'intensive'}

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--vault', default=VAULT)
ap.add_argument('--today', default=datetime.date.today().isoformat())
ap.add_argument('--check', action='store_true')
A = ap.parse_args()


def frontmatter(path):
    txt = open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---', txt, re.S)
    fm = {}
    for line in (m.group(1) if m else '').splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip().strip('"\'')
    return fm


def edition(ev):
    i = ev['id']
    m = re.search(r'vol(\d+)', i)
    if m: return f'Vol {int(m.group(1)):02d}'
    m = re.search(r'build-day-(\d+)', i)
    if m: return f'No. {int(m.group(1)):02d}'
    m = re.search(r'cohort-(\d+)', i)
    if m: return f'Cohort {int(m.group(1)):02d}'
    sys.exit(f'{i}: cannot derive the edition from the id (expected volNN / build-day-NN / 2bi-cohort-NN)')


ov = json.load(open(os.path.join(A.vault, OVERRIDES), encoding='utf-8'))
upcoming = []
for ev in ov['events']:
    if not ev.get('brief'):
        continue                                   # historical / no-brief entries are not the site's business
    kind = KINDS.get(ev.get('kind', '').upper())
    if not kind:
        sys.exit(f'{ev["id"]}: unknown kind {ev.get("kind")!r}')
    fm = frontmatter(os.path.join(A.vault, ev['brief']))
    due = fm.get('due', '')[:10]
    start = (fm.get('started') or fm.get('start') or due)[:10]
    if not re.match(r'\d{4}-\d{2}-\d{2}$', start):
        sys.exit(f'{ev["id"]}: no started/due date in {ev["brief"]}')
    upcoming.append(dict(id=ev['id'], kind=kind, edition=edition(ev), start=start, end=due or start,
                         time=ev.get('time', ''), link=ev['link']))
upcoming.sort(key=lambda e: e['start'])

old = json.load(open(EVENTS, encoding='utf-8')) if os.path.exists(EVENTS) else {'history': []}
new = {'_readme': old.get('_readme', ''), 'synced': A.today, 'now': A.today,
       'history': old.get('history', []), 'planned': old.get('planned', []), 'upcoming': upcoming}

before = {e['id']: e for e in old.get('upcoming', [])}
after = {e['id']: e for e in upcoming}
changes = []
for i, e in after.items():
    if i not in before: changes.append(f'  + {i}: {e["start"]}..{e["end"]}')
    elif (before[i]['start'], before[i]['end'], before[i]['link']) != (e['start'], e['end'], e['link']):
        changes.append(f'  ~ {i}: {before[i]["start"]}..{before[i]["end"]} -> {e["start"]}..{e["end"]}')
for i in before:
    if i not in after: changes.append(f'  - {i} (gone from overrides.json)')
print(f'upcoming ({len(upcoming)}): ' + ', '.join(f'{e["id"]} {e["start"]}' for e in upcoming))
print('changes vs events.json:' if changes else 'no date/link changes; only `now`/`synced` move to ' + A.today)
for c in changes: print(c)
if A.check:
    sys.exit(0)
json.dump(new, open(EVENTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(EVENTS, 'a').write('\n')
print(f'wrote {os.path.relpath(EVENTS)}; next: python3 build/build.py, preview, push')
