# Breakthrough 官网

Breakthrough 的首页, 一个纯静态站: 一份 `index.html` 加 `assets/` 里的照片和 logo, 没有后端, 没有 build 框架。托管在 GitHub Pages, 之后由 GHL 用 iframe 包进 kalozedu.com。外部只载两样: GSAP (cdnjs) 和三套字体 (Google Fonts), 其余全在这个夹里。

## 目录

```
index.html            首页 (由 build/build.py 从模板生成, 不手改)
assets/
  img/                照片, 可读的 kebab-case 档名 (live-grouphoto.jpg, 2bi-classroom.jpg, buildday-room.jpg ...)
  logos/              七个产品 lockup 的 -ink.svg, wordmark.png, favicon 用的 b-mark.svg
build/
  build.py            重出 index.html 的脚本; 文案表 (ROWS / CARDS / ENTRIES) 和照片表 (PHOTOS) 在顶部
  index.tpl.html      页面模板 (head, CSS, 三张卡的日期与文案, 页脚, 动画脚本)
  README.md           怎么改字、换照片、本机预览、上线 (细节版)
.nojekyll             告诉 GitHub Pages 不要跑 Jekyll, 原样出档
```

## 三个动作

**预览**: 在这个夹里跑 `python3 -m http.server 8080`, 然后开 http://localhost:8080 。要用 http 开, 不要直接双击 index.html (file:// 下 logo 的跨源规则不同, 看到的不是上线后的样子)。

**改**: 换照片 = 用同名档覆盖 `assets/img/` 里那张, 完事, 不用重 build。改文案 = 改 `build/build.py` 顶部的 ROWS / CARDS / ENTRIES 表 (七行的文案、三张卡的 lockup 与期数、build log), 或改 `build/index.tpl.html` (三张卡的日期与一句话、页脚、head), 然后在这个夹里跑 `python3 build/build.py` 重出 index.html。细节看 `build/README.md`。

**上线**: git push 到 GitHub, Pages 约一分钟后更新。上线前先跑一次预览, 1440 和 375 各看一眼。
