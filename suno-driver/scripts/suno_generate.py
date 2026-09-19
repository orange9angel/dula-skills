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
import re
import sys
import time
from pathlib import Path

STORY = Path(__file__).resolve().parents[3] / 'dula-story'  # workspace 根下的内容仓库（修 parents 误指）
PROFILE = STORY / '.suno_profile'

STYLE_SELECTORS = [
    'div.css-9ekxdd textarea',  # Styles 区块容器（2026-09 实测）
    'textarea[placeholder="Enter style tags"]',
    'xpath=(//textarea)[2]',
    'textarea[placeholder*="style" i]', '[data-testid*="style" i] textarea',
]
LYRICS_SELECTORS = [  # 歌词框是 contenteditable div，不是 textarea
    'div.lyrics-editor-content[contenteditable="true"]',
    '[contenteditable="true"].lyrics-editor-content',
    'textarea[placeholder*="Start writing lyrics" i]',
    'textarea[placeholder="Describe your lyrics"]',
    'textarea[placeholder*="lyrics" i]',
]
TITLE_SELECTORS = [
    'input[placeholder="Song Title (Optional)"]', 'input[placeholder*="Song Title" i]',
]
CREATE_BUTTON_SELECTORS = [
    'button:has-text("Create")', '[data-testid*="create" i]',
]
CUSTOM_TOGGLE_SELECTORS = [  # 2026 UI: Custom 已改名为 Advanced
    'button:has-text("Advanced")', 'button:has-text("Custom")',
    '[role="tab"]:has-text("Advanced")', '[role="tab"]:has-text("Custom")',
]
INSTRUMENTAL_SELECTORS = [
    '[role="switch"][aria-label="Instrumental"]',
    'label:has-text("Instrumental")', 'button:has-text("Instrumental")',
]
COOKIE_SELECTORS = [
    'button:has-text("Accept All")', 'button:has-text("Accept")',
    'button:has-text("Allow all")', 'button:has-text("Got it")',
]


def dismiss_overlays(page):
    """关掉遮罩层（onboarding/导览/弹窗），否则它们会拦截点击。"""
    for _ in range(3):
        page.keyboard.press('Escape')
        page.wait_for_timeout(400)
        overlay = page.locator('div.fixed.inset-0')
        if not overlay.count():
            return
        for sel in ('div.fixed.inset-0 button[aria-label*="lose" i]',
                    'div.fixed.inset-0 button:has-text("Dismiss")',
                    'div.fixed.inset-0 button:has-text("Skip")',
                    'div.fixed.inset-0 button:has-text("×")',
                    'div.fixed.inset-0 [role="button"]:has-text("×")'):
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click()
                page.wait_for_timeout(500)
                break
        else:
            # 没有关闭按钮就点遮罩角落
            try:
                page.mouse.click(20, 20)
            except Exception:
                pass
        page.wait_for_timeout(400)


def log(msg):
    print(f'[suno] {msg}', flush=True)


