#!/usr/bin/env python3
"""Rebuild the site from build/index.tpl.html: the homepage (index.html) and the build log pages
(log/, log/<key>/, roundtable/; their content is build/records.json).

Run from the site root:   python3 build/build.py
Photos live in assets/img/ and logos in assets/logos/ as plain files; the page references them by
relative path (no base64). Rebuilding rewrites index.html and upcoming.json (the events feed the Student Portal reads,
printed from the same table as the section 02 sheets and checked against them). A photo already present in assets/img/
is left exactly as it is, so swapping a photo = overwrite the file with the same name, no rebuild needed.
A photo that is missing from assets/img/ is made from the original under SOURCE (resized + JPEG-compressed
with the parameters below). `--refresh-photos` remakes every photo from SOURCE.
"""
import argparse, html, io, os, re, shutil, sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
IMG = os.path.join(SITE, 'assets', 'img')
LOGOS = os.path.join(SITE, 'assets', 'logos')
OUT = os.path.join(SITE, 'index.html')
TPL = os.path.join(HERE, 'index.tpl.html')
# Originals (full-size photos, the seven lockup vectors, the wordmark). Only read when a file under assets/
# is missing or --refresh-photos is given; a checkout without this folder still rebuilds index.html.
_DRIVE = os.path.expanduser('~/Documents/Breakthrough-Assets/Breakthrough-EDU/website/homepage-design-2026-09-06/assets')
SOURCE = os.environ.get('BT_SOURCE', _DRIVE)   # the design folder in the Drive asset library holds every original
CAP = 160 * 1024          # every photo at or under 160KB as a JPEG
QUALITIES = (80, 76, 72, 68, 64, 60, 55, 50)   # tried in order until the file fits under CAP

# ---------------- photos: output name in assets/img -> (original under SOURCE, target width in px) ----------------
# JW picked these on 2026-09-06 (photo-picker artifact); originals are in the Drive asset library, see build/README.md.
PHOTOS = {
    'live-grouphoto.jpg':  ('grouphoto.jpg', 1000),
    'live-stage.jpg':      ('20260703_Breakthrough Live_316_talk.jpg', 720),
    'live-audience.jpg':   ('20260703_Breakthrough Live_113_audience.jpg', 720),
    '2bi-room.jpg':        ('DSC03599.jpg', 1000),
    '2bi-huddle.jpg':      ('DSC03737.jpg', 720),
    '2bi-pair.jpg':        ('rows/2bi-3.jpg', 720),
    'buildday-front.jpg':  ('DSCF8211.JPG', 1000),
    'buildday-board.jpg':  ('DSCF8123.JPG', 720),
    'buildday-banner.jpg': ('DSCF8220.JPG', 720),
    'bsbb-room.jpg':       ('DSC08837.jpg', 1000),
    'bsbb-flipchart.jpg':  ('DSC08884.jpg', 720),
    'bsbb-marker.jpg':     ('DSC08955.jpg', 720),
}
# ---------------- logos: the seven product lockups (<slug>-ink.svg), the wordmark bitmap, the favicon ----------------
SLUGS = ('breakthrough-live', '2nd-brain-intensive', 'breakthrough-build-day', 'breakthrough-circle',
         'brand-strategy-breakthrough', 'brand-launch-off-challenge', 'breakthrough-roundtable')
WORDMARK = 'wordmark.png'
FAVICON = 'b-mark.svg'

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--refresh-photos', action='store_true', help='remake every photo in assets/img/ from SOURCE')
ap.add_argument('--source', default=SOURCE, help=f'folder holding the originals (default: {SOURCE})')
ARGS = ap.parse_args()
SOURCE = ARGS.source


def need_source(what):
    if not os.path.isdir(SOURCE):
        sys.exit(f'{what} is missing under assets/ and the originals folder is not here: {SOURCE}\n'
                 f'  put the file in place, or point --source / BT_SOURCE at the originals.')


def make_photo(name, src, width):
    """Resize the original to `width` (never upscale) and save a progressive JPEG under CAP, trying QUALITIES in order."""
    from PIL import Image, ImageOps
    need_source(f'assets/img/{name}')
    im = ImageOps.exif_transpose(Image.open(os.path.join(SOURCE, src))).convert('RGB')
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    for q in QUALITIES:
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=q, optimize=True, progressive=True)
        if buf.tell() <= CAP:
            break
    assert buf.tell() <= CAP, (name, buf.tell())
    os.makedirs(IMG, exist_ok=True)
    with open(os.path.join(IMG, name), 'wb') as f:
        f.write(buf.getvalue())
    print(f'  made  {name:20s} {im.width}x{im.height} q{q} {buf.tell()/1024:.0f} KB  (from {src})')


def photo(name):
    """Path + pixel size of a photo in assets/img/, making it from the original only if it is not there yet."""
    from PIL import Image
    path = os.path.join(IMG, name)
    if ARGS.refresh_photos or not os.path.exists(path):
        src, width = PHOTOS[name]
        make_photo(name, src, width)
    else:
        print(f'  kept  {name:20s} {os.path.getsize(path)/1024:.0f} KB')
    with Image.open(path) as im:
        w, h = im.size          # reported for the build log; the page's CSS owns the box, so no width/height attributes are written
    return f'assets/img/{name}', w, h


def logo(file):
    """Path of a file in assets/logos/, copied from the originals only if it is not there yet."""
    path = os.path.join(LOGOS, file)
    if not os.path.exists(path):
        need_source(f'assets/logos/{file}')
        src = os.path.join(SOURCE, 'logos', file) if file.endswith('-ink.svg') else os.path.join(SOURCE, file)
        os.makedirs(LOGOS, exist_ok=True)
        shutil.copyfile(src, path)
        print(f'  copied assets/logos/{file}')
    return f'assets/logos/{file}'


def svg_uri(svg):
    svg = re.sub(r'\s+', ' ', svg.strip())
    return 'data:image/svg+xml,' + quote(svg, safe="=:/ '(),.-")


LK = {}       # slug -> (x, y, w, h); the one <image> per lockup lives in the page's defs, every use of it is a <use>
LKDEFS = []
ROOT = ''     # the way from the page being written back to the site root: '' on the homepage, '../' in /log/, '../../' in /log/<key>/


def begin(root):
    """Start a new page: its own path back to the root, and its own (empty) set of lockups in the defs."""
    global ROOT
    ROOT = root
    LK.clear()
    LKDEFS.clear()


def reg(slug):
    """Register a lockup once: the untouched ink vector as one <image id="lk-<slug>"> in the shared defs, referenced
    by path. A row and a card that show the same product both <use> this one image."""
    if slug in LK:
        return LK[slug]
    href = logo(f'{slug}-ink.svg')
    raw = open(os.path.join(SITE, href), 'rb').read()
    vb = re.search(rb'viewBox="([^"]+)"', raw).group(1).decode().split()
    x, y, w, h = map(float, vb)
    LKDEFS.append(f'<image id="lk-{slug}" href="{ROOT}{href}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"/>')
    LK[slug] = (x, y, w, h)
    return LK[slug]


def card_lockup(slug, name, edition):
    """The lockup printed on the lower piece of a sheet: static, no mask, no motion of its own.
    A visually hidden text title stays for readers and screen readers. (The edition is on the stub's serial, see stub().)"""
    x, y, w, h = reg(slug)
    return (f'<h3><svg class="lkc" viewBox="{x:g} {y:g} {w:g} {h:g}" aria-hidden="true" focusable="false"><use href="#lk-{slug}"/></svg>'
            f'<span class="sr">{name}</span></h3>')


def lockup(slug, name, lw=1):
    """The product lockup (ink version) as a <use> of the shared image inside an inline svg that carries its own brush mask.
    The vector file is referenced untouched, shapes never edited. The mask is only attached by the motion layer."""
    x, y, w, h = reg(slug)
    n = 4
    band = h / n
    sw = band * 1.3
    paths = []
    for i in range(n):
        cy = y + band * (i + .5)
        paths.append(f'<path class="lk-stroke" pathLength="1" d="M {x - w*.12:.1f} {cy + h*.025:.1f} L {x + w*1.12:.1f} {cy - h*.025:.1f}"/>')
    mid = f'lk-m-{slug}'
    style = f' style="--lw:{lw}"' if lw != 1 else ''
    return (f'<h3><svg class="lk"{style} viewBox="{x:g} {y:g} {w:g} {h:g}" aria-hidden="true" focusable="false">'
            f'<defs><mask id="{mid}" maskUnits="userSpaceOnUse" x="{x - w:.0f}" y="{y - h:.0f}" width="{3*w:.0f}" height="{3*h:.0f}">'
            f'<g fill="none" stroke="#fff" stroke-width="{sw:.1f}" stroke-linecap="round" filter="url(#lk-bristle)">{"".join(paths)}</g></mask></defs>'
            f'<g class="lk-paint" data-mask="url(#{mid})"><use href="#lk-{slug}"/></g>'
            f'</svg><span class="sr">{name}</span></h3>')


