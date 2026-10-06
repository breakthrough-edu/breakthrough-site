# build/ 怎么用

`index.html`、`log/` 与 `roundtable/` 底下的每一张 `index.html`、`upcoming.json` 都是生成物, 不手改。改这里的东西, 然后从站根 (有 `index.html` 的那层) 跑:

```
python3 build/build.py
```

脚本读 `build/index.tpl.html`, 填进 `build.py` 顶部各张表、`events.json` 与 `records.json` 的内容, 写出首页和每一张子页。同一份输入跑几次, 出来的页面一个字节都不变。模板就是首页; 子页留着它的外壳 (head、CSS、顶上那条胶带、页头、页脚), 把中间 (`<!--@home-->` 两个记号之间) 换成自己的内容, 首页的动画脚本 (`<!--@homejs-->` 之间) 不带过去。需要 Python 3 和 Pillow (`pip install pillow`); Pillow 只用来读照片尺寸和 (需要时) 压照片。

## 改字

文案分两处住, 看你要改的是哪一段:

- **`build.py` 顶部的表**
  - `ROWS`: 第三节的行 (Breakthrough Live, 2nd Brain Intensive, Build Day, Circle, Brand Strategy Breakthrough, Brand Launch Off Challenge, Roundtable) 的段落 `para`、记录行 `rec`、按钮 `action` (`('link', url)` 出「了解更多」, `('soon',)` 出 Coming soon 印章), 以及每行三张照片 `pics` (档名、宽高比、alt 中文描述)。行的顺序就是表的顺序。带 `hidden=True` 的行留在表里但不上页 (2026-09-06 起 Circle / Challenge 这样藏着, Roundtable 2026-10-06 放回来当最后一行; 要放一行出来: 拿掉 flag, 补 `pics`, 页脚 `index.tpl.html` 加回那行的锚点, 跑 build)。
  - `SHEET_COPY` / `PRODUCT`: 第二节每张卡的印章字样、那一句话、go 链接 (字样与 href), 以及每种活动印哪个 lockup。卡上的字只住这里 (2026-09-24 起从模板搬来), 因为同一张表也印 `upcoming.json` (见下面「给 Portal 的 feed」)。Live 週六或週日那场用 `live-weekend` 那句, 週五那场用 `live` 那句。
  - `ENTRIES`: 顶上那条 build log 胶带的条目, `x` 是做过的, `o` 是排定的, `now` 是游标。⚠️ 2026-09-06 起不手打: 它从 `events.json` 生 (下面「改日期」)。
- **`index.tpl.html`**: 页脚 (地址、链接); `<head>` 里的 title / description / og。CSS 和动画脚本也在这里, 但那是设计层, 不是改字。第二节的卡整张由 `build.py` 生 (模板里只剩 `{{SHEETS}}`), 卡上的日期与届次也不在这里 (见「改日期」)。

## Build log 那几页 (2026-10-06 起)

首页第 03 段「What's already been built.」、`/log/`、`/log/<key>/` 各张记录页、`/log/live/` 与 `/log/build-day/` 两张合起来的照片页、`/roundtable/`, 内容全部住 **`build/records.json`** (档头的 `_readme` 有逐项说明), 长相是模板 CSS 最后那一大段 (`x-` 开头的 class)。

- **加一场记录** (2BI 新的一届、一场不会每个月重来的活动): 在 `records` 加一笔 (`key` 就是它在 `/log/` 底下的夹名, 起讫日期, 届次, `copy` 指 `copy` 段里哪一份文案; 2BI 各届共用 `2bi` 那份), 照片放进 `assets/rec/`, 档名 `<key>-lead.jpg` (主图, 长边 1600px) 与 `<key>-01.jpg` 起 (长边 960px, JPEG 品质 78), 把每张的档名与像素宽高写进 `photos`。跑 build, 它的页、`/log/` 上的那一条、同一条产品线前后届的链接都自己出来。首页第 03 段那张 2BI 卡印的是 `home.latest_line` 那条线上最新的一笔, 所以新的一届会自己换上去; 横跨全宽的那张大卡是 `home.featured` 手动指定的, 不会被后来的场次挤走。
- **Live 与 Build Day 加照片**: 加进那个 collection 的 `photos`, 每张带 `cap` (是哪一场)。页上的场次范围 (Vol 01 to 04) 是从 `events.json` 数出来的, 办过几场就写到几场, 不手打; 照片标的场次要是已经办过的, 否则 build 会停下来说。
- **有短片**: 档放 `assets/film/<名字>.mp4` 与同名 `.jpg` 封面, 在那笔记录写 `"film": {"file": "<名字>", "duration": "0:45"}`。短片直接放站上, 压到几 MB (H.264 + AAC, `-movflags +faststart`), 不经 YouTube。
- **Roundtable 加一集**: 那一集在 YouTube 发了之后, 封面放 `assets/rt/<来宾名字>.jpg` (1280x720), 在 `roundtable.episodes` 加一笔 (YouTube 上的集数、来宾、封面档名、影片 id)。集数只照 YouTube 的编号, 对集数只认来宾名字。还没发的集数不放。
- **照片谁选**: 每一张都是站主自己在挑图页点选的, 不自动选。照名单从原档压图, `orig` 记着原档在 Drive 资产库 (`~/Documents/Breakthrough-Assets/`) 里的位置。
- **照片的 alt**: build 自己写 (哪一场 + 现场 / 合照)。不要把照片索引里描述人的句子搬进页面。
- **分享预览**: 每张子页有自己的标题、描述 (卡上那句短文案) 与分享图。分享图在 `assets/og/<key>.jpg`, 第一次 build 时从那页的主图裁成 1200x630; 裁的位置不对就在那笔记录加 `og_focus` (0 是贴上缘, 1 是贴下缘), 删掉那张 og 图再跑 build。
- **改字**: 这几页的文案是站主逐段过的, 先改 vault 的 SOT, 再改 `records.json`。

