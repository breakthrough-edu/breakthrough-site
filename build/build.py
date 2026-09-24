#!/usr/bin/env python3
"""Rebuild index.html from build/index.tpl.html.

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


def reg(slug):
    """Register a lockup once: the untouched ink vector as one <image id="lk-<slug>"> in the shared defs, referenced
    by path. A row and a card that show the same product both <use> this one image."""
    if slug in LK:
        return LK[slug]
    href = logo(f'{slug}-ink.svg')
    raw = open(os.path.join(SITE, href), 'rb').read()
    vb = re.search(rb'viewBox="([^"]+)"', raw).group(1).decode().split()
    x, y, w, h = map(float, vb)
    LKDEFS.append(f'<image id="lk-{slug}" href="{href}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"/>')
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
                 cta='RSVP →', href='https://kalozedu.com/breakthrough-live'),
    # 一个月两场 Live (decision 2026-09-20): 週五晚上那场用上面那句, 週末下午那场用这句 (它的字就是在讲周末下午)。
    'live-weekend': dict(stamp='Free meetup',
                         para='同一个月的第二场, 换成周末下午。一样是现场 build, 走不开平日晚上的就来这一场。',
                         cta='RSVP →', href='https://kalozedu.com/breakthrough-live'),   # 报名页两场同时开放 (decision 2026-09-24), 不再指社群
    'buildday': dict(stamp='Members only',
                     para='带着生意上一个卡住的地方来。一整天, 用 AI 亲手 build 一套解决它的系统; 不是上课, 是做出来。',
                     cta='WHATSAPP US →', href=WA_BUILD_DAY),
    'intensive': dict(stamp='Paid workshop',
                      para='你一直在当全公司的硬盘。两天, 把你怎么做生意的判断 build 进 2nd Brain, 装成你的 Personal OS: AI 照你的方式做事, 团队问 AI 就像问你。公司的 OS, 从这里开始。',
                      cta='REGISTER →', href='https://kalozedu.com/2nd-brain-intensive'),
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
         action=('link', 'https://kalozedu.com/breakthrough-live')),
    dict(id='intensive', slug='2nd-brain-intensive', name='2nd Brain Intensive', lw=.84,
         pics=[('2bi-room.jpg', '4/3', '2nd Brain Intensive 课室, 满桌黑 T 恤, Jia Wei 在前面的 Breakthrough 立牌旁', ''),
               ('2bi-huddle.jpg', '3/2', '一桌学员围着一台笔电, 一起 build', ''),
               ('2bi-pair.jpg', '3/2', '两位学员在 2nd Brain Intensive 里一起看一台笔电', '')],
         para='不是 AI 课, 是 2nd Brain 的课。两天, 把你做生意的那套判断, 从只在你脑袋里, build 进你自己的 2nd Brain, 装成你的 Personal OS。从那天起, AI 做出来的东西开始像你, 同事去问 AI 就像问你, 你不用再当全公司的硬盘; 再往上一步, 就是整间公司的 OS。教的人不是纸上谈兵, 他自己的生意, 每天就是这样跑的。',
         rec=f'两天 · 周末 · Kaloz EDU, Shah Alam · 下一届 <b>{zh_date(NEXT["intensive"])}</b>',
         action=('link', 'https://kalozedu.com/2nd-brain-intensive')),
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
    dict(id='roundtable', hidden=True,  # JW 2026-09-06: hidden until it has photos
         slug='breakthrough-roundtable', name='Breakthrough Roundtable', lw=1,
         pics=[None, None, None],
         para='别人的 Breakthrough, 是怎么 build 出来的? 一档访谈节目, 每集请一位真的在做生意的人坐下来, 不讲成功学, 拆他把方法落地的过程: 怎么判断、怎么取舍、踩过什么坑。',
         rec=None,
         action=('soon',)),
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

# ---------------- assemble ----------------
tpl = open(TPL, encoding='utf-8').read()
print('photos:')
rows = rows_html()
# the sheets carry the same lockups as their rows (registered above, so these are <use>s of the same image)
sheets = '\n'.join(sheet_html(e, tilt) for e, tilt in SHEETS)
logo(FAVICON)
rep = {
    '{{HL}}': HL,
    '{{GRIT}}': GRIT,
    '{{WM}}': logo(WORDMARK),
    '{{LKDEFS}}': ''.join(LKDEFS),
    '{{LOG}}': log_html(),
    '{{TAPEBAND}}': TAPEBAND,
    '{{ROWS}}': rows,
    '{{NROWS}}': f'{len(LIVE_ROWS):02d}',
    '{{NOTE}}': NOTE,
    '{{SHEETS}}': sheets,
    **DATES,
}
out = tpl
for k, v in rep.items():
    assert k in out, k
    out = out.replace(k, v)
left = re.findall(r'\{\{[A-Z0-9]+\}\}', out)
assert not left, left

# ---------------- checks: same page as before, now referencing files ----------------
assert 'base64' not in out, 'no base64 anywhere: photos and logos are files under assets/'
refs = re.findall(r'(?:src|href)="(assets/[^"]+)"', out)
for r in refs:
    assert os.path.exists(os.path.join(SITE, r)), f'referenced file missing: {r}'
photos = [r for r in refs if r.startswith('assets/img/')]
assert len(photos) == len(PHOTOS) and len(set(photos)) == len(PHOTOS), 'every photo referenced exactly once'
assert set(os.path.basename(p) for p in photos) == set(PHOTOS), 'every photo in PHOTOS is on the page'
lks = [r for r in refs if r.endswith('-ink.svg')]
assert len(lks) == len(LIVE_ROWS) and len(set(lks)) == len(LIVE_ROWS), 'one lockup per visible row, each embedded exactly once'
assert out.count(f'href="{rep["{{WM}}"]}"') == 1, 'wordmark bitmap referenced exactly once'
assert os.path.exists(os.path.join(IMG, 'og.jpg')) and 'assets/img/og.jpg"' in out, 'the share image (1200x630, wordmark on the wall black) is in place and declared'
for slug in ('breakthrough-live', 'breakthrough-build-day', '2nd-brain-intensive'):
    # 一行 + 一格; Live 在一个月两场的月份有两格 (decision 2026-09-20), 所以它是 2 或 3, 别的仍然只能是 2。
    want = (2, 3) if (slug == 'breakthrough-live' and LIVE2) else (2,)
    assert out.count(f'href="#lk-{slug}"') in want, f'{slug}: one use on its row, one per sheet (got {out.count(chr(34)+"#lk-"+slug+chr(34))})'
assert out.count('<use href="#lk-') == len(LIVE_ROWS) + (4 if LIVE2 else 3), 'visible rows + the sheets (four when the month has two Lives)'
assert 'class="kind"' not in out and 'class="ed"' not in out, 'the kind and edition lines are gone from the sheets'
N_SHEETS = 4 if LIVE2 else 3
assert out.count('class="idx" aria-hidden') == N_SHEETS and out.count('class="tick"') == N_SHEETS, 'one stub per sheet, each with its tape index and ticking serial'
assert '<div class="idx">Row <b>03</b> / 04</div>' in out and 'id="buildday"' in out
for rid in ('circle', 'challenge', 'roundtable'):
    assert f'id="{rid}"' not in out and f'href="#{rid}"' not in out, f'{rid} is hidden for now'
ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', out)
for u in ext:
    assert u.startswith(('https://cdnjs.cloudflare.com/', 'https://fonts.googleapis.com', 'https://kalozedu.com/', 'https://wa.me/', 'https://chat.whatsapp.com/', 'https://www.facebook.com/', 'https://www.instagram.com/', 'https://www.skool.com/', 'https://claude.ai/')), u
assert out.startswith('<!doctype html>') and out.rstrip().endswith('</html>')

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


open(OUT, 'w', encoding='utf-8').write(out)
FEED = write_feed(FEED)
print(f'upcoming.json {len(FEED["events"])} events ({len(SHEETS)} on sheets) · generatedAt {FEED["generatedAt"]}')
size = lambda p: os.path.getsize(p)
assets = sum(size(os.path.join(d, f)) for d, _, fs in os.walk(os.path.join(SITE, 'assets')) for f in fs)
print(f'index.html {size(OUT)/1024:.0f} KB · assets/ {assets/1024/1024:.2f} MB')
