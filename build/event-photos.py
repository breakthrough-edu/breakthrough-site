#!/usr/bin/env python3
"""After every event its photos reach the site: the owner picks them on a picker page, this script puts his picks in.
Process map (when, who): the vault's Event-Prep-System-Process-Map,「活动之后: 照片上官网」. How to run: build/README.md.

  pick  writes a picker page folder (every photo of the event, none left out: the owner picks every photo himself):
        index.html, app.js, data.js and img/<id>.jpg, published as a claude.ai artifact; plus a manifest next to the
        folder that maps each photo id to its original in the Drive asset library.
  add   takes the ids he picked, makes the site's JPEGs from the originals, adds them to build/records.json.
        Then run build/build.py, look, push.

Targets: `live` / `build-day` add to the pooled photo page (each photo carries `cap`, the edition); any other key is a
record of its own (/log/<key>/), created on first `add` from `--like` (a record of the same line, e.g. the previous
2BI cohort) with its edition and dates; its first photo is the lead.
"""
import argparse, csv, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
REC_JSON = os.path.join(HERE, 'records.json')
REC_DIR = os.path.join(SITE, 'assets', 'rec')
LIB = os.path.expanduser(os.environ.get('BT_ASSETS', '~/Documents/Breakthrough-Assets'))
POOLED = ('live', 'build-day')
LEAD, REST, Q = 1600, 960, 78     # long side of a record's lead photo / every other photo, JPEG quality (records.json _readme)
THUMB = 560


def load(path):
    """An original, upright (EXIF) and RGB; HEIC goes through sips first."""
    from PIL import Image, ImageOps
    if path.lower().endswith('.heic'):
        out = os.path.join(tempfile.mkdtemp(), 'x.jpg')
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '92', path, '--out', out],
                       capture_output=True, check=True)
        path = out
    return ImageOps.exif_transpose(Image.open(path)).convert('RGB')