# highlighter: one clean solid orange block. Hard edges, each end a hair off square (about 0.7 degree of lean), no bristles, no black.
HL = svg_uri("""
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 60' preserveAspectRatio='none'>
<polygon points='1,5 400,0 398,55 0,60' fill='#FF6600'/>
</svg>""")

# grit mask for rubber stamps
GRIT = svg_uri("""
<svg xmlns='http://www.w3.org/2000/svg' width='200' height='80'>
<filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='2' seed='11'/>
<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 3.6 -0.95'/></filter>
<rect width='200' height='80' filter='url(#g)'/>
</svg>""")

# ---------------- dates: everything dated on the page comes from build/events.json (see its _readme) ----------------
import datetime, json
EV = json.load(open(os.path.join(HERE, 'events.json'), encoding='utf-8'))
NOW = EV['now']
UPCOMING = [e for e in EV['upcoming'] if e['end'] >= NOW]          # still ahead of the cursor
NEXT = {}                                                          # kind -> its next occurrence
for e in UPCOMING:
    NEXT.setdefault(e['kind'], e)
for k in ('live', 'buildday', 'intensive'):
    assert k in NEXT, f'events.json has no upcoming {k}: run build/sync-events.py (or the event has no brief yet)'
# 一个月两场 Live 之后 (decision 2026-09-20), section 02 要能印第二场; 没有第二场时第四格自己消失。
LIVE2 = next((e for e in UPCOMING if e['kind'] == 'live' and e is not NEXT['live']), None)
WD = ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')


def d(iso):
    return datetime.date.fromisoformat(iso)


def zh_date(e):
    """9月11日  /  9月26至27日  (same month) /  9月30日至10月1日"""
    a, b = d(e['start']), d(e['end'])
    if a == b: return f'{a.month}月{a.day}日'
    if a.month == b.month: return f'{a.month}月{a.day}至{b.day}日'
    return f'{a.month}月{a.day}日至{b.month}月{b.day}日'


def sheet_date(e):
    """9月11日 · FRI · 8:00 PM  /  9月26至27日 · SAT + SUN"""
    a, b = d(e['start']), d(e['end'])
    days = ' + '.join(WD[(a + datetime.timedelta(i)).weekday()] for i in range((b - a).days + 1))
    return f'{zh_date(e)} · {days}' + (f' · {e["time"]}' if e.get('time') else '')


LOG_LABEL = {'live': lambda e: f'Breakthrough Live · {e["edition"].replace(" ", "")}',
             'buildday': lambda e: f'Build Day {e["edition"].split()[-1]}',
             'intensive': lambda e: f'2nd Brain Intensive · {e["edition"]}'}

# ---------------- the build log (top tape) ----------------
# (status, date, label)  status: x = built, o = scheduled, now = cursor. History is curated in events.json;
# upcoming entries come from the vault briefs via sync-events.py; an upcoming entry already behind `now` shows as built.
ENTRIES = [("x", date, label) for date, label in EV['history']]
ENTRIES += [("x" if e['end'] < NOW else "o", e['start'], LOG_LABEL[e['kind']](e)) for e in EV['upcoming']]
ENTRIES += [("o", date, label) for date, label in EV.get('planned', []) if (date, label) not in {(t[1], t[2]) for t in ENTRIES}]
ENTRIES.sort(key=lambda t: t[1])
ENTRIES.insert(next(i for i, t in enumerate(ENTRIES + [(None, '9999', None)]) if t[1] > NOW), ("now", NOW, "Now"))
_OLD_ENTRIES = [
    ("x", "2024-12-18", "Brand Strategy Breakthrough · Class 01"),
    ("x", "2026-03-19", "Brand Launch Off Challenge · Batch 01 start"),
    ("x", "2026-05-22", "Brand Strategy Breakthrough · Class 10"),
    ("x", "2026-07-03", "Breakthrough Live · Vol01"),
    ("x", "2026-07-25", "Build Day 01"),
    ("x", "2026-08-07", "Breakthrough Live · Vol02"),
    ("x", "2026-08-15", "Build Day 02"),
    ("x", "2026-08-20", "Brand Launch Off Challenge · Batch 01 graduated"),
    ("x", "2026-08-29", "2nd Brain Intensive · Cohort 01"),
    ("now", "2026-09-06", "Now"),
    ("o", "2026-09-11", "Breakthrough Live · Vol03"),
    ("o", "2026-09-19", "Build Day 03"),
    ("o", "2026-09-26", "2nd Brain Intensive · Cohort 02"),
    ("o", "2026-10-02", "Breakthrough Live · Vol04"),
    ("o", "2026-10-17", "Build Day 04"),
    ("o", "2026-10-24", "2nd Brain Intensive · Cohort 03"),
]   # (the hand-typed list the page shipped with on 2026-09-06; kept only as a record of the tape's first entries)


def log_html():
    parts, n = [], 0
    for status, date, label in ENTRIES:
        if status == "now":
            parts.append(f'<span class="e now">▶ {label} {date}</span>')
            continue
        n += 1
        cls = "done" if status == "x" else "todo"
        box = "[x]" if status == "x" else "[&nbsp;]"
        parts.append(f'<span class="e {cls}"><span class="box">{box}</span><span class="d">{n:04d} {date}</span>{label}</span>')
    return "".join(parts)


TAPEBAND = ("<b>Think it.</b><i>//</i><b>Build it.</b><i>//</i><b class='o'>Break through.</b><i>//</i>") * 4

# ---------------- the sheets (section 02): what each kind of event prints, and which events get a sheet ----------------
# One table for every word on a sheet (the stamp, the one line, the go link), so the page and upcoming.json (the feed the
# Student Portal reads, see FEED below) are both printed from it and can never disagree. Dates and editions come from events.json.
SITE_URL = 'https://project-breakthrough.com.my/'   # where GitHub Pages serves this repo; the feed's logo links are absolute
PRODUCT = {   # kind -> (lockup slug, the product's English name, the lockup's hidden title on a sheet)
    'live': ('breakthrough-live', 'Breakthrough Live', lambda e: f'Breakthrough Live {e["edition"].replace(" ", "")}'),
    'buildday': ('breakthrough-build-day', 'Build Day', lambda e: f'Breakthrough Build Day {e["edition"].split()[-1]}'),
    'intensive': ('2nd-brain-intensive', '2nd Brain Intensive', lambda e: f'2nd Brain Intensive {e["edition"]}'),
}
WA_BUILD_DAY = 'https://wa.me/60167226505?text=Hi%20CT%21%20I%27d%20like%20to%20join%20the%20upcoming%20Build%20Day.'
SHEET_COPY = {   # key -> the sheet's stamp, its one line, and its go link (label as printed, href)
    'live': dict(stamp='Free meetup',
                 para='你的生意, 有多少只住在你脑袋里? 来现场, 看 2nd Brain 怎么让 AI 真的帮得上你, 然后当场 build 一颗自己的。',
                 cta='RSVP →', href='https://join.project-breakthrough.com.my/breakthrough-live'),
    # 一个月两场 Live (decision 2026-09-20): 週五晚上那场用上面那句, 週末下午那场用这句 (它的字就是在讲周末下午)。
    'live-weekend': dict(stamp='Free meetup',
                         para='同一个月的第二场, 换成周末下午。一样是现场 build, 走不开平日晚上的就来这一场。',
                         cta='RSVP →', href='https://join.project-breakthrough.com.my/breakthrough-live'),   # 报名页两场同时开放 (decision 2026-09-24), 不再指社群
    'buildday': dict(stamp='Members only',
                     para='带着生意上一个卡住的地方来。一整天, 用 AI 亲手 build 一套解决它的系统; 不是上课, 是做出来。',
                     cta='WHATSAPP US →', href=WA_BUILD_DAY),
    # JW 2026-10-04: 2BI is the two days Included in Breakthrough Circle, no longer a course sold on its own. No「Personal OS → Company OS」, and no「十步」either: a stranger has no context for it.
    'intensive': dict(stamp='Included in Circle',
                      para='你怎么做生意的那套东西, 现在只有你脑袋里有。加入 Breakthrough Circle 先上这两天, 我们一起搭起一个认得你、照你的方法替你做事的 2nd Brain, 之后你回去接着 build, 每个月带着手上在做的东西回来 Build Day。',
                      cta='JOIN →', href='https://join.project-breakthrough.com.my/2nd-brain-intensive'),
}