def fill_first(page, selectors, value, what):
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() and loc.is_visible():
            loc.click()
            try:
                loc.fill(value)
            except Exception:
                # contenteditable 富文本编辑器对 fill 免疫时用键盘输入
                page.keyboard.insert_text(value)
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
    ap.add_argument('--title', help='歌曲标题（定位新卡用，建议中文名）')
    ap.add_argument('--out', type=Path, default=Path('.'))
    ap.add_argument('--timeout', type=int, default=300)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=False,  # Suno 有 Cloudflare 挑战，headless 会被拦
            viewport={'width': 1440, 'height': 900},
            args=['--disable-blink-features=AutomationControlled'])
        # cookie 双保险：profile 损坏/被 kill 时用导出的 cookies 恢复
        cookies_file = PROFILE / 'cookies.json'
        if cookies_file.exists() and not args.login:
            try:
                ctx.add_cookies(json.loads(cookies_file.read_text(encoding='utf-8')))
                log('cookies.json 已注入')
            except Exception as exc:
                log(f'cookies 注入失败（忽略）：{exc}')
        page = ctx.new_page()
        page.goto('https://suno.com/create', wait_until='domcontentloaded')

        if args.login:
            log('浏览器已打开。请手动登录 Suno 并进入 /create 页面。')
            log('（脚本每 5 秒自动检测登录态（找 "My Workspace"），最长等 10 分钟）')
            deadline = time.time() + 600
            ok = False
            while time.time() < deadline:
                page.wait_for_timeout(5000)
                if page.locator('text=My Workspace').count() > 0:
                    ok = True
                    log('检测到已登录（My Workspace 可见）')
                    break
                log('等待登录...')
            if not ok:
                log('超时未检测到登录')
                ctx.close()
                return 1
            # 双保险：profile 目录 + 显式导出 cookie（kill/异常退出后也能恢复）
            cookies = ctx.cookies('https://suno.com')
            (PROFILE / 'cookies.json').write_text(json.dumps(cookies), encoding='utf-8')
            log(f'cookies 已导出（{len(cookies)} 条）')
            ctx.close()
            log('会话已保存，之后可 headless 运行')
            return 0

        page.wait_for_timeout(4000)
        click_first(page, COOKIE_SELECTORS, 'cookie-consent')
        dismiss_overlays(page)

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

        # Advanced 模式：已在 Advanced 就别再点（再点会切回 Simple，字段消失）
        LYRICS_PROBE = 'div.lyrics-editor-content[contenteditable="true"], textarea[placeholder*="Start writing" i], textarea[placeholder*="Describe your lyrics" i]'
        try:
            page.wait_for_selector(LYRICS_PROBE, timeout=20000, state='attached')
            log('已在 Advanced 模式')
        except Exception:
            click_first(page, CUSTOM_TOGGLE_SELECTORS, 'custom-mode')
            try:
                page.wait_for_selector(LYRICS_PROBE, timeout=30000, state='attached')
            except Exception:
                pass

        # 标题：Advanced 面板的 Song Title，用于生成后定位新卡
        title = args.title or f'auto-{int(time.time())}'
        fill_first(page, TITLE_SELECTORS, title, 'title')

        if not fill_first(page, STYLE_SELECTORS, style, 'style'):
            page.screenshot(path=str(args.out / 'suno_fail_style.png'))
            log('style 填写失败，截图 suno_fail_style.png；请用 --probe 校准选择器')
            ctx.close()
            return 1

        if args.instrumental:
            click_first(page, INSTRUMENTAL_SELECTORS, 'instrumental')
        elif lyrics:
            if not fill_first(page, LYRICS_SELECTORS, lyrics, 'lyrics'):
                page.screenshot(path=str(args.out / 'suno_fail_lyrics.png'))
                ctx.close()
                return 1

        # 记录已有 clip uuid，生成后找新增
        def clip_uuids():
            srcs = page.locator('img[src*="suno.ai/image"]').evaluate_all(
                '(els)=>els.map(e=>e.getAttribute("src")||e.getAttribute("data-src")||"")')
            out = set()
            for s in srcs:
                m = re.search(r'image_(?:large_)?([0-9a-f-]{36})', s or '')
                if m:
                    out.add(m.group(1))
            return out

        before = clip_uuids()

        def try_create():
            """逐个候选按钮点；遮罩出现时先等它消失（可能是生成进度遮罩）；force 兜底。"""
            for sel in ['button[aria-label="Create song"]',
                        'xpath=(//button[contains(.,"Create")])[last()]',
                        'button:has-text("Create")']:
                loc = page.locator(sel).last
                if not (loc.count() and loc.is_visible()):
                    continue
                # 遮罩在的话先等它消（最多 15s），不消就 JS 点击绕过
                try:
                    page.wait_for_selector('div.fixed.inset-0', state='detached', timeout=15000)
                except Exception:
                    dismiss_overlays(page)
                try:
                    loc.click(timeout=8000)
                except Exception:
                    log(f'create: {sel} 常规点击被拦，JS 点击')
                    loc.evaluate('(e)=>e.click()')
                log(f'create: clicked via {sel}')
                for _ in range(4):
                    page.wait_for_timeout(5000)
                    if clip_uuids() - before:
                        return True
                    ov = page.locator('div.fixed.inset-0')
                    if ov.count():
                        txt = ov.first.inner_text()[:200].replace('\n', ' | ')
                        log(f'遮罩内容: {txt}')
                        # 可能是确认对话框：点里面的主按钮
                        for csel in ('div.fixed.inset-0 button:has-text("Create")',
                                     'div.fixed.inset-0 button:has-text("Generate")',
                                     'div.fixed.inset-0 button:has-text("Confirm")',
                                     'div.fixed.inset-0 button:has-text("Continue")'):
                            cl = page.locator(csel).last
                            if cl.count() and cl.is_visible():
                                cl.evaluate('(e)=>e.click()')
                                log(f'遮罩内确认: {csel}')
                                break
                        return True
                log(f'create: {sel} 点了没反应，试下一个')
            return False

        if not try_create():
            page.screenshot(path=str(args.out / 'suno_fail_create.png'))
            log('Create 提交失败，截图 suno_fail_create.png')
            ctx.close()
            return 1

        log('生成中（通常 30-120s）...')
        deadline = time.time() + args.timeout
        new_uuid = None
        while time.time() < deadline:
            page.wait_for_timeout(5000)
            new = clip_uuids() - before
            if new:
                new_uuid = sorted(new)[0]
                break
        if not new_uuid:
            page.screenshot(path=str(args.out / 'suno_fail_timeout.png'))
            log('超时未见新 clip')
            ctx.close()
            return 1
        log(f'新 clip: {new_uuid}，等音频就绪...')
        page.wait_for_timeout(20000)  # 卡片出现后音频还要渲染一会

        # 歌曲页 → More options → Download → WAV（生成未完时重试）
        args.out.mkdir(parents=True, exist_ok=True)
        page.goto(f'https://suno.com/song/{new_uuid}', wait_until='domcontentloaded')
        while time.time() < deadline:
            try:
                dismiss_overlays(page)
                page.locator('button[aria-label="More options"]').first.click()
                page.wait_for_timeout(1000)
                page.locator('text=Download').first.click()
                page.wait_for_timeout(1200)
                wav = page.locator('button:has-text("WAV"), [role="menuitem"]:has-text("WAV"), div[role="button"]:has-text("WAV")').first
                wav.click()
                page.wait_for_timeout(800)
                # 选完格式后可能需要确认（"Unlock & Download" 或主按钮）
                for csel in ('button:has-text("Unlock & Download")',
                             'button:has-text("Unlock and Download")',
                             'div.fixed.inset-0 button:has-text("Download")',
                             '[role="dialog"] button:has-text("Download")'):
                    cl = page.locator(csel).last
                    if cl.count() and cl.is_visible():
                        cl.click()
                        log(f'确认下载: {csel}')
                        break
                # 等浏览器下载事件
                di = page.expect_download(timeout=30000)
                with di:
                    pass
                d = di.value
                target = args.out / f'{title}.wav'
                d.save_as(str(target))
                log(f'downloaded: {target}')
                ctx.close()
                return 0
            except Exception as exc:
                log(f'下载重试中（{type(exc).__name__}）…')
                page.wait_for_timeout(15000)
                page.reload(wait_until='domcontentloaded')
                page.wait_for_timeout(4000)
        page.screenshot(path=str(args.out / 'suno_fail_download.png'))
        log('下载最终失败（截图 suno_fail_download.png）')
        ctx.close()
        return 1


if __name__ == '__main__':
    sys.exit(main())
