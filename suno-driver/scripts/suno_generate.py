#!/usr/bin/env python3
"""Suno 网页版自动化驱动（Playwright 持久会话）。

没有公开 API，这是对自己付费账号的低频自用自动化（灰色地带，见 SKILL.md）。

用法：
  首次登录（弹真实浏览器，手动登录后回车关闭）：
    suno_generate.py --login
  探测页面结构（选择器校准用）：
    suno_generate.py --probe
  生成：
    suno_generate.py --style "..." --lyrics-file lyrics.txt --out outdir --count 2
    suno_generate.py --style "..." --instrumental --out outdir

会话档案存 dula-story/.suno_profile（已 gitignore）。
Run: dula-story/.venv/Scripts/python.exe
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

STORY = Path(__file__).resolve().parents[3]
PROFILE = STORY / '.suno_profile'

STYLE_SELECTORS = [
    'textarea[placeholder*="style" i]', 'textarea[placeholder*="Style"]',
    'textarea[name*="style" i]', '[data-testid*="style" i] textarea',
    'textarea[placeholder*="describe" i]',
]
LYRICS_SELECTORS = [
    'textarea[placeholder*="lyrics" i]', 'textarea[placeholder*="Lyrics"]',
    'textarea[name*="lyrics" i]', '[data-testid*="lyric" i] textarea',
]
CREATE_BUTTON_SELECTORS = [
    'button:has-text("Create")', '[data-testid*="create" i]',
]
CUSTOM_TOGGLE_SELECTORS = [
    'button:has-text("Custom")', '[role="tab"]:has-text("Custom")',
    'label:has-text("Custom")',
]
INSTRUMENTAL_SELECTORS = [
    'label:has-text("Instrumental")', 'button:has-text("Instrumental")',
    '[data-testid*="instrumental" i]',
]


def log(msg):
    print(f'[suno] {msg}', flush=True)


def fill_first(page, selectors, value, what):
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() and loc.is_visible():
            loc.click()
            loc.fill(value)
            log(f'{what}: filled via {sel}')
            return True
    log(f'{what}: NOT FOUND (tried {len(selectors)} selectors)')
    return False


def click_first(page, selectors, what):
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() and loc.is_visible():
            loc.click()
            log(f'{what}: clicked via {sel}')
            return True
    log(f'{what}: NOT FOUND')
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--login', action='store_true', help='headed 登录后退出')
    ap.add_argument('--probe', action='store_true', help='探测页面结构')
    ap.add_argument('--style', default='')
    ap.add_argument('--style-file')
    ap.add_argument('--lyrics-file')
    ap.add_argument('--instrumental', action='store_true')
    ap.add_argument('--count', type=int, default=2)
    ap.add_argument('--out', type=Path, default=Path('.'))
    ap.add_argument('--timeout', type=int, default=300)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=not (args.login or args.probe),
            viewport={'width': 1440, 'height': 900},
            args=['--disable-blink-features=AutomationControlled'])
        page = ctx.new_page()
        page.goto('https://suno.com/create', wait_until='domcontentloaded')

        if args.login:
            log('浏览器已打开。请手动登录 Suno（可用 Google/Discord 等）。')
            input('登录完成并进入 /create 页面后，回到这里按回车关闭...')
            ctx.close()
            log('会话已保存到 .suno_profile，之后可 headless 运行')
            return 0

        page.wait_for_timeout(4000)
        if args.probe:
            dump = {
                'url': page.url,
                'textareas': page.locator('textarea').evaluate_all(
                    '(els)=>els.map(e=>({ph:e.placeholder,name:e.name,id:e.id,testid:e.getAttribute("data-testid")}))'),
                'buttons': page.locator('button').evaluate_all(
                    '(els)=>els.filter(e=>e.offsetParent).map(e=>e.innerText.trim()).filter(Boolean).slice(0,60)'),
                'toggles': page.locator('[role="switch"],[role="tab"],[role="checkbox"]').evaluate_all(
                    '(els)=>els.map(e=>e.innerText.trim()||e.getAttribute("aria-label")||"").slice(0,40)'),
            }
            page.screenshot(path=str(args.out / 'suno_probe.png'), full_page=False)
            (args.out / 'suno_probe.json').write_text(json.dumps(dump, ensure_ascii=False, indent=2))
            log(f'probe written: {args.out}/suno_probe.json + suno_probe.png')
            ctx.close()
            return 0

        style = args.style
        if args.style_file:
            style = Path(args.style_file).read_text(encoding='utf-8-sig').strip()
        lyrics = None
        if args.lyrics_file:
            lyrics = Path(args.lyrics_file).read_text(encoding='utf-8-sig').strip()
        if not style:
            log('--style 或 --style-file 必填')
            return 2

        # Custom 模式
        click_first(page, CUSTOM_TOGGLE_SELECTORS, 'custom-mode')
        page.wait_for_timeout(800)

        if not fill_first(page, STYLE_SELECTORS, style, 'style'):
            page.screenshot(path=str(args.out / 'suno_fail_style.png'))
            log('style 填写失败，截图 suno_fail_style.png；请用 --probe 校准选择器')
            ctx.close()
            return 1

        if args.instrumental:
            click_first(page, INSTRUMENTAL_SELECTORS, 'instrumental')
        elif lyrics:
            fill_first(page, LYRICS_SELECTORS, lyrics, 'lyrics')

        if not click_first(page, CREATE_BUTTON_SELECTORS, 'create'):
            page.screenshot(path=str(args.out / 'suno_fail_create.png'))
            log('Create 按钮未找到，截图 suno_fail_create.png')
            ctx.close()
            return 1

        # 等生成：轮询工作区新卡片直到音频就绪
        log('生成中（通常 30-90s）...')
        deadline = time.time() + args.timeout
        args.out.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        while time.time() < deadline and downloaded < args.count:
            page.wait_for_timeout(8000)
            # 找最新卡片里的进度指示消失后，打开菜单下载 WAV
            menus = page.locator('button[aria-label*="more" i], button:has-text("⋯"), [data-testid*="menu" i]')
            if menus.count() > 0:
                try:
                    menus.first.click()
                    page.wait_for_timeout(800)
                    dl = page.locator('[role="menuitem"]:has-text("WAV"), a:has-text("WAV"), button:has-text("WAV")')
                    if dl.count() and dl.first.is_visible():
                        with page.expect_download(timeout=30000) as dl_info:
                            dl.first.click()
                        path = dl_info.value
                        target = args.out / f'suno_{int(time.time())}_{downloaded}.wav'
                        path.save_as(str(target))
                        log(f'downloaded: {target}')
                        downloaded += 1
                        page.keyboard.press('Escape')
                        continue
                except Exception as exc:
                    log(f'download attempt: {exc}')
        ctx.close()
        if downloaded < args.count:
            log(f'只拿到 {downloaded}/{args.count}，可能选择器需校准（--probe）')
            return 1
        return 0


if __name__ == '__main__':
    sys.exit(main())