def copy_key(e):
    """Which SHEET_COPY entry an event prints, or None when the site has no words for it (such an event is left out of the feed)."""
    if e['kind'] == 'live':
        return 'live-weekend' if d(e['start']).weekday() >= 5 else 'live'
    return e['kind'] if e['kind'] in SHEET_COPY else None


# The sheets in page order (Live, the month's second Live when there is one, Build Day, 2BI), each with the tilt of its stamp.
SHEETS = [(NEXT['live'], '-8deg'), *([(LIVE2, '5deg')] if LIVE2 else []), (NEXT['buildday'], '6deg'), (NEXT['intensive'], '-7deg')]
for e, _ in SHEETS:
    assert copy_key(e), f'{e["id"]}: a sheet event needs words in SHEET_COPY'


def entry_index(e):
    """The number this event carries on the build-log tape (0001... counting every entry except the cursor)."""
    n = 0
    for status, date, label in ENTRIES:
        if status == 'now':
            continue
        n += 1
        if date == e['start'] and label == LOG_LABEL[e['kind']](e):
            return n
    raise AssertionError(f'{e["id"]} is not on the tape')


def stub(e):
    """The top piece of a sheet (B3, JW 2026-09-06): orange bar, the edition as a boxed serial that ticks up, and the ruled ledger field
    with the DAY as the biggest thing on the card, month / weekday / time stacked in mono beside it, the tape's entry index ghosted behind."""
    label, num = e['edition'].rsplit(' ', 1)                      # 'Vol 03' -> Vol, 03
    a, b = d(e['start']), d(e['end'])
    days = ' + '.join(WD[(a + datetime.timedelta(i)).weekday()] for i in range((b - a).days + 1))
    if a == b:
        n = f'<div class="n" aria-hidden="true">{a.day}</div>'
    else:
        n = f'<div class="n two" aria-hidden="true"><span>{a.day}<i>至</i></span><span>{b.day}</span></div>'
    col = f'<span class="m">{a.month}月</span><span class="w">{days}</span>' + (f'<span class="t">{e["time"]}</span>' if e.get('time') else '')
    return (f'<div class="stub">\n          <div class="bar"></div>\n'
            f'          <div class="serial"><span><em>{label}</em> <b class="tick" data-v="{num}">{num}</b></span></div>\n'
            f'          <div class="day" aria-label="{sheet_date(e)}">\n'
            f'            <span class="idx" aria-hidden="true">{entry_index(e):04d}</span>\n'
            f'            {n}\n'
            f'            <div class="col" aria-hidden="true">{col}</div>\n'
            f'          </div>\n        </div>')


def sheet_html(e, tilt):
    """One whole sheet: the stamp, the stub, the perforation, and the lower piece (lockup, the one line, the go link), all from
    SHEET_COPY and events.json. Call it after rows_html(), so the lockups are registered in the rows' order."""
    c = SHEET_COPY[copy_key(e)]
    slug, _, title = PRODUCT[e['kind']]
    return (f'      <div class="sheetw"><article class="sheet">\n'
            f'        <div class="stampw" style="--sr:{tilt}"><span class="stamp">{escape(c["stamp"])}</span></div>\n'
            f'        {stub(e)}\n'
            f'        <div class="tear" aria-hidden="true"></div>\n'
            f'        <div class="piece">\n'
            f'          <div class="what">{card_lockup(slug, title(e), e["edition"])}</div>\n'
            f'          <div class="qb">\n'
            f'            <p>{escape(c["para"])}</p>\n'
            f'            <a class="go" href="{escape(c["href"], quote=True)}">{escape(c["cta"])}</a>\n'
            f'          </div>\n'
            f'        </div>\n'
            f'      </article></div>')


def escape(text, quote=False):
    """HTML-escape copy for the page (the feed keeps the plain text); none of today's words need it, so the page is unchanged."""
    return html.escape(text, quote=quote)


# ---------------- the feed (upcoming.json at the site root): the events this site describes, for the Student Portal's Home ----------------
FEED_FILE = os.path.join(SITE, 'upcoming.json')
FEED_SCHEMA = 1


def feed_entry(e):
    """One upcoming event as the Portal reads it. Every value is the one the site prints (or would print on a sheet), taken from
    the same helpers the sheets use."""
    c = SHEET_COPY[copy_key(e)]
    slug, product, _ = PRODUCT[e['kind']]
    label, num = e['edition'].rsplit(' ', 1)
    a, b = d(e['start']), d(e['end'])
    logo_file = os.path.join(LOGOS, f'{slug}-ink.svg')
    assert os.path.exists(logo_file), f'feed logo missing: {logo_file}'
    return {
        'id': e['id'],
        'kind': e['kind'],
        'product': product,
        'edition': e['edition'],
        'editionLabel': label,
        'editionNumber': num,
        'start': e['start'],
        'end': e['end'],
        'days': [str(a.day)] if a == b else [str(a.day), str(b.day)],   # the big day number(s) the stub prints
        'through': '至',                                                 # printed between the two days of a range
        'month': f'{a.month}月',
        'weekdays': ' + '.join(WD[(a + datetime.timedelta(i)).weekday()] for i in range((b - a).days + 1)),
        'time': e.get('time') or None,
        'dateLine': sheet_date(e),
        'stamp': c['stamp'],
        'paragraph': c['para'],
        'cta': {'label': c['cta'], 'href': c['href']},
        'logo': f'{SITE_URL}assets/logos/{slug}-ink.svg',
        'tapeIndex': f'{entry_index(e):04d}',                            # the build-log number ghosted on the stub
        'onSheet': any(e is s for s, _ in SHEETS),
    }


def feed():
    """The feed: every upcoming event (end on or after events.json's `now`) the site has words for, in date order. The sheets
    are the first of them; events past the sheets come after (the Portal filters by the learner's own date and shows at most four)."""
    events = sorted((e for e in UPCOMING if copy_key(e)), key=lambda e: (e['start'], e['end'], e['id']))
    return {'schemaVersion': FEED_SCHEMA, 'generatedAt': None, 'source': SITE_URL, 'events': [feed_entry(e) for e in events]}


DATES = {'{{NCOUNT}}': str(len(SHEETS)),
         '{{NEXTMETA}}': d(min(e['start'] for e in NEXT.values())).strftime('%b %Y'), '{{REV}}': EV['synced']}

# ---------------- the rows (section 03); hidden=True keeps a row in the table but off the page ----------------
# a photo slot: (file in assets/img, aspect, alt, extra style) ; None = paper card PHOTO · TO COME ; ('note', text) = the SKOOL sticker
TAPE_A = '<i class="tape" style="--tr:-6deg;left:-12px;top:-9px"></i><i class="tape" style="--tr:5deg;right:-12px;top:-8px"></i>'
TAPE_B = '<i class="tape" style="--tr:-8deg;left:-10px;top:-8px"></i>'
TAPE_C = '<i class="tape" style="--tr:7deg;right:-10px;top:-8px"></i>'
TAPES = {'a': TAPE_A, 'b': TAPE_B, 'c': TAPE_C}


def slot(letter, spec):
    tape = TAPES[letter]
    if spec is None or spec[0] is None:
        ar = '4/3' if letter == 'a' else '3/2'
        extra = spec[1] if spec else ''
        return f'<figure class="pinw {letter}"{extra}><div class="pin"><div class="ph" style="--ar:{ar}">Photo · to come</div>{tape}</div></figure>'
    if spec[0] == 'note':
        extra = spec[2] if len(spec) > 2 else ''
        return f'<figure class="pinw {letter}"{extra}><div class="pin"><div class="ph note" style="--ar:3/2">{spec[1]}</div>{tape}</div></figure>'
    file, ar, alt, extra = spec
    if file.startswith('assets/'):      # a picture that lives outside assets/img/ (a Roundtable cover): used as it is, never remade
        assert os.path.exists(os.path.join(SITE, file)), f'row picture missing: {file}'
        src = file
    else:
        src, w, h = photo(file)
    # Every photo sits below the fold (section 03), so all of them load lazily. No width/height attributes on purpose:
    # the CSS box is width:100% + aspect-ratio, and a height attribute would become a fixed height that beats the aspect-ratio.
    return (f'<figure class="pinw {letter}"{extra}><div class="pin"><img src="{src}" alt="{alt}" style="--ar:{ar}" loading="lazy">{tape}</div></figure>')


