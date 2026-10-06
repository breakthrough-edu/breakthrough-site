# Breakthrough 官网

Breakthrough 的官网, 一个纯静态站: 首页加八张以内的子页, `assets/` 里的照片、短片和 logo, 没有后端, 没有 build 框架。托管在 GitHub Pages, 网域 https://project-breakthrough.com.my/ 直接接过来 (`CNAME`)。外部只载两样: GSAP (cdnjs, 只有首页用) 和三套字体 (Google Fonts), 其余全在这个夹里。

## 目录

```
index.html            首页
log/index.html        Build log: Live 与 Build Day 两张卡, 加一条按日期排的时间线
log/<key>/index.html  一场一页的记录 (2BI 每一届、BLOC 午宴), 以及 log/live/、log/build-day/ 两张合在一起的照片页
roundtable/index.html Breakthrough Roundtable: 每集封面连去 YouTube
upcoming.json         给 2BI Builder Portal 读的活动 feed
                      (以上全部由 build/build.py 生成, 不手改)
assets/
  img/                首页的照片, 可读的 kebab-case 档名 (live-grouphoto.jpg, 2bi-classroom.jpg ...), 加首页的分享图 og.jpg
  rec/                记录页的照片: <key>-lead.jpg 是主图, <key>-01.jpg 起是其余的
  film/               记录页的精华短片 (<key>.mp4) 和它的封面 (<key>.jpg)
  rt/                 Roundtable 各集封面, 档名是来宾的名字
  og/                 各子页的分享图 (1200x630), build 时从该页主图裁出来
  logos/              七个产品 lockup 的 -ink.svg, wordmark.png, favicon 用的 b-mark.svg
build/
  build.py            重出全部页面的脚本; 首页的文案表 (ROWS / SHEET_COPY) 和照片表 (PHOTOS) 在顶部
  index.tpl.html      页面模板: 首页本身, 也是每张子页共用的外壳 (head, CSS, 顶上那条胶带, 页头, 页脚)
  records.json        Build log 那几页的全部内容: 每一场的日期、文案、照片名单, Roundtable 的集数
  events.json         页上所有日期的来源 (由 sync-events.py 从活动 brief 刷出来)
  README.md           怎么改字、换照片、加一场记录、本机预览、上线 (细节版)
.nojekyll             告诉 GitHub Pages 不要跑 Jekyll, 原样出档
```

## 三个动作

**预览**: 在这个夹里跑 `python3 -m http.server 8080`, 然后开 http://localhost:8080 。要用 http 开, 不要直接双击 index.html (file:// 下 logo 的跨源规则不同, 看到的不是上线后的样子)。 这个本机服务器不支援影片拖进度条 (短片只能从头播), 上线后在 GitHub Pages 上是正常的。

**改**: 换照片 = 用同名档覆盖 `assets/img/` 里那张, 完事, 不用重 build。改文案 = 改 `build/build.py` 顶部的 ROWS / CARDS / ENTRIES 表 (七行的文案、三张卡的 lockup 与期数、build log), 或改 `build/index.tpl.html` (三张卡的日期与一句话、页脚、head), 然后在这个夹里跑 `python3 build/build.py` 重出全部页面。加一场活动的记录 = 在 `build/records.json` 加一笔, 照片放进 `assets/rec/`, 跑 build。细节看 `build/README.md`。

**上线**: git push 到 GitHub, Pages 约一分钟后更新。上线前先跑一次预览, 1440 和 375 各看一眼。
