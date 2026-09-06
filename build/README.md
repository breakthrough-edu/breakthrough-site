# build/ 怎么用

`index.html` 是生成物, 不手改。改这里的东西, 然后从站根 (`site/`, 有 `index.html` 的那层) 跑:

```
python3 build/build.py
```

脚本读 `build/index.tpl.html`, 填进 `build.py` 顶部各张表的内容, 写出 `index.html`。同一份输入跑几次, 出来的 `index.html` 一个字节都不变。需要 Python 3 和 Pillow (`pip install pillow`); Pillow 只用来读照片尺寸和 (需要时) 压照片。

## 改字

文案分两处住, 看你要改的是哪一段:

- **`build.py` 顶部的表**
  - `ROWS`: 第三节的行 (Breakthrough Live, 2nd Brain Intensive, Build Day, Circle, Brand Strategy Breakthrough, Brand Launch Off Challenge, Roundtable) 的段落 `para`、记录行 `rec`、按钮 `action` (`('link', url)` 出「了解更多」, `('soon',)` 出 Coming soon 印章), 以及每行三张照片 `pics` (档名、宽高比、alt 中文描述)。行的顺序就是表的顺序。带 `hidden=True` 的行留在表里但不上页 (2026-09-06 起 Circle / Challenge / Roundtable 这样藏着, 等有照片: 拿掉 flag, 补 `pics`, 页脚 `index.tpl.html` 加回那行的锚点, 跑 build)。
  - `CARDS`: 第二节三张卡各自印哪个产品的 lockup, 和 lockup 下那行期数 (Vol 03 / No. 03 / Cohort 02)。
  - `ENTRIES`: 顶上那条 build log 胶带的条目, `x` 是做过的, `o` 是排定的, `now` 是游标。
- **`index.tpl.html`**: 三张卡的日期、印章字样、那一句话和 go 链接; 页脚 (地址、链接); `<head>` 里的 title / description / og。CSS 和动画脚本也在这里, 但那是设计层, 不是改字。

改完跑一次 `python3 build/build.py`。脚本末尾有一串检查 (`PHOTOS` 里每张照片、每个可见行的 lockup 各引用一次, 外链只准 cdnjs / Google Fonts / kalozedu.com / wa.me / skool / claude.ai), 不过就会报错停下, 不会写出半成品。

## 换照片

**同名覆盖 `assets/img/` 里那张就好, 不用重 build。** 页面用相对路径引档, CSS 定框 (宽 100% 加固定宽高比, 用 object-fit 裁), 所以新照片比例不同也不会破版, 只是裁的位置不同。建议自己先缩到 1000px 宽以内、JPEG 品质 80 上下, 单张控制在 160KB 内。

要**加新照片或换档名**才动 `build.py`: 在 `PHOTOS` 表加一行 (`'新档名.jpg': ('原图相对路径', 目标宽度)`), 在 `ROWS` 对应那行的 `pics` 里引用它, 然后跑 build。`assets/img/` 里已经存在的档一律不动; 缺的那张会从原图夹压出来 (压之前照 EXIF 转正; 原图夹默认是 Drive 资产库的设计夹 `~/Documents/Breakthrough-Assets/Breakthrough-EDU/website/homepage-design-2026-09-06/assets`, 可用 `--source 路径` 或环境变量 `BT_SOURCE` 指别处)。`--refresh-photos` 会把全部照片从原图重压一遍, 覆盖现有档, 一般用不到。

Logo 同理: `assets/logos/` 里的档直接用, 缺了才从原图夹的 `logos/` 复制。

## 本机预览

```
python3 -m http.server 8080
```

从站根跑, 然后开 http://localhost:8080 。一定要经 http, 直接用 file:// 打开 index.html 不算数: 页面里的 lockup 是 SVG `<image>` 引外部 svg 档, file:// 下的跨源规则跟上线后不同, 看到的不是真实样子。看 1440 和 375 两个宽度, 375 不能有横向滚动。

## 上线

站是 GitHub Pages 托管 (`.nojekyll` 在, 所以 Pages 原样出档, 不跑 Jekyll)。改完 `git push` 到 GitHub, 约一分钟后上线。推之前先本机预览一次。