ROWS = [
    dict(id='live', slug='breakthrough-live', name='Breakthrough Live', lw=1,
         pics=[('live-grouphoto.jpg', '4/3', 'Breakthrough Live 大合照, 挑高白墙空间里满场笔电', ''),
               ('live-stage.jpg', '3/2', 'Jia Wei 在 Breakthrough Live 前面讲, 两边屏幕, 满场笔电', ''),
               ('live-audience.jpg', '3/2', 'Breakthrough Live 全场举手', '')],
         para='每个月两场, 免费, 线下。不是讲座, 是一起动手: 先看 Jia Wei 现场跑自己的 2nd Brain, 再全场打开笔电, 一起 build 你自己的。走的时候, 你电脑里已经有一颗。',
         rec=f'Offline · Kaloz EDU, Shah Alam · 每月两场 (週五晚上 · 週六下午) · 下一场 <b>{zh_date(NEXT["live"])}</b>',
         action=('link', 'https://join.project-breakthrough.com.my/breakthrough-live')),
    dict(id='intensive', slug='2nd-brain-intensive', name='2nd Brain Intensive', lw=.84,
         pics=[('2bi-room.jpg', '4/3', '2nd Brain Intensive 课室, 满桌黑 T 恤, Jia Wei 在前面的 Breakthrough 立牌旁', ''),
               ('2bi-huddle.jpg', '3/2', '一桌学员围着一台笔电, 一起 build', ''),
               ('2bi-pair.jpg', '3/2', '两位学员在 2nd Brain Intensive 里一起看一台笔电', '')],
         para='很多老板用了 AI, 觉得它做出来的东西不像自己, 因为你怎么报价、怎么带人、怎么拍板, 全部还在你脑袋里, AI 读不到。这两天从这件事做起, 我们一起把你脑袋里那套做法, 一样一样写进你自己的 2nd Brain, AI 读得到了, 做出来的东西才会像你, 接着让它每天照你的方法替你做事, 公司那一层也搭出第一版。这两天是加入 Breakthrough Circle 之后先上的, 之后你回去在自己的生意里接着 build, 卡住了在会员群里问, 每个月有一天 Build Day, 你带着手上在做的东西回来, 我们继续一起 build。',
         rec=f'Included in Circle · 两天 · 周末 · Kaloz EDU, Shah Alam · 下一届 <b>{zh_date(NEXT["intensive"])}</b>',
         action=('link', 'https://join.project-breakthrough.com.my/2nd-brain-intensive')),
    # JW 2026-09-06: Build Day before Circle.
    dict(id='buildday', slug='breakthrough-build-day', name='Breakthrough Build Day', lw=1,
         pics=[('buildday-front.jpg', '4/3', 'Build Day 现场, Jia Wei 在大屏前, 满桌笔电', ' style="--op:50% 42%"'),
               ('buildday-board.jpg', '3/2', 'Jia Wei 指着屏幕讲一个系统怎么 build', ''),
               ('buildday-banner.jpg', '3/2', 'Jia Wei 在 Breakthrough 立牌旁带 Build Day', ' style="--op:50% 42%"')],
         para='Circle 会员每个月一次的现场。带着生意上一个卡住的地方来, 一整天, 用 AI 亲手 build 一套解决它的系统; 不是上课, 是做出来, 卡住了旁边就有人。',
         rec=f'Offline · Kaloz EDU, Shah Alam · 每月一次 · 下一场 <b>{zh_date(NEXT["buildday"])}</b>',
         # JW 2026-09-06: WhatsApp button instead of the stamp (same link as the sheet in section 02)
         action=('wa', 'https://wa.me/60167226505?text=Hi%20CT%21%20I%27d%20like%20to%20join%20the%20upcoming%20Build%20Day.')),
    # Circle: a tall cluster (one portrait photo, the SKOOL sticker, one blank card), so it does not read as Build Day's wide cluster again
    dict(id='circle', hidden=True,  # JW 2026-09-06: hidden until it has photos
         slug='breakthrough-circle', name='Breakthrough Circle', lw=1,
         pics=[('circle-pair.jpg', '2/3', 'Jia Wei 跟一位 Circle 会员一起看一台笔电', ' style="width:50%"'),
               (None, ' style="width:44%;top:2%"'),
               ('note', 'SKOOL 社群', ' style="width:44%;left:42%;bottom:4%"')],
         para='Breakthrough 那群 builder 平常待的地方。SKOOL + WhatsApp 社群: 有人卡住了, 群里就有人接; 有人做出来了, 全群一起看。Breakthrough 这条路, 没有人是一个人在走。',
         rec='SKOOL + WhatsApp · 会员每月一次 Build Day',
         action=('soon',)),
    dict(id='strategy', slug='brand-strategy-breakthrough', name='Brand Strategy Breakthrough', lw=.84,
         pics=[('bsbb-room.jpg', '4/3', 'Brand Strategy Breakthrough 课室, 学员围桌, 屏上是品牌图', ''),
               ('bsbb-flipchart.jpg', '3/2', 'Jia Wei 在 flipchart 前带 Brand Strategy Breakthrough', ''),
               ('bsbb-marker.jpg', '3/2', 'Jia Wei 在白板上写', ' style="--op:50% 22%"')],
         para='三天, build 你的品牌策略, 用的是我们自己的方法论 Da Vinci Code。从六个 pillar, 把品牌一层一层理清楚: 你的定位是什么, 你跟别人的差异到底在哪里, 客户为什么非选你不可。',
         rec='三天 · Offline · Kaloz EDU, Shah Alam',
         action=('none',)),   # JW 2026-09-06: no button until the BSBB page exists
    dict(id='challenge', hidden=True,  # JW 2026-09-06: hidden until it has photos
         slug='brand-launch-off-challenge', name='Brand Launch Off Challenge', lw=.84,
         pics=[None, None, None],
         para='六个月的 challenge。我们跟你的团队一起, 把你的品牌从 0 build 到 launch, 从策略一路做到打市场; 不是听课, 是每一步真的做出来。',
         rec='六个月 · 带着你的团队一起',
         action=('soon',)),
    # JW 2026-10-06: Roundtable is back as the last row. Its pictures are three episode covers (no photos from the shoots), its button goes to /roundtable/.
    dict(id='roundtable',
         slug='breakthrough-roundtable', name='Breakthrough Roundtable', lw=1,
         pics=[('assets/rt/simon-pang.jpg', '16/9', 'Breakthrough Roundtable 一集的封面: Simon Pang', ''),
               ('assets/rt/siu-chong.jpg', '16/9', 'Breakthrough Roundtable 一集的封面: Siu Chong', ''),
               ('assets/rt/jeff-chin.jpg', '16/9', 'Breakthrough Roundtable 一集的封面: Jeff Chin', '')],
         para='别人的 Breakthrough, 是怎么 build 出来的? 一档访谈节目, 每集请一位真的在做生意的人坐下来, 不讲成功学, 拆他把方法落地的过程: 怎么判断、怎么取舍、踩过什么坑。',
         rec='访谈节目 · 华语为主 · 每集一位嘉宾',
         action=('page', 'roundtable/', '看每一集')),
]


LIVE_ROWS = [r for r in ROWS if not r.get('hidden')]


def rows_html():
    out = []
    for i, r in enumerate(LIVE_ROWS):
        n = i + 1
        flip = ' flip' if n % 2 == 0 else ''
        pics = ''.join(slot(l, s) for l, s in zip('abc', r['pics']))
        rec = f'\n        <div class="rec">{r["rec"]}</div>' if r['rec'] else ''
        kind = r['action'][0]
        if kind == 'link':
            act = f'<a class="btn" href="{r["action"][1]}">了解更多 <span class="ar" aria-hidden="true">→</span></a>'
        elif kind == 'wa':
            act = f'<a class="btn" href="{r["action"][1]}">WhatsApp 我们 <span class="ar" aria-hidden="true">→</span></a>'
        elif kind == 'page':
            act = f'<a class="btn" href="{r["action"][1]}">{r["action"][2]} <span class="ar" aria-hidden="true">→</span></a>'
        elif kind == 'none':
            act = ''
        else:
            act = '<div class="soon"><span class="stamp">Coming soon</span></div>'
        out.append(f'''    <div class="row{flip}" id="{r['id']}">
      <div class="pics">{pics}</div>
      <div class="txt">
        <div class="idx">Row <b>{n:02d}</b> / {len(LIVE_ROWS):02d}</div>
        {lockup(r['slug'], r['name'], r['lw'])}
        <p class="one">{r['para']}</p>{rec}
        {act}
      </div>
    </div>
''')
    return '\n'.join(out)


