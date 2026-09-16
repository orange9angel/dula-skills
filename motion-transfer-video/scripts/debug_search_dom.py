#!/usr/bin/env python3
"""One-off DOM dump of the douyin search page for selector debugging.

Dumps (into dula-story/tmp/douyin/dom/):
  - filterbar.html   : the top filter/sort area
  - card_N.html      : outerHTML of the first few result cards
  - cards.txt        : innerText of those cards (what the regexes see)
  - page_url.txt     : final URL (post redirect)

Run from dula-story:
  .venv/Scripts/python.exe ../dula-skills/motion-transfer-video/scripts/debug_search_dom.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search_douyin import launch, rsleep, PROFILE_DIR  # noqa: E402

OUT = Path("tmp/douyin/dom")

CARD_PROBE = r"""
() => {
  const anchors = [...document.querySelectorAll('a[href*="/video/"]')]
    .filter(a => /\/video\/\d+/.test(a.getAttribute('href')));
  const cards = [];
  const seen = new Set();
  for (const a of anchors) {
    const li = a.closest('li');
    if (!li) continue;
    if (seen.has(li)) continue;
    seen.add(li);
    cards.push(li);
    if (cards.length >= 4) break;
  }
  return cards.map(c => ({html: c.outerHTML, text: c.innerText}));
}
"""

FILTER_PROBE = r"""
() => {
  // grab anything that looks like a filter / tab bar near the top of results
  const hits = [];
  for (const el of document.querySelectorAll('div, span, button')) {
    const t = (el.innerText || '').trim();
    if (['综合排序','最多点赞','最新发布','最多评论','最多收藏','筛选','全部',
         '视频','用户','音乐','话题','直播','图文'].includes(t) && el.children.length === 0) {
      hits.push({tag: el.tagName, text: t,
                 cls: el.className.toString().slice(0, 80),
                 parent: el.parentElement.className.toString().slice(0, 80)});
    }
  }
  // also dump the big containers up top
  const main = document.querySelector('#search-content-area, div[class*="search-result"], main');
  return {hits: hits.slice(0, 40),
          top_html: main ? main.outerHTML.slice(0, 6000) : document.body.innerHTML.slice(0, 6000)};
}
"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = launch(p, headless=False)
        try:
            page = ctx.new_page()
            page.goto("https://www.douyin.com/search/卡点变装?type=video",
                      wait_until="domcontentloaded", timeout=90000)
            rsleep(5, 8)
            (OUT / "page_url.txt").write_text(page.url, encoding="utf-8")

            filt = page.evaluate(FILTER_PROBE)
            (OUT / "filter_hits.json").write_text(
                __import__("json").dumps(filt["hits"], ensure_ascii=False, indent=2),
                encoding="utf-8")
            (OUT / "top.html").write_text(filt["top_html"], encoding="utf-8")

            cards = page.evaluate(CARD_PROBE)
            for i, c in enumerate(cards):
                (OUT / f"card_{i}.html").write_text(c["html"], encoding="utf-8")
            (OUT / "cards.txt").write_text(
                "\n=====CARD=====\n".join(c["text"] for c in cards), encoding="utf-8")
            print(f"dumped {len(cards)} cards, {len(filt['hits'])} filter hits -> {OUT}")
            time.sleep(2)
        finally:
            ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
