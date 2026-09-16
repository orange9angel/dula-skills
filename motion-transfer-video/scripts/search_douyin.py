#!/usr/bin/env python3
"""Search Douyin via the web UI with a logged-in real-Chrome work profile.

Anonymous search on douyin.com is fully walled (login modal with no close
button, zero search XHR — see SKILL.md 翻车记录). This tool therefore keeps its
OWN persistent Chrome profile (never touches the user's real Chrome profile):

  <this dir>/../.chrome-profile/   <- launch_persistent_context user_data_dir
  <this dir>/../.storage_state.json

First run opens a HEADED real Chrome on www.douyin.com; if not logged in it
clicks the login button and polls up to 5 minutes for the user to scan the QR
code. Once logged in, cookies persist in the work profile and later runs reuse
them (storage_state.json is also saved as a backup/inspection artifact).

Usage (from dula-story):
  .venv/Scripts/python.exe ../dula-skills/motion-transfer-video/scripts/search_douyin.py \
      "猫咪跳舞" --limit 20 --sort likes --out tmp/douyin/search.json
  # optional: download every hit through download_douyin.py's cookie-jar path
  ... --download tmp/douyin/videos
  # smoke test: open douyin.com headed, report login state, hold 30s, exit
  ... --smoke

Anti-risk-control etiquette: headless first, headed fallback; random 1.5-4s
sleeps between actions; scroll in small batches; stock UA/window size.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PROFILE_DIR = SKILL_DIR / ".chrome-profile"
STORAGE_STATE = SKILL_DIR / ".storage_state.json"
HOME = "https://www.douyin.com/"

LOGIN_WAIT_S = 300  # QR scan budget
SMOKE_HOLD_S = 30


def rsleep(lo: float = 1.5, hi: float = 4.0) -> None:
    time.sleep(random.uniform(lo, hi))


def _cookie_logged_in(ctx) -> bool:
    # sessionid / sessionid_ss only exist on a logged-in session
    names = {c["name"] for c in ctx.cookies("https://www.douyin.com")}
    return "sessionid" in names or "sessionid_ss" in names


def _dom_logged_in(page) -> bool:
    # logged-out homepage shows a "登录" button top-right and no avatar menu
    try:
        if page.locator('div[data-e2e="douyin-avatar-container"]').count() > 0:
            return True
    except Exception:
        pass
    try:
        btn = page.locator("#douyin-header").locator("button", has_text="登录")
        return btn.count() == 0
    except Exception:
        return _cookie_logged_in(page.context)


def is_logged_in(page) -> bool:
    return _cookie_logged_in(page.context) or _dom_logged_in(page)


def launch(p, headless: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return p.chromium.launch_persistent_context(
        str(PROFILE_DIR), channel="chrome", headless=headless,
        timeout=120000, viewport={"width": 1440, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])


def save_state(ctx) -> None:
    try:
        ctx.storage_state(path=str(STORAGE_STATE))
    except Exception as e:
        print(f"warn: storage_state save failed: {e}")


def ensure_login(p, smoke: bool = False) -> bool:
    """Open douyin.com headed; wait for QR login if needed. Returns logged-in."""
    ctx = launch(p, headless=False)
    try:
        page = ctx.new_page()
        page.goto(HOME, wait_until="domcontentloaded", timeout=90000)
        rsleep(3, 6)
        if is_logged_in(page):
            print("login state: LOGGED IN (work profile cookies valid)")
            save_state(ctx)
            if smoke:
                time.sleep(SMOKE_HOLD_S)
            return True

        print("login state: anonymous -> waiting for QR login dialog")
        try:
            # douyin auto-opens the QR panel for anonymous visitors; it also
            # swallows clicks on the header button, so detect before clicking
            page.wait_for_selector('[id^="login-full-panel"]',
                                   state="attached", timeout=15000)
            print("QR login dialog already up (douyin auto-opens it)")
        except Exception:
            try:  # panel not up — click the header 登录 button
                page.locator("#douyin-header").locator(
                    "button", has_text="登录").first.click(timeout=10000)
            except Exception as e:
                print(f"warn: could not click login button ({e}); "
                      "click 登录 in the window manually")
        if smoke:
            print(f"smoke mode: holding window {SMOKE_HOLD_S}s "
                  "(QR visible), not waiting for scan")
            time.sleep(SMOKE_HOLD_S)
            return False

        print(f"scan the QR code in the Chrome window (timeout {LOGIN_WAIT_S}s)...")
        deadline = time.time() + LOGIN_WAIT_S
        while time.time() < deadline:
            rsleep(2, 3)
            if _cookie_logged_in(ctx) or is_logged_in(page):
                print("login state: LOGGED IN (QR scanned)")
                save_state(ctx)
                return True
        print("error: login timeout (5 min) — rerun and scan faster")
        return False
    finally:
        ctx.close()


# --- search result extraction ------------------------------------------------

CARD_JS = r"""
() => {
  // Card innerText line order (2026-09-16 real DOM, class names are
  // obfuscated and rotate — parse LINES, not classes):
  //   [合集] / 00:07 (duration) / 1.1万 (likes, bare, no 赞 suffix) /
  //   title (has hashtags) / @author / 1月前 (date)
  const RE_DUR = /^\d{1,2}:\d{2}(:\d{2})?$/;
  const RE_LIKES = /^\d+(\.\d+)?万?$/;
  const RE_DATE = /^\d+\s*(小时|天|周|月|年)前$|^\d{4}-\d{2}-\d{2}$|^\d{2}-\d{2}$/;
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll('a[href*="/video/"]')) {
    const m = a.getAttribute('href').match(/\/video\/(\d+)/);
    if (!m || seen.has(m[1])) continue;
    const li = a.closest('li');
    if (!li) continue;
    seen.add(m[1]);
    const lines = (li.innerText || '').split('\n')
      .map(s => s.trim()).filter(Boolean);
    let duration = null, likes = null, author = null, date = null;
    const rest = [];
    for (const ln of lines) {
      if (ln === '合集' || ln === '图文') continue;
      if (!duration && RE_DUR.test(ln)) { duration = ln; continue; }
      if (!likes && RE_LIKES.test(ln)) { likes = ln; continue; }
      if (!author && ln.startsWith('@')) { author = ln.slice(1); continue; }
      if (!date && RE_DATE.test(ln)) { date = ln; continue; }
      rest.push(ln);
    }
    out.push({
      aweme_id: m[1],
      url: 'https://www.douyin.com/video/' + m[1],
      title: rest.join(' ').trim() || null,
      author, likes, duration, date,
    });
  }
  return out;
}
"""


def enrich(results: list[dict]) -> list[dict]:
    """Add numeric likes_num / duration_s for downstream ranking."""
    import re
    for r in results:
        lk = r.get("likes")
        if lk:
            m = re.match(r"^(\d+(?:\.\d+)?)(万)?$", lk)
            if m:
                r["likes_num"] = int(float(m.group(1))
                                     * (10000 if m.group(2) else 1))
        du = r.get("duration")
        if du:
            parts = [int(x) for x in du.split(":")]
            r["duration_s"] = (parts[0] * 3600 + parts[1] * 60 + parts[2]
                               if len(parts) == 3 else parts[0] * 60 + parts[1])
    return results

EXTRACT_TRIES = 6  # rounds with no growth before giving up


def do_search(p, keyword: str, limit: int, sort: str, headless: bool) -> list[dict]:
    ctx = launch(p, headless=headless)
    try:
        page = ctx.new_page()
        url = f"{HOME}search/{keyword}?type=video"
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        rsleep(4, 7)

        if not _cookie_logged_in(ctx) and page.locator(
                "text=登录后即可搜索").count() > 0:
            raise RuntimeError("login wall on search page (cookies stale?)")

        if sort == "likes":
            try:
                # 筛选 is a hover-dropdown (2026-09-16 real UI): hovering opens
                # a panel with 排序依据: 综合排序|最新发布|最多点赞 (+发布时间/
                # 视频时长/搜索范围 rows). Clicking 筛选 itself does nothing.
                page.get_by_text("筛选", exact=True).first.hover(timeout=8000)
                rsleep(1, 2)
                page.get_by_text("最多点赞", exact=True).first.click(timeout=8000)
                rsleep(3, 5)
            except Exception as e:
                print(f"warn: sort filter failed ({e}); using default sort")

        results: list[dict] = []
        stale = 0
        while len(results) < limit and stale < EXTRACT_TRIES:
            found = page.evaluate(CARD_JS)
            if len(found) > len(results):
                results = found
                stale = 0
            else:
                stale += 1
            # gentle batched scroll, not one big yank
            for _ in range(2):
                page.mouse.wheel(0, random.randint(600, 1200))
                rsleep(1.5, 4)
        print(f"extracted {len(results)} cards "
              f"({'headless' if headless else 'headed'})")
        return enrich(results[:limit])
    finally:
        ctx.close()


def search(p, keyword: str, limit: int, sort: str) -> list[dict]:
    try:
        r = do_search(p, keyword, limit, sort, headless=True)
        if r:
            return r
        print("headless got 0 cards — retrying headed")
    except Exception as e:
        print(f"headless search failed ({e}) — retrying headed")
    return do_search(p, keyword, limit, sort, headless=False)


# --- optional download fan-out ----------------------------------------------

VIDEO_SRC_JS = r"""
() => {
  const v = document.querySelector('video');
  if (!v) return null;
  const cands = [v.currentSrc, v.src,
                 ...[...v.querySelectorAll('source')].map(s => s.src)]
    .filter(u => u && u.startsWith('http'));
  // prefer the highest-bitrate variant (br= param), else the one playing
  const br = u => parseInt((u.match(/[?&]br=(\d+)/) || [0, 0])[1]);
  cands.sort((a, b) => br(b) - br(a));
  return cands[0] || null;
}
"""


def sniff_download_one(page, url: str, dest: Path) -> bool:
    """Plan B: read the signed CDN URL off the detail page's <video> element
    and GET it through the browser context. yt-dlp's Douyin extractor 403s
    on the web-detail JSON endpoint (2026-09-16, v2026.08.19, both logged-in
    and anonymous jars) — the signed CDN link in <video src> still works."""
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    try:
        page.wait_for_function(
            "() => { const v = document.querySelector('video'); "
            "return v && (v.currentSrc || v.src); }", timeout=30000)
    except Exception:
        return False
    rsleep(2, 4)  # let the player settle / sources populate
    src = page.evaluate(VIDEO_SRC_JS)
    if not src:
        return False
    resp = page.context.request.get(src, timeout=120000)
    if not resp.ok:
        print(f"warn: CDN GET {resp.status} for {url}")
        return False
    dest.write_bytes(resp.body())
    return True


def download_all(results: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [r for r in results
            if not (out_dir / f"{r['aweme_id']}.mp4").exists()]

    # plan A: yt-dlp with a cookie jar from OUR work profile (reuses
    # download_douyin.build_cookie_jar — currently 403s, kept for when the
    # extractor recovers; cheap to try once and disable for the batch)
    ytdlp_ok = False
    if todo:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from download_douyin import build_cookie_jar
        jar_path = out_dir / "cookies.txt"
        build_cookie_jar(PROFILE_DIR, jar_path)
        r = todo[0]
        dest = out_dir / f"{r['aweme_id']}.mp4"
        print(f"download (yt-dlp): {r['url']} -> {dest}")
        rc = subprocess.run(["yt-dlp", "--no-update", "--cookies",
                             str(jar_path), r["url"], "-o", str(dest),
                             "--no-playlist"]).returncode
        if rc == 0:
            ytdlp_ok = True
            todo.pop(0)
            rsleep()
        else:
            print("yt-dlp failed — switching to browser-sniff for the batch")

    if todo and ytdlp_ok:
        for r in list(todo):
            dest = out_dir / f"{r['aweme_id']}.mp4"
            print(f"download (yt-dlp): {r['url']} -> {dest}")
            subprocess.run(["yt-dlp", "--no-update", "--cookies",
                            str(jar_path), r["url"], "-o", str(dest),
                            "--no-playlist"], check=True)
            todo.remove(r)
            rsleep()

    if todo:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = launch(p, headless=True)
            page = ctx.new_page()
            try:
                for r in todo:
                    dest = out_dir / f"{r['aweme_id']}.mp4"
                    print(f"download (sniff): {r['url']} -> {dest}")
                    if sniff_download_one(page, r["url"], dest):
                        print(f"  ok ({dest.stat().st_size // 1024} KiB)")
                    else:
                        print(f"  FAILED: {r['url']}")
                    rsleep()
            finally:
                ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("keyword", nargs="?", help="search keyword")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--sort", choices=["default", "likes"], default="likes")
    ap.add_argument("--out", help="write results JSON here (default stdout)")
    ap.add_argument("--download", metavar="DIR",
                    help="download every result into DIR via yt-dlp")
    ap.add_argument("--smoke", action="store_true",
                    help="headed smoke test: open douyin.com, report login "
                         f"state, hold {SMOKE_HOLD_S}s, exit")
    args = ap.parse_args()
    if not args.smoke and not args.keyword:
        ap.error("keyword required unless --smoke")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        if args.smoke:
            ok = ensure_login(p, smoke=True)
            print(f"smoke result: browser opened douyin.com, "
                  f"login={'yes' if ok else 'no (anonymous)'}")
            return 0

        if not ensure_login(p):
            return 1
        results = search(p, args.keyword, args.limit, args.sort)

    payload = {"keyword": args.keyword, "sort": args.sort,
               "count": len(results), "results": results}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"results -> {args.out}")
    else:
        print(text)

    if args.download and results:
        download_all(results, Path(args.download))
    return 0


if __name__ == "__main__":
    sys.exit(main())