# ---------------- the build log pages (JW 2026-10-06): what has been built, one place per event ----------------
# Section 03 on the homepage, /log/, one page per record under /log/<key>/, the pooled photo pages of Live and Build Day, and /roundtable/.
# Every word, date and photo on them comes from build/records.json (see its _readme); the look is the x- block at the end of the template's CSS.
REC = json.load(open(os.path.join(HERE, 'records.json'), encoding='utf-8'))
for _r in REC['records']:
    _r.update({k: v for k, v in REC['copy'][_r['copy']].items()})       # a record prints the copy block it names (the 2BI cohorts share one)
RECORDS = sorted(REC['records'], key=lambda r: r['start'], reverse=True)   # newest first, whatever order the file is in
COLLECTIONS = REC['collections']
FEATURED = next(r for r in RECORDS if r['key'] == REC['home']['featured'])
LATEST = next(r for r in RECORDS if r['line'] == REC['home']['latest_line'] and r is not FEATURED)   # a new cohort takes this card by itself
EPISODES = sorted(REC['roundtable']['episodes'], key=lambda e: e['n'], reverse=True)
OGDIR = os.path.join(SITE, 'assets', 'og')


def held(kind):
    """The edition numbers of a recurring event that have already happened, read off events.json (the tape's history + upcoming entries behind `now`)."""
    prefix = {'live': 'Breakthrough Live · Vol', 'buildday': 'Build Day '}[kind]
    nums = [int(label[len(prefix):]) for _, label in EV['history'] if label.startswith(prefix)]
    nums += [int(e['edition'].rsplit(' ', 1)[1]) for e in EV['upcoming'] if e['kind'] == kind and e['end'] < NOW]
    return sorted(set(nums))


for _c in COLLECTIONS:
    _n = held(_c['kind'])
    _c['editions'] = f'{_c["edition_label"]} {_n[0]:02d} to {_n[-1]:02d}'            # Vol 01 to 04: counted, never typed
    for _p in _c['photos']:
        assert int(_p['cap'].rsplit(' ', 1)[1]) in _n, f'{_c["key"]}: {_p["src"]} is captioned {_p["cap"]}, which events.json has not seen happen'


def when(r):
    a, b = d(r['start']), d(r['end'])
    return f'{a.year} · {a.month}月{a.day}日' if a == b else f'{a.year} · {a.month}月{a.day}至{b.day}日'


def x_lockup(slug, label):
    """A lockup on the build log pages: a <use> of the page's one image of it, flat on the paper (no brush mask), with its name for screen readers."""
    x, y, w, h = reg(slug)
    return (f'<svg class="x-lk" viewBox="{x:g} {y:g} {w:g} {h:g}" aria-hidden="true" focusable="false"><use href="#lk-{slug}"/></svg>'
            f'<span class="sr">{escape(label)}</span>')


def pin(img, label, cls='', tapes=1, eager=False, cap=False):
    """One photo pinned to the paper. `label` says whose photo it is; the alt text is that plus 合照 / 现场 (the photos' indexing notes describe
    the people in them and stay out of the page). width/height are the file's own pixels, so the masonry holds its shape before the photo arrives."""
    assert os.path.exists(os.path.join(SITE, 'assets', 'rec', img['src'])), f'photo missing: assets/rec/{img["src"]}'
    t = '<i class="tape" style="--tr:-6deg;left:-12px;top:-9px"></i>'
    if tapes > 1: t += '<i class="tape" style="--tr:5deg;right:-12px;top:-8px"></i>'
    if tapes == 0: t = ''
    alt = f'{label} {img["cap"]}' if img.get('cap') else label
    alt += ' 合照' if img.get('group') else ' 现场'
    lazy = '' if eager else ' loading="lazy"'
    fc = f'<figcaption>{escape(img["cap"])}</figcaption>' if cap and img.get('cap') else ''
    return (f'<figure class="x-pin {cls}"><img src="{ROOT}assets/rec/{img["src"]}" width="{img["w"]}" height="{img["h"]}" alt="{escape(alt, quote=True)}"{lazy}>{t}{fc}</figure>')


def rec_label(r):
    return f'{r["name"]} {r["edition"]}'


def datebox(r):
    a, b = d(r['start']), d(r['end'])
    if a != b:
        n = f'<b class="two"><span>{a.day}<i>至</i></span><span>{b.day}</span></b>'
        wd = f'{WD[a.weekday()]} + {WD[b.weekday()]}'
    else:
        n, wd = f'<b>{a.day}</b>', WD[a.weekday()]
    return f'<div class="x-date" aria-label="{when(r)}">{n}<span aria-hidden="true">{a.month}月<br>{a.year}<br>{wd}</span></div>'


def stamp(text, tilt):
    return f'<div class="stampw" style="--sr:{tilt}"><span class="stamp">{escape(text)}</span></div>'


# ---- the homepage's section 03: one wide card (named by hand in records.json, for the kind of event that does not come round every month,
#      so later editions cannot push it off), then three equal cards: the newest 2BI cohort, Live, Build Day. Lockup first, then the photo. ----
def built_card(r, feat=False):
    lead = r['photos'][0]
    head = f'<h3>{x_lockup(r["lockup"], r["name"])}</h3><span class="x-ed">{escape(r["edition"])}</span>'
    foot = f'<span class="x-foot"><span class="x-when">{when(r)}</span><span class="x-go">看这一场 →</span></span>'
    href = f'{ROOT}log/{r["key"]}/'
    if feat:
        return (f'<a class="x-bc x-feat" href="{href}">{stamp(r["stamp"], "-7deg")}<span class="x-ft">{head}<p>{escape(r["text"])}</p>{foot}</span>'
                f'{pin(lead, rec_label(r), tapes=2)}</a>')
    return f'<a class="x-bc" href="{href}">{stamp(r["stamp"], "-7deg")}{head}{pin(lead, rec_label(r))}{foot}</a>'


def col_card(c, tilt, tapes=1, text=False):
    """Live / Build Day as a card: on the homepage (no words), and on top of /log/ (two tapes, the short line)."""
    imgs = c['photos']
    p = f'<p>{escape(c["text"])}</p>' if text else ''
    return (f'<a class="x-bc" href="{ROOT}log/{c["key"]}/">{stamp("Every month", tilt)}'
            f'<h3>{x_lockup(c["lockup"], c["name"])}</h3><span class="x-ed">{escape(c["editions"])}</span>'
            f'{pin(imgs[0], c["name"], tapes=tapes)}{p}<span class="x-foot"><span class="x-when"><b>{len(imgs)}</b> photos</span><span class="x-go">看全部照片 →</span></span></a>')


def built_html():
    cards = built_card(FEATURED, True) + built_card(LATEST) + ''.join(col_card(c, '6deg') for c in COLLECTIONS)
    return f"""  <!-- 03 · what's already been built -->
  <section class="sec wrap" id="built">
    <div class="sh">
      <span class="n">03</span>
      <h2 class="h2" lang="en"><span class="l"><span>What's already</span></span><span class="l"><span>been built.</span></span></h2>
      <span class="meta">From the <b>build log</b></span>
    </div>
    <div class="x-built">{cards}</div>
    <div class="x-more"><a class="btn" href="{ROOT}log/">看整条 build log <span class="ar" aria-hidden="true">→</span></a></div>
  </section>
"""


def story(paras):
    return '<div class="x-story">' + ''.join(f'<p>{escape(t)}</p>' for t in paras) + '<span class="x-sign">Jia Wei</span></div>'


def main(inner):
    return f'<main class="paper x-page"><section class="sec wrap">\n{inner}\n</section></main>\n'