## 改日期

页上所有日期 (胶带 · 三张卡的日期与届次 · 各行「下一场」· Rev 章) 都从 **`build/events.json`** 生, 而它的 `upcoming` 段是 **`build/sync-events.py`** 从 vault 的活动正本 (Event Prep skill 的 `overrides.json` → 各活动 brief 的 `started` / `due`) 刷出来的, 不手打。活动日期定了或改了, 从站根跑:

```
python3 build/sync-events.py --check   # 先看会改什么
python3 build/sync-events.py           # 写 events.json
python3 build/build.py                 # 重出 index.html, 预览, 再 push
```

`events.json` 里手写的只有两段: `history` (胶带上做过的往事) 和 `planned` (有日期还没 brief 的, 只上胶带不上卡; brief 开了就删那行)。⛔ 模板跟 build.py 里不准再打日期; 页要的日期 brief 没有, 去补 brief。这一步已经写进 Event Prep skill 的「Website sync」模式, 平常由它带着跑。

改完跑一次 `python3 build/build.py`。脚本末尾有一串检查 (`PHOTOS` 里每张照片、每个 lockup 各嵌一次; 每一页引用的档都在、站内的每一条链接都指得到一张真的页与真的锚点; `records.json` 里的每张照片都在它的页上出现一次; Roundtable 每一集各连一次; 外链只准白名单上的几个网域, YouTube 在内), 不过就会报错停下, 不会写出半成品。

## 给 Portal 的 feed: `upcoming.json`

每次 build 也在站根写 `upcoming.json` (上线后在 https://breakthrough-edu.github.io/breakthrough-site/upcoming.json , GitHub Pages 自带 `access-control-allow-origin: *`)。2BI Student Portal 的 Home 读它, 在右边那条「What's getting built next」印票根。

- 内容: `events.json` 里还没过 `now` 的活动, 只收站上有字 (`SHEET_COPY`) 的那些, 按日期排; 每条带 id、kind、英文产品名、期数、起讫日期、月份与星期 (照卡上印的)、时间、印章字样、卡上那句话、go 链接的字样与 href、lockup 的绝对网址、`onSheet` (是不是第二节那几张卡之一)。`schemaVersion` 现在是 1; `generatedAt` 是内容最后一次变的时间, 内容没变就不动, 所以重跑 build 不会平白多出 diff。
- 它跟卡永远一致: build 末尾把 feed 开头那几条跟页面上实际印出的卡逐项比 (从 HTML 读回来比, 不是跟表比), 对不上就停下不写。也要求 feed 开头就是那几张卡 (按日期); 哪天有一场不上卡的活动排在某张卡之前, build 会停下来说, 那时再决定卡的规则。
- 改卡上的字 = 改 `SHEET_COPY`, 跑 build, 两处一起变。⛔ 别手改 `upcoming.json`。
- 改 feed 的形状 (加减栏位) 前先想 Portal: 它用 Zod 整份验, 不认得的形状整份丢掉只显示 motto。要改就把 `schemaVersion` 加一, Portal 那边先接好新版再推站。

## 换照片

**同名覆盖 `assets/img/` 里那张就好, 不用重 build。** 页面用相对路径引档, CSS 定框 (宽 100% 加固定宽高比, 用 object-fit 裁), 所以新照片比例不同也不会破版, 只是裁的位置不同。建议自己先缩到 1000px 宽以内、JPEG 品质 80 上下, 单张控制在 160KB 内。

要**加新照片或换档名**才动 `build.py`: 在 `PHOTOS` 表加一行 (`'新档名.jpg': ('原图相对路径', 目标宽度)`), 在 `ROWS` 对应那行的 `pics` 里引用它, 然后跑 build。`assets/img/` 里已经存在的档一律不动; 缺的那张会从原图夹压出来 (压之前照 EXIF 转正; 原图夹默认是 Drive 资产库的设计夹 `~/Documents/Breakthrough-Assets/Breakthrough-EDU/website/homepage-design-2026-09-06/assets`, 可用 `--source 路径` 或环境变量 `BT_SOURCE` 指别处)。`--refresh-photos` 会把全部照片从原图重压一遍, 覆盖现有档, 一般用不到。

Logo 同理: `assets/logos/` 里的档直接用, 缺了才从原图夹的 `logos/` 复制。

## 本机预览

```
python3 -m http.server 8080
```

从站根跑, 然后开 http://localhost:8080 。一定要经 http, 直接用 file:// 打开 index.html 不算数: 页面里的 lockup 是 SVG `<image>` 引外部 svg 档, file:// 下的跨源规则跟上线后不同, 看到的不是真实样子。看 1440 和 375 两个宽度, 375 不能有横向滚动; 改了页头或导航再多看 1000 上下 (导航四项加按钮要 1200px 才排得下, 以下只留按钮)。子页也各开一张看。本机这个服务器不支援影片拖进度条, 短片只能从头播, 上线后正常。

## 上线

站是 GitHub Pages 托管 (`.nojekyll` 在, 所以 Pages 原样出档, 不跑 Jekyll)。改完 `git push` 到 GitHub, 约一分钟后上线。推之前先本机预览一次。