def rows(folder):
    """The photo index of one photos/ folder (_index.tsv, made by breakthrough-photo-index)."""
    tsv = os.path.join(folder, '_index.tsv')
    if not os.path.exists(tsv):
        sys.exit(f'{tsv} is missing: index the folder first (breakthrough-photo-index)')
    with open(tsv, encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def cmd_pick(a):
    from concurrent.futures import ThreadPoolExecutor
    items, manifest = [], {}
    for folder in a.folders:
        folder = os.path.realpath(os.path.expanduser(folder))
        rel = os.path.relpath(folder, os.path.realpath(LIB))
        if rel.startswith('..'):
            sys.exit(f'{folder} is not inside the asset library ({LIB})')
        tag = os.path.basename(folder) if len(a.folders) > 1 else ''
        for r in rows(folder):
            pid = (tag + '-' if tag else '') + os.path.splitext(os.path.basename(r['file']))[0]
            manifest[pid] = dict(orig=f"{rel}/{r['file']}", shot=r['shot'])
            items.append(dict(id=pid, grp=tag, shot=r['shot'], hero=r.get('quality') == 'hero',
                              note=r['content'][:70], path=os.path.join(folder, r['file'])))

    out = os.path.abspath(os.path.expanduser(re.sub(r'\.html$', '', a.out.rstrip('/'))))
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    for f in os.listdir(img):                      # a re-run replaces the old thumbnails, nothing else in the folder
        if f.endswith('.jpg'):
            os.remove(os.path.join(img, f))

    def thumb(it):
        im = load(it.pop('path'))
        im.thumbnail((THUMB, THUMB))
        src = 'img/' + re.sub(r'[^A-Za-z0-9_-]', '_', it['id']) + '.jpg'
        im.save(os.path.join(out, src), 'JPEG', quality=70, optimize=True)
        it.update(w=im.width, h=im.height, src=src)
        return it

    with ThreadPoolExecutor(8) as ex:
        items = list(ex.map(thumb, items))
    srcs = [it['src'] for it in items]
    if len(set(srcs)) != len(srcs):
        sys.exit('two photo ids make the same file name under img/; rename one of the originals')
    # The page is published as a claude.ai artifact (publish_files, the whole folder): one file per photo plus small
    # scripts. A single HTML with every photo inlined as base64 never ran there (2026-11-10, Live 06).
    with open(os.path.join(HERE, 'picker.tpl.html'), encoding='utf-8') as f:
        page = f.read()
    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page.replace('__TITLE__', a.name))
    with open(os.path.join(HERE, 'picker.app.js'), encoding='utf-8') as f:
        app = f.read()
    with open(os.path.join(out, 'app.js'), 'w', encoding='utf-8') as f:
        f.write(app)
    data = dict(key=a.target, title=a.title, want=a.want, items=items)
    with open(os.path.join(out, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.PICKER_DATA=' + json.dumps(data, ensure_ascii=False) + ';\n')
    with open(out + '.manifest.json', 'w', encoding='utf-8') as f:
        json.dump(dict(target=a.target, cap=a.cap, photos=manifest), f, ensure_ascii=False, indent=1)
    kb = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs) // 1024
    print(f'{out}/: index.html, app.js, data.js, img/ ({len(items)} photos), {kb} KB in all')
    print(f'{out}.manifest.json')
    print('Next: publish the folder as an artifact (claude-artifacts publish_files: index.html, app.js, data.js and every '
          'img/<id>.jpg, each "as" its own path), then declare_capabilities {db:{}, user:{}}.')


def cmd_add(a):
    with open(REC_JSON, encoding='utf-8') as f:
        rec = json.load(f)
    with open(a.manifest, encoding='utf-8') as f:
        man = json.load(f)
    target, photos = man['target'], man['photos']
    ids = [i for i in a.ids.split(',') if i]
    missing = [i for i in ids if i not in photos]
    if missing:
        sys.exit(f'not in the manifest: {missing}')
    if len(set(ids)) != len(ids):
        sys.exit('an id is picked twice')

    if target in POOLED:
        coll = next(c for c in rec['collections'] if c['key'] == target)
        lst, cap = coll['photos'], man.get('cap') or sys.exit('a pooled page needs --cap at pick time (e.g. "Vol 05")')
        done = {p['orig'] for p in lst}
        nums = [int(m.group(1)) for p in lst if (m := re.match(rf'{target}-(\d+)\.jpg$', p['src']))]
        names = [f'{target}-{n:02d}.jpg' for n in range(max(nums, default=0) + 1, max(nums, default=0) + 1 + len(ids))]
        sizes = [REST] * len(ids)
    else:
        r = next((x for x in rec['records'] if x['key'] == target), None)
        if r is None:
            like = next((x for x in rec['records'] if x['key'] == a.like), None)
            if not (like and a.edition and a.start and a.end):
                sys.exit(f'{target} is a new record: give --like <existing key> --edition --start --end')
            r = {k: like[k] for k in ('line', 'lockup', 'name', 'stamp', 'copy') if k in like}
            r = dict(key=target, **r)
            r.update(edition=a.edition, start=a.start, end=a.end, photos=[])
            rec['records'].insert(0, r)
        lst, cap, done = r['photos'], None, {p['orig'] for p in r['photos']}
        if a.lead:
            if a.lead not in ids:
                sys.exit('--lead must be one of the picked ids')
            ids.remove(a.lead)
            ids.insert(0, a.lead)
        start = len(lst)
        names = [f'{target}-lead.jpg' if start + n == 0 else f'{target}-{start + n:02d}.jpg' for n in range(len(ids))]
        sizes = [LEAD if start + n == 0 else REST for n in range(len(ids))]

    again = [i for i in ids if photos[i]['orig'] in done]
    if again:
        sys.exit(f'already on the page: {again}')
    os.makedirs(REC_DIR, exist_ok=True)
    for pid, name, size in zip(ids, names, sizes):
        dst = os.path.join(REC_DIR, name)
        if os.path.exists(dst):
            sys.exit(f'{dst} exists; nothing is overwritten')
        im = load(os.path.join(LIB, photos[pid]['orig']))
        im.thumbnail((size, size))
        im.save(dst, 'JPEG', quality=Q, optimize=True, progressive=True)
        p = dict(src=name, w=im.width, h=im.height, orig=photos[pid]['orig'])
        if cap:
            p['cap'] = cap
        if photos[pid]['shot'] == 'group-photo':
            p['group'] = True
        lst.append(p)
        print(name, im.width, im.height, photos[pid]['orig'])
    with open(REC_JSON, 'w', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, indent=1) + '\n')
    print(f'{target}: +{len(ids)} photos, {len(lst)} on the page. Next: python3 build/build.py')


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest='cmd', required=True)
p = sub.add_parser('pick', help='write the picker page for one event')
p.add_argument('target', help='live | build-day | a record key such as 2bi-cohort-03')
p.add_argument('folders', nargs='+', help="the event's photos/ folder(s) in the asset library, each with an _index.tsv")
p.add_argument('--title', required=True, help='heading on the picker page, e.g. "Build Day No. 04"')
p.add_argument('--name', required=True, help='the page\'s name in the gallery, e.g. "Build Day 04 挑图"')
p.add_argument('--cap', help='edition label for a pooled page, e.g. "Vol 05" / "No. 04"')
p.add_argument('--want', type=int, required=True, help='suggested number to pick (the owner decides)')
p.add_argument('--out', required=True, help='the picker page folder, e.g. <event>/picker (a trailing .html is dropped); '
               'its manifest <folder>.manifest.json is written beside it')
p = sub.add_parser('add', help="put the owner's picks into records.json and assets/rec/")
p.add_argument('manifest', help='the .manifest.json written by pick')
p.add_argument('--ids', required=True, help='picked ids, comma-separated, in the order they should appear')
p.add_argument('--lead', help="a new record's lead photo (default: the first id)")
p.add_argument('--like', help='a new record copies line / lockup / name / stamp / copy from this record')
p.add_argument('--edition')
p.add_argument('--start')
p.add_argument('--end')
a = ap.parse_args()
cmd_pick(a) if a.cmd == 'pick' else cmd_add(a)