# ---- /log/: Live and Build Day as two cards on top, then every record by date, with the dated lines that have no page of their own ----
def log_page():
    def entry(r):
        imgs = r['photos']
        ct = f'<b>{len(imgs)}</b> photos' + (' · <b>1</b> film' if r.get('film') else '')
        fs = stamp('Milestone', '-6deg') if r.get('milestone') else ''
        return (f'<li class="x-en" data-line="{r["line"]}"{" data-feat" if r.get("milestone") else ""}><a href="{ROOT}log/{r["key"]}/">{fs}{datebox(r)}'
                f'<div class="x-what"><h3>{x_lockup(r["lockup"], r["name"])}</h3><strong>{escape(r["edition"])}</strong><p>{escape(r["text"])}</p>'
                f'<span class="x-ct">{ct} · 看这一场 →</span></div>{pin(imgs[0], rec_label(r))}</a></li>')
    plain = lambda date, line, name: f'<li class="x-en plain" data-line="{line}"><div><span>[x]</span><span>{date}</span><span>{escape(name)}</span></div></li>'
    items = [(r['start'], entry(r)) for r in RECORDS] + [(date, plain(date, line, name)) for date, line, name in REC['plain']]
    items.sort(key=lambda t: t[0], reverse=True)
    rows, year = '', None
    for date, h in items:
        if date[:4] != year:
            year = date[:4]
            rows += f'<li class="x-year" aria-hidden="true">{year}</li>'
        rows += h
    chips = ('<button class="x-chip" type="button" data-f="all" aria-pressed="true">全部</button>'
             + ''.join(f'<button class="x-chip" type="button" data-f="{k}" aria-pressed="false">{escape(v)}</button>' for k, v in REC['lines'].items())
             + '<button class="x-chip" type="button" data-f="feat" aria-pressed="false">Milestones</button>')
    band = f'<div class="x-band"><div class="x-built x-two">{"".join(col_card(c, "-6deg", tapes=2, text=True) for c in COLLECTIONS)}</div></div>'
    return main(f'''  <a class="x-back" href="{ROOT}#built">← 回首页</a>
  <div class="sh"><span class="n">Log</span><h1 class="h2" lang="en">Build log.</h1><span class="meta"><b>{len(items)}</b> entries · since {min(t[0] for t in items)[:4]}</span></div>
  <p class="x-lede">{escape(REC['log']['lede'])}</p>
  {band}
  <div class="x-sub x-sub2"><span class="x-k">By date</span></div>
  <div class="x-chips" role="group" aria-label="按产品线看">{chips}</div>
  <ol class="x-log">{rows}</ol>''')


# the filter on /log/: a chip shows its line (or the milestones), and a year with nothing left under it hides too. Without JS every entry simply shows.
LOG_JS = '''<script>
(function(){
  var chips=[].slice.call(document.querySelectorAll('.x-chip'));
  chips.forEach(function(c){c.addEventListener('click',function(){
    var f=c.getAttribute('data-f');
    chips.forEach(function(o){o.setAttribute('aria-pressed',o===c)});
    [].forEach.call(document.querySelectorAll('.x-en'),function(e){e.hidden=f==='feat'?!e.hasAttribute('data-feat'):(f!=='all'&&e.getAttribute('data-line')!==f)});
    [].forEach.call(document.querySelectorAll('.x-year'),function(y){var n=y.nextElementSibling,any=false;while(n&&!n.classList.contains('x-year')){if(!n.hidden)any=true;n=n.nextElementSibling}y.hidden=!any});
  })});
})();
</script>
'''


# ---- /log/<key>/: one record. The lead photo, the story in the founder's words, the film when there is one, then every photo. ----
def record_page(r):
    imgs = r['photos']
    lead, rest = imgs[0], imgs[1:]
    same = [x for x in RECORDS if x['line'] == r['line']]
    j = same.index(r)
    newer = same[j - 1] if j > 0 else None
    older = same[j + 1] if j + 1 < len(same) else None
    film = ''
    if r.get('film'):
        f = r['film']['file']
        for ext in ('mp4', 'jpg'):
            assert os.path.exists(os.path.join(SITE, 'assets', 'film', f'{f}.{ext}')), f'film file missing: assets/film/{f}.{ext}'
        film = (f'<div class="x-film"><video controls playsinline preload="none" poster="{ROOT}assets/film/{f}.jpg" aria-label="{escape(rec_label(r), quote=True)} highlight">'
                f'<source src="{ROOT}assets/film/{f}.mp4" type="video/mp4"></video>'
                f'<div><span class="x-k">Film · {r["film"]["duration"]}</span><h2>The highlight.</h2><p>这一场剪成的一支短片。</p></div></div>')
    fields = (f'<div><dt>Date</dt><dd>{when(r)}</dd></div><div><dt>Line</dt><dd>{escape(r["name"])}</dd></div>'
              f'<div><dt>Where</dt><dd>{escape(REC["where"])}</dd></div><div><dt>Record</dt><dd><b>{len(imgs)}</b> photos{" · 1 film" if r.get("film") else ""}</dd></div>')
    pn = ((f'<a href="{ROOT}log/{older["key"]}/">← {escape(older["edition"])}</a>' if older else '<span></span>')
          + f'<a href="{ROOT}log/">整条 build log</a>'
          + (f'<a href="{ROOT}log/{newer["key"]}/">{escape(newer["edition"])} →</a>' if newer else '<span></span>'))
    return main(f'''  <a class="x-back" href="{ROOT}log/">← Build log</a>
  <header class="x-rh">{stamp(r['stamp'], '-7deg')}{datebox(r)}
    <div class="x-rt"><div class="x-rlk">{x_lockup(r['lockup'], r['name'])}</div><h1>{escape(r['edition'])}</h1></div></header>
  <dl class="x-fields">{fields}</dl>
  {pin(lead, rec_label(r), 'x-lead', tapes=2, eager=True)}
  {story(r['long'])}
  {film}
  <div class="x-grid">{''.join(pin(m, rec_label(r), tapes=0) for m in rest)}</div>
  <nav class="x-pn" aria-label="其他记录">{pn}</nav>''')


# ---- /log/live/ and /log/build-day/: every edition's photos on one page, each photo captioned with the edition it is from ----
def collection_page(c):
    imgs = c['photos']
    lead, rest = imgs[0], imgs[1:]
    fields = (f'<div><dt>Since</dt><dd>{escape(c["since"])}</dd></div><div><dt>Editions</dt><dd>{escape(c["editions"])}</dd></div>'
              f'<div><dt>Where</dt><dd>{escape(REC["where"])}</dd></div><div><dt>Record</dt><dd><b>{len(imgs)}</b> photos</dd></div>')
    return main(f'''  <a class="x-back" href="{ROOT}log/">← Build log</a>
  <header class="x-rh x-rhc">{stamp('Every month', '-7deg')}
    <div class="x-rt"><div class="x-rlk">{x_lockup(c['lockup'], c['name'])}</div><h1 lang="en">{escape(c['h1'])}</h1></div></header>
  <dl class="x-fields">{fields}</dl>
  {pin(lead, c['name'], 'x-lead', tapes=2, eager=True)}
  {story(c['long'])}
  <div class="x-grid">{''.join(pin(m, c['name'], tapes=0, cap=True) for m in rest)}</div>
  <nav class="x-pn" aria-label="其他记录"><span></span><a href="{ROOT}log/">整条 build log</a><span></span></nav>''')


# ---- /roundtable/: the published episodes, each cover a link to its episode on YouTube, and one subscribe button. No photos from the shoots. ----
def roundtable_page():
    rt = REC['roundtable']
    eps = ''
    for e in EPISODES:
        assert os.path.exists(os.path.join(SITE, 'assets', 'rt', f'{e["file"]}.jpg')), f'cover missing: assets/rt/{e["file"]}.jpg'
        alt = escape(f'Breakthrough Roundtable EP{e["n"]}, {e["guest"]}', quote=True)
        eps += (f'<a class="x-ep" href="https://www.youtube.com/watch?v={e["video"]}" target="_blank" rel="noopener">'
                f'<figure class="x-pin "><img src="{ROOT}assets/rt/{e["file"]}.jpg" width="1280" height="720" alt="{alt}" loading="lazy">'
                f'<i class="tape" style="--tr:-6deg;left:-12px;top:-9px"></i></figure>'
                f'<span>EP {e["n"]:02d} · 在 YouTube 看 →</span><b>{escape(e["guest"])}</b></a>')
    return main(f'''  <a class="x-back" href="{ROOT}#built">← 回首页</a>
  <div class="sh"><span class="n">Show</span><h1 class="x-rtlk">{x_lockup('breakthrough-roundtable', 'Breakthrough Roundtable')}</h1><span class="meta">Season <b>{rt['season']}</b> · {len(EPISODES)} episodes</span></div>
  <p class="x-lede">{escape(rt['lede'])}</p>
  <div class="x-eps">{eps}</div>
  <div class="x-more"><a class="btn" href="{rt['channel']}" target="_blank" rel="noopener">去 YouTube 订阅 <span class="ar" aria-hidden="true">→</span></a></div>''')


