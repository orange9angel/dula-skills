#!/usr/bin/env python3
"""Download a Douyin video from a share link (e.g. https://v.douyin.com/xxx/).

Douyin's web XHR needs fresh anti-bot cookies; yt-dlp's extractor needs a
Netscape cookie jar with real values. Chrome >= 127 encrypts cookies with
app-bound (v20) keys that only Chrome itself can decrypt, so this script:

1. copies the minimal Chrome profile (Local State + Default/Network/Cookies)
   to a temp dir (the real profile dir blocks CDP: "DevTools remote debugging
   requires a non-default data directory"; and is locked while Chrome runs —
   close Chrome/Edge first);
2. launches REAL chrome.exe headless via playwright persistent context on the
   copied profile (same exe path -> app-bound cookies decrypt fine);
3. reads cookies via CDP and saves a MozillaCookieJar (yt-dlp rejects
   hand-rolled Netscape files with negative/odd expires — always go through
   MozillaCookieJar);
4. runs yt-dlp with that jar.

Usage (from dula-story):
  .venv/Scripts/python.exe <this> "https://v.douyin.com/xxxx/" -o tmp/douyin/out.mp4

NOTE: profile copy works because app-bound decryption keys off the exe path,
not the profile path. If Chrome updates break this, the fallback is asking the
user to 保存本地 from the mobile app.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path

CHROME_PROFILE = Path(r"C:\Users\orang\AppData\Local\Google\Chrome\User Data")
COPY_DIR = Path("tmp/chrome_profile_copy")


def build_cookie_jar(profile_copy: Path, jar_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile_copy.resolve()), channel="chrome", headless=True,
            timeout=120000)
        page = ctx.new_page()
        # douyin.com sets fresh anti-bot cookies on any page load
        page.goto("https://www.douyin.com/", wait_until="commit", timeout=90000)
        time.sleep(8)
        cookies = ctx.cookies()
        ctx.close()

    jar = MozillaCookieJar(str(jar_path))
    for c in cookies:
        jar.set_cookie(Cookie(
            version=0, name=c["name"], value=c["value"], port=None,
            port_specified=False, domain=c["domain"],
            domain_specified=c["domain"].startswith("."),
            domain_initial_dot=c["domain"].startswith("."),
            path=c.get("path", "/"), path_specified=True,
            secure=bool(c.get("secure")),
            expires=int(c.get("expires", 0) or 0) or None,
            discard=False, comment=None, comment_url=None, rest={},
            rfc2109=False))
    jar.save(ignore_discard=True, ignore_expires=True)
    print(f"cookies: {len(cookies)} -> {jar_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="douyin share link or video URL")
    parser.add_argument("-o", "--out", required=True, help="output .mp4 path")
    parser.add_argument("--jar", default="tmp/douyin/cookies.txt")
    args = parser.parse_args()

    # 1. minimal profile copy (idempotent refresh of the two files that matter)
    for rel in ["Local State", "Default/Network/Cookies"]:
        src = CHROME_PROFILE / rel
        dst = COPY_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

    # 2-3. fresh cookie jar via headless real Chrome on the copy
    build_cookie_jar(COPY_DIR, Path(args.jar))

    # 4. yt-dlp download
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["yt-dlp", "--no-update", "--cookies", args.jar,
                    args.url, "-o", str(out), "--no-playlist"], check=True)
    print(f"downloaded -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