def og_image(name, source, focus=.5):
    """The share picture of a page (assets/og/<name>.jpg, 1200x630), cut from one of the page's own pictures; made only when it is not there yet.
    `focus` is where the cut sits between the top (0) and the bottom (1) of the source."""
    path = os.path.join(OGDIR, f'{name}.jpg')
    if ARGS.refresh_photos or not os.path.exists(path):
        from PIL import Image
        im = Image.open(os.path.join(SITE, source)).convert('RGB')
        s = max(1200 / im.width, 630 / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        left, top = (im.width - 1200) // 2, round((im.height - 630) * focus)
        os.makedirs(OGDIR, exist_ok=True)
        im.crop((left, top, left + 1200, top + 630)).save(path, 'JPEG', quality=80, optimize=True, progressive=True)
        print(f'  made  assets/og/{name}.jpg  (from {source})')
    return f'{SITE_URL}assets/og/{name}.jpg'


NOTE = """<!--
DESIGN NOTE · MIX-BLACK V6 (two client comments, 2026-09-06)
1 Everything v5 settled stays. V6 does two things: Circle and Build Day become two rows, and the three sheets carry the product lockups instead of typed titles.
2 On a sheet the lockup sits where the title was, under the date: 66% of the sheet's inner width, left, printed flat on the paper with no brush pass (the sheet's slap is the card's one event). One mono line under it names the edition (VOL 03 · NO. 03 · COHORT 02; the Build Day sheet says NO. 03 so its own name is not printed twice). The typed title survives only as a visually hidden heading.
3 The kind line is gone from the sheets: the lockup already says which product this is, so the top of the card keeps only the tier stamp at the right. The three sheets are grids (date · lockup · edition · one line · go), so the go links sit on one baseline whatever the lockup's height.
4 Each lockup is one image in the page's defs, and every place it appears is a <use> of it: the Live, Build Day and Intensive lockups are each embedded once and shared by their sheet and their row. Seven lockups, eight photos, none twice.
5 Circle (row 03) and Build Day (row 04) sit on opposite sides and carry different shapes: Circle's cluster is tall (one portrait photo, the SKOOL 社群 paper sticker, one blank card), Build Day's is wide (the Build Day room as the big photo with two blank cards over its corners). Circle's copy is the community and its record line is SKOOL + WhatsApp; Build Day's copy is the one day in the room and its record line is a date and a place. Same stamp on both, because both are still to be opened.
6 Row count runs 01 to 07 everywhere it is printed (the row index, the section meta), the foot lists Build Day after Circle anchored to #buildday, and the row still brushes its lockup on as before.
7 The Build Day lockup is the client's v6 shape, embedded untouched like the other six; only its context (paper, size) is set here.
8 Nothing else moved: the tape, the wall, the sheet on the wall, the seam, the row motion, the foot.
-->"""

# ---------------- assemble: one shell (the template), nine pages ----------------
# The template is the homepage. Its middle (between the @home marks) and its motion layer (between the @homejs marks) belong to the homepage only;
# every other page keeps the shell around them (head, the tape, the wall header, the foot) and puts its own <main> in the middle.
tpl = open(TPL, encoding='utf-8').read()
MARKS = ('<!--@home-->\n', '<!--@/home-->\n', '<!--@homejs-->\n', '<!--@/homejs-->\n')
for m in MARKS:
    assert tpl.count(m) == 1, m
PAGES = {}     # path under the site root -> finished html


def page(path, title, desc, og, middle=None, js='', home=None):
    """Finish one page. Call it after the page's own html is made (so its lockups are registered under the right ROOT)."""
    t = tpl
    if middle is None:
        for m in MARKS:
            t = t.replace(m, '')
    else:
        a, b = t.index(MARKS[0]), t.index(MARKS[1]) + len(MARKS[1])
        t = t[:a] + middle + t[b:]
        a, b = t.index(MARKS[2]), t.index(MARKS[3]) + len(MARKS[3])
        t = t[:a] + js + t[b:]
    rep = {
        '{{HL}}': HL,
        '{{GRIT}}': GRIT,
        '{{WM}}': logo(WORDMARK),
        '{{LKDEFS}}': ''.join(LKDEFS),
        '{{LOG}}': log_html(),
        '{{REV}}': EV['synced'],
        '{{TITLE}}': escape(title),
        '{{DESC}}': escape(desc).replace('"', '&quot;'),          # inside content="...": only the double quote needs escaping, an apostrophe stays as typed
        '{{OGURL}}': SITE_URL + os.path.dirname(path) + ('/' if os.path.dirname(path) else ''),
        '{{OGIMG}}': og,
        '{{HOME}}': '' if middle is None else ROOT,     # the nav's #next / #where: the page's own anchors on the homepage, ../#next from anywhere else
        **(home or {}),
        '{{ROOT}}': ROOT,                               # last, so a {{ROOT}} inside another value is filled too
    }
    for k, v in rep.items():
        assert k in t, (path, k)
        t = t.replace(k, v)
    left = re.findall(r'\{\{[A-Z0-9]+\}\}', t)
    assert not left, (path, left)
    PAGES[path] = t
    return t


print('photos:')
begin('')
rows = rows_html()
# the sheets carry the same lockups as their rows (registered above, so these are <use>s of the same image)
sheets = '\n'.join(sheet_html(e, tilt) for e, tilt in SHEETS)
built = built_html()
logo(FAVICON)
out = page('index.html', 'Breakthrough', "You don't learn a breakthrough. You build one.", f'{SITE_URL}assets/img/og.jpg', home={
    '{{TAPEBAND}}': TAPEBAND,
    '{{ROWS}}': rows,
    '{{NROWS}}': f'{len(LIVE_ROWS):02d}',
    '{{NOTE}}': NOTE,
    '{{SHEETS}}': sheets,
    '{{BUILT}}': built,
    '{{NCOUNT}}': DATES['{{NCOUNT}}'],
    '{{NEXTMETA}}': DATES['{{NEXTMETA}}'],
})
HOME_LK = list(LK)

begin('../')
m = log_page()
page('log/index.html', 'Build log · Breakthrough', REC['log']['lede'], og_image(FEATURED['key'], f'assets/rec/{FEATURED["photos"][0]["src"]}', FEATURED.get('og_focus', .5)), m, LOG_JS)
for r in RECORDS:
    begin('../../')
    m = record_page(r)
    page(f'log/{r["key"]}/index.html', f'{r["name"]} · {r["edition"]} · Breakthrough', r['text'],
         og_image(r['key'], f'assets/rec/{r["photos"][0]["src"]}', r.get('og_focus', .5)), m)
for c in COLLECTIONS:
    begin('../../')
    m = collection_page(c)
    page(f'log/{c["key"]}/index.html', f'{c["name"]} · {c["h1"].rstrip(".")}', c['text'],
         og_image(c['key'], f'assets/rec/{c["photos"][0]["src"]}', c.get('og_focus', .5)), m)
begin('../')
m = roundtable_page()
page('roundtable/index.html', 'Breakthrough Roundtable', REC['roundtable']['lede'], og_image('roundtable', f'assets/rt/{EPISODES[0]["file"]}.jpg'), m)
begin('')

# ---------------- checks: the homepage as before, then every page's files and links ----------------
assert 'base64' not in out, 'no base64 anywhere: photos and logos are files under assets/'
refs = re.findall(r'(?:src|href)="(assets/[^"]+)"', out)
photos = [r for r in refs if r.startswith('assets/img/')]
assert len(photos) == len(PHOTOS) and len(set(photos)) == len(PHOTOS), 'every photo referenced exactly once'
assert set(os.path.basename(p) for p in photos) == set(PHOTOS), 'every photo in PHOTOS is on the page'
lks = [r for r in refs if r.endswith('-ink.svg')]
assert len(lks) == len(set(lks)) == len(HOME_LK), 'each lockup embedded exactly once'
assert {r['slug'] for r in LIVE_ROWS} <= set(HOME_LK), 'every visible row has its lockup'
assert out.count(f'href="{logo(WORDMARK)}"') == 1, 'wordmark bitmap referenced exactly once'
assert os.path.exists(os.path.join(IMG, 'og.jpg')) and 'assets/img/og.jpg"' in out, 'the share image (1200x630, wordmark on the wall black) is in place and declared'
N_SHEETS = 4 if LIVE2 else 3
N_BUILT = 2 + len(COLLECTIONS)          # section 03: the wide card, the newest cohort, one card per pooled page
BUILT_SLUGS = [FEATURED['lockup'], LATEST['lockup']] + [c['lockup'] for c in COLLECTIONS]
for slug in ('breakthrough-live', 'breakthrough-build-day', '2nd-brain-intensive'):
    # 一行 + 一格 (Live 在一个月两场的月份有两格, decision 2026-09-20) + 第 03 段里印它的卡。
    on_sheets = 2 if (slug == 'breakthrough-live' and LIVE2) else 1
    want = 1 + on_sheets + BUILT_SLUGS.count(slug)
    assert out.count(f'href="#lk-{slug}"') == want, f'{slug}: one use on its row, one per sheet, one per card in section 03 (got {out.count(chr(34)+"#lk-"+slug+chr(34))}, want {want})'
assert out.count('<use href="#lk-') == len(LIVE_ROWS) + N_SHEETS + N_BUILT, 'visible rows + the sheets (four when the month has two Lives) + the cards of section 03'
assert 'class="kind"' not in out and 'class="ed"' not in out, 'the kind and edition lines are gone from the sheets'
assert out.count('class="idx" aria-hidden') == N_SHEETS and out.count('class="tick"') == N_SHEETS, 'one stub per sheet, each with its tape index and ticking serial'
assert '<div class="idx">Row <b>03</b> / 05</div>' in out and 'id="buildday"' in out and '<div class="idx">Row <b>05</b> / 05</div>' in out and 'id="roundtable"' in out
for rid in ('circle', 'challenge'):
    assert f'id="{rid}"' not in out and f'href="#{rid}"' not in out, f'{rid} is hidden for now'
assert out.count('<a class="x-bc') == N_BUILT and out.count('<a class="x-bc x-feat"') == 1, 'section 03: one wide card and three beside it'
assert out.startswith('<!doctype html>') and out.rstrip().endswith('</html>')

EXTERNAL = ('https://cdnjs.cloudflare.com/', 'https://fonts.googleapis.com', 'https://kalozedu.com/', 'https://join.project-breakthrough.com.my/',
            'https://wa.me/', 'https://chat.whatsapp.com/', 'https://www.facebook.com/', 'https://www.instagram.com/', 'https://www.skool.com/',
            'https://claude.ai/', 'https://www.youtube.com/')
for path, html_ in PAGES.items():
    here = os.path.dirname(path)
    assert html_.startswith('<!doctype html>') and html_.rstrip().endswith('</html>'), path
    assert 'base64' not in html_, path
    assert all(m not in html_ for m in MARKS), path
    assert html_.count('<h1') == 1, f'{path}: one h1'
    if path != 'index.html':
        assert 'gsap' not in html_ and 'class="hero' not in html_, f'{path}: the homepage\'s middle and motion layer stay on the homepage'
    for u in re.findall(r'(?:src|href|poster)="([^"]+)"', html_):
        if u.startswith(('http://', 'https://')):
            assert u.startswith(EXTERNAL), (path, u)
            continue
        if u.startswith('#'):
            assert u == '#top' or f'id="{u[1:]}"' in html_, f'{path}: nothing on the page is called {u}'
            continue
        target, _, frag = u.partition('#')
        full = os.path.normpath(os.path.join(SITE, here, target))
        assert full == SITE or full.startswith(SITE + os.sep), (path, u)
        rel = os.path.relpath(full, SITE)
        if target == '' or target.endswith('/'):            # a page of this site
            dest = 'index.html' if rel == '.' else os.path.join(rel, 'index.html')
            assert dest in PAGES, f'{path}: links to {u}, which is not a page this build writes'
            assert not frag or f'id="{frag}"' in PAGES[dest], f'{path}: {u} points at an anchor {dest} does not have'
        else:                                                # a file under assets/
            assert os.path.exists(full), f'{path}: referenced file missing: {u}'
    for u in re.findall(r'<meta property="og:image" content="([^"]+)"', html_):
        assert u.startswith(SITE_URL) and os.path.exists(os.path.join(SITE, u[len(SITE_URL):])), f'{path}: share image missing: {u}'
for e in EPISODES:
    assert PAGES['roundtable/index.html'].count(f'watch?v={e["video"]}"') == 1, f'episode {e["n"]} is linked exactly once'
assert len({e['video'] for e in EPISODES}) == len({e['n'] for e in EPISODES}) == len({e['file'] for e in EPISODES}) == len(EPISODES)
for r in RECORDS + COLLECTIONS:
    names = [p['src'] for p in r['photos']]
    assert len(names) == len(set(names)), f'{r["key"]}: a photo is listed twice'
    assert PAGES[f'log/{r["key"]}/index.html'].count('class="x-pin') == len(names), f'{r["key"]}: every photo in records.json is on its page, once'
    assert f'href="log/{r["key"]}/"' in PAGES['log/index.html'].replace('../', ''), f'{r["key"]} can be reached from /log/'

# ---------------- the feed: printed from the same table as the sheets, then held to the sheets as the finished page shows them ----------------
FEED = feed()


def rendered_sheets(page):
    """What each sheet on the finished page says, read back out of the HTML (not out of SHEET_COPY), in page order."""
    got = []
    for block in re.findall(r'<article class="sheet">(.*?)</article>', page, re.S):
        one = lambda rx: html.unescape(re.search(rx, block, re.S).group(1))
        slug = one(r'<use href="#lk-(.*?)"/>')
        got.append({
            'stamp': one(r'<span class="stamp">(.*?)</span>'),
            'editionLabel': one(r'<em>(.*?)</em>'),
            'editionNumber': one(r'data-v="(.*?)"'),
            'dateLine': one(r'class="day" aria-label="(.*?)"'),
            'days': re.findall(r'(\d+)(?:<i>|</span>|</div>)', re.search(r'<div class="n[^"]*" aria-hidden="true">(.*?)</div>', block, re.S).group(1) + '</div>'),
            'tapeIndex': one(r'<span class="idx" aria-hidden="true">(.*?)</span>'),
            'paragraph': one(r'<p>(.*?)</p>'),
            'cta': {'label': one(r'<a class="go" href="[^"]*">(.*?)</a>'), 'href': one(r'<a class="go" href="([^"]*)"')},
            'logo': f'{SITE_URL}assets/logos/{slug}-ink.svg',
        })
    return got


PAGE_SHEETS = rendered_sheets(out)
assert len(PAGE_SHEETS) == len(SHEETS), f'the page shows {len(PAGE_SHEETS)} sheets, SHEETS lists {len(SHEETS)}'
BY_DATE = sorted(range(len(SHEETS)), key=lambda i: (SHEETS[i][0]['start'], SHEETS[i][0]['end'], SHEETS[i][0]['id']))
FIRST = FEED['events'][:len(SHEETS)]
assert [f['id'] for f in FIRST] == [SHEETS[i][0]['id'] for i in BY_DATE], (
    'upcoming.json must open with the sheets, in date order; an event that is not on a sheet now falls before one that is: '
    f'{[f["id"] for f in FIRST]} vs {[SHEETS[i][0]["id"] for i in BY_DATE]}')
for f, i in zip(FIRST, BY_DATE):
    want = {k: f[k] for k in PAGE_SHEETS[i]}
    assert want == PAGE_SHEETS[i], f'upcoming.json {f["id"]} differs from its sheet on the page: {want} vs {PAGE_SHEETS[i]}'
    assert f['onSheet'], f['id']
assert not any(f['onSheet'] for f in FEED['events'][len(SHEETS):]), 'only the sheets are marked onSheet'
assert all(f['logo'].startswith('https://') for f in FEED['events']), 'feed logos are absolute https links'
assert len({f['id'] for f in FEED['events']}) == len(FEED['events']), 'feed ids are unique'


def write_feed(body):
    """Write upcoming.json. generatedAt is when its content last changed: a rebuild that changes nothing keeps the old stamp,
    so the file stays byte-identical run after run like index.html."""
    old = None
    if os.path.exists(FEED_FILE):
        try:
            old = json.load(open(FEED_FILE, encoding='utf-8'))
        except ValueError:
            old = None
    rest = lambda f: {k: v for k, v in f.items() if k != 'generatedAt'}
    stamp = old.get('generatedAt') if isinstance(old, dict) and rest(old) == rest(body) else None
    body = dict(body, generatedAt=stamp or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'))
    open(FEED_FILE, 'w', encoding='utf-8').write(json.dumps(body, ensure_ascii=False, indent=1) + '\n')
    return body


for path, html_ in PAGES.items():
    full = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w', encoding='utf-8').write(html_)
FEED = write_feed(FEED)
print(f'upcoming.json {len(FEED["events"])} events ({len(SHEETS)} on sheets) · generatedAt {FEED["generatedAt"]}')
size = lambda p: os.path.getsize(p)
assets = sum(size(os.path.join(d, f)) for d, _, fs in os.walk(os.path.join(SITE, 'assets')) for f in fs)
print(f'{len(PAGES)} pages: ' + ' · '.join(f'{"/" + os.path.dirname(p) + "/" if os.path.dirname(p) else "/"} {len(h.encode())/1024:.0f} KB' for p, h in PAGES.items()))
print(f'assets/ {assets/1024/1024:.2f} MB')
