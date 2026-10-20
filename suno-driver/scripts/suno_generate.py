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
    ap.add_argument('--headed', action='store_true', help='显示浏览器窗口（默认无头后台运行）')
    ap.add_argument('--restore-cookies', action='store_true', help='显式从备份恢复 cookie；正常使用持久 profile，避免旧备份覆盖新登录')
    ap.add_argument('--probe', action='store_true', help='探测页面结构')
    ap.add_argument('--library-probe', action='store_true', help='只检查作品筛选和现有生成结果，不提交生成')
    ap.add_argument('--download-id', help='仅下载账号内已有曲目的播放音频，不提交生成')
    ap.add_argument('--create-voice', help='建档声音克隆：<名称>（配合 --voice-file）')
    ap.add_argument('--voice-file', type=Path, help='声音克隆参考音频（wav/mp3）')
    ap.add_argument('--voice', help='生成时使用的已建档 Voice 名称')
    ap.add_argument('--style', default='')
    ap.add_argument('--style-file')
    ap.add_argument('--lyrics-file')
    ap.add_argument('--instrumental', action='store_true')
    ap.add_argument('--count', type=int, default=2)
    ap.add_argument('--title', help='歌曲标题（定位新卡用，建议中文名）')
    ap.add_argument('--out', type=Path, default=Path('.'))
    ap.add_argument('--timeout', type=int, default=300)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        # 默认无头后台运行；--login/--headed 才开窗口。
        # Cloudflare 拦无头时下方 goto 后会检测挑战文本并给出指引。
        headless = not args.login and not args.headed
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=headless,
            viewport={'width': 1440, 'height': 900},
            args=['--disable-blink-features=AutomationControlled'])
        # cookie 双保险：profile 损坏/被 kill 时用导出的 cookies 恢复
        cookies_file = PROFILE / 'cookies.json'
        if cookies_file.exists() and args.restore_cookies and not args.login:
            try:
                ctx.add_cookies(json.loads(cookies_file.read_text(encoding='utf-8')))
                log('cookies.json 已注入')
            except Exception as exc:
                log(f'cookies 注入失败（忽略）：{exc}')
        page = ctx.new_page()
        receipts=[]
        failures=[]
        def capture_result(response):
            url=response.url
            if response.status>=400 and any(host in url for host in ['suno.com/','suno.ai/']):
                from urllib.parse import urlsplit
                parts=urlsplit(url)
                failures.append({'status':response.status,'method':response.request.method,'endpoint':parts.netloc+parts.path})
                (args.out/'request_failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
            if response.request.method!='POST' or not re.search(r'/generate(?:/|\?|$)',url):return
            try:
                data=response.json()
                clips=data.get('clips',[]) if isinstance(data,dict) else []
                receipt={'status':response.status,'ids':[c['id'] for c in clips if isinstance(c,dict) and c.get('id')],
                         'detail':str(data.get('detail',data.get('error','')))[:600] if isinstance(data,dict) else ''}
                receipts.append(receipt)
                (args.out/'generation_receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
                log('Generation response: '+json.dumps(receipt))
            except Exception:pass
        page.on('response',capture_result)
        page.goto('https://suno.com/create', wait_until='domcontentloaded')
        # Cloudflare 挑战检测（无头模式易被拦）：命中则提示改用 --headed
        page.wait_for_timeout(2500)
        if page.locator('text=/verify you are human|just a moment|checking your browser/i').count():
            ctx.close()
            sys.exit('Cloudflare 挑战拦截了无头模式：先用 --headed 跑一次通过挑战（会话会记住），'
                     '或改 --headed 运行本次。')
        log(f'浏览器模式: {"headless" if headless else "headed"}')

        if args.login:
            log('浏览器已打开。请手动登录 Suno 并进入 /create 页面。')
            log('（脚本每 5 秒检查全部 Suno 标签页的创作界面，最长等 10 分钟）')
            deadline = time.time() + 600
            ok = False
            while time.time() < deadline:
                page.wait_for_timeout(5000)
                candidates=[tab for tab in ctx.pages if not tab.is_closed() and 'suno.com' in tab.url]
                active=next((tab for tab in candidates if tab.locator('div.lyrics-editor-content[contenteditable="true"], textarea[placeholder*="song" i], textarea[placeholder*="style" i]').count() or tab.get_by_text('My Workspace',exact=True).count()),None)
                if active is not None:
                    page=active
                    ok = True
                    log('检测到已登录（创作界面可见）')
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
        if ('sign-in' in page.url or 'login' in page.url
                or page.get_by_text('Welcome to Suno', exact=True).count()):
            args.out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.out / 'suno_login_required.png'))
            log('登录态已失效：请运行 --login 手动登录；未提交歌曲生成。')
            ctx.close()
            return 3
        click_first(page, COOKIE_SELECTORS, 'cookie-consent')
        dismiss_overlays(page)

        # Persist refreshed state only after the login-page guard has passed.
        cookies_file.write_text(json.dumps(ctx.cookies('https://suno.com')), encoding='utf-8')

        if args.create_voice:
            if not args.voice_file or not args.voice_file.exists():
                log('--create-voice 需要 --voice-file 指向存在的音频')
                ctx.close()
                return 2
            page.keyboard.press('Escape')
            click_first(page, ['button:has-text("Voice")'], 'voice-dialog')
            page.wait_for_timeout(1200)
            click_first(page, ['text=Create Voice'], 'create-voice')
            page.wait_for_timeout(1200)
            click_first(page, ['button:has-text("Upload Audio")'], 'upload-audio')
            page.wait_for_timeout(800)
            fi = page.locator('input[type=file]').first
            # 上传链路观测（P3 校准）：记录 upload/clips 相关响应状态码
            page.on('response', lambda r: log(f'net {r.status} {r.url[:110]}')
                    if any(k in r.url for k in ('upload', 'clip', 'voice')) else None)
            fi.set_input_files(str(args.voice_file))
            log('音频已上传，等 upload-finish 响应...')
            # v6 上传流程（P3 校准两轮实录）：①Continue 在未选内容类型时一直禁用，
            # 等它没用；②上传完成后再点 Voice 芯片，Continue 才解锁。顺序错=回拖放区。
            try:
                page.wait_for_event('response', predicate=lambda r: 'upload-finish' in r.url,
                                    timeout=60000)
            except Exception:
                log('60s 未见 upload-finish——上传未完成')
                args.out.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(args.out / 'voice_upload_stall.png'))
                ctx.close()
                return 2
            # 选内容类型 Voice 芯片（与页面顶部 Voice 入口同文，限定在对话框内点）
            click_first(page, ['div.fixed.inset-0 button:has-text("Voice")',
                               '[role="dialog"] button:has-text("Voice")',
                               'div.fixed.inset-0 :text-is("Voice")'], 'upload-kind-voice')
            page.wait_for_timeout(1200)
            try:
                page.wait_for_function(
                    "() => { const dlg=document.querySelector('div.fixed.inset-0,[role=dialog]');"
                    " if(!dlg) return false;"
                    " const b=[...dlg.querySelectorAll('button')].find(x=>/Continue/i.test(x.innerText));"
                    " return b && !b.disabled; }", timeout=15000)
            except Exception:
                log('选片后 Continue 仍未解锁')
            click_first(page, ['div.fixed.inset-0 button:has-text("Continue")',
                               '[role="dialog"] button:has-text("Continue")',
                               'button:has-text("Continue"):visible'], 'upload-continue')
            log('内容类型已提交（Voice），等待建档处理...')
            page.wait_for_timeout(10000)
            # v6 正解（P3 JS 逆工程）：上传成 clip 后关对话框，在 clip 卡片的
            # More options 菜单里点 Voice（songActions.voice）才进命名弹层。
            # "Select from library" 是选既有歌的旁路，上传件不在 Songs 列表。
            log('上传已成 clip——关对话框走卡片菜单 Voice 入口')
            page.keyboard.press('Escape')
            page.wait_for_timeout(1500)
            clip_title = args.voice_file.stem
            card = page.locator(f'div:has(> *:text-is("{clip_title}"))').last
            try:
                btn = page.locator('button[aria-label="More options"]').first
                card.hover()
                page.wait_for_timeout(600)
                card.locator('button[aria-label="More options"]').click()
                log('卡片 More options 已开')
            except Exception:
                log('卡片菜单定位失败，试全局第一个 More options')
                page.locator('button[aria-label="More options"]').first.click()
            page.wait_for_timeout(1000)
            click_first(page, ['[role="menuitem"]:has-text("Voice")', 'text=Voice'], 'card-menu-voice')
            page.wait_for_timeout(2000)
            named = fill_first(page, ['div.fixed.inset-0 input[placeholder*="name" i]',
                                      '[role="dialog"] input[placeholder*="name" i]',
                                      'input[placeholder*="name" i]:visible',
                                      'input[type="text"]:visible'], args.create_voice, 'voice-name')
            if not named:
                log('卡片 Voice 路径仍无命名框')
                click_first(page, ['div.fixed.inset-0 button:has-text("Select from library")',
                                   '[role="dialog"] button:has-text("Select from library")',
                                   'button:has-text("Select from library"):visible'], 'pick-from-library')
                page.wait_for_timeout(3000)
                clip_name = args.voice_file.stem
                # 先搜索框过滤（上传件可能不在默认序前列——P3 实录）
                sb = page.locator('div.fixed.inset-0 input[placeholder*="Search" i], '
                                  '[role="dialog"] input[placeholder*="Search" i]').first
                if sb.count() and sb.is_visible():
                    sb.fill(clip_name)
                    log(f'库选择器内搜索: {clip_name}')
                    page.wait_for_timeout(2000)
                args.out.mkdir(parents=True, exist_ok=True)
                (args.out / 'voice_library_probe.txt').write_text(
                    chr(10).join(page.locator('[role="dialog"],div.fixed.inset-0')
                                 .evaluate_all('(els)=>els.map(e=>e.innerText)')), encoding='utf-8')
                page.screenshot(path=str(args.out / 'voice_library_probe.png'))
                pick = page.locator(f'div.fixed.inset-0 :text-is("{clip_name}"), '
                                    f'[role="dialog"] :text-is("{clip_name}")').last
                if pick.count() and pick.is_visible():
                    pick.click()
                    log(f'库中选中上传件: {clip_name}')
                    page.wait_for_timeout(2500)
                    named = fill_first(page, ['div.fixed.inset-0 input[placeholder*="name" i]',
                                              '[role="dialog"] input[placeholder*="name" i]',
                                              'input[placeholder*="name" i]:visible',
                                              'input[type="text"]:visible'],
                                       args.create_voice, 'voice-name')
            if not named:
                # 命名框漂移即停：盲点是/否按钮会提交无名 voice 或点到禁用件（P3 实录）。
                # 落盘对话框结构供校准，不继续。
                args.out.mkdir(parents=True, exist_ok=True)
                dump = {'inputs': page.locator('input').evaluate_all(
                            '(els)=>els.map(e=>({ph:e.placeholder||"",type:e.type||"",vis:!!e.offsetParent,dis:e.disabled}))'),
                        'buttons': page.locator('button').evaluate_all(
                            '(els)=>els.filter(e=>e.offsetParent).map(e=>({t:e.innerText.trim(),dis:e.disabled})).slice(0,40)'),
                        'texts': page.locator('[role="dialog"],div.fixed.inset-0').evaluate_all(
                            '(els)=>els.map(e=>e.innerText.trim().slice(0,400))')}
                (args.out / 'voice_dialog_probe.json').write_text(json.dumps(dump, ensure_ascii=False, indent=2))
                page.screenshot(path=str(args.out / 'voice_dialog_probe.png'))
                log('命名框未找到：已落盘 voice_dialog_probe.json/.png 供校准，未提交')
                ctx.close()
                return 2
            for sel in ('button:has-text("Save")', 'button:has-text("Create")',
                        'button:has-text("Done")', 'button:has-text("Confirm")'):
                loc = page.locator(sel).last
                if loc.count() and loc.is_visible():
                    loc.click()
                    log(f'保存 voice: {sel}')
                    break
            page.wait_for_timeout(4000)
            page.screenshot(path=str(args.out / f'voice_{args.create_voice}.png'))
            ctx.close()
            return 0

        if args.download_id:
            if not re.fullmatch(r'[0-9a-f-]{36}',args.download_id):raise ValueError('Invalid song id')
            song_media=[]
            def collect_song_media(response):
                if args.download_id in response.url and '.mp3' in response.url:song_media.append(response.url)
                if 'json' not in response.headers.get('content-type',''):return
                if not any(x in response.url for x in ('clip','feed','song')):return
                try:
                    def visit(value):
                        if isinstance(value,dict):
                            if value.get('id')==args.download_id and value.get('audio_url'):song_media.append(value['audio_url'])
                            for child in value.values():visit(child)
                        elif isinstance(value,list):
                            for child in value:visit(child)
                    visit(response.json())
                except Exception:pass
            page.on('response',collect_song_media)
            page.goto('https://suno.com/song/'+args.download_id,wait_until='domcontentloaded')
            page.wait_for_timeout(7000)
            metadata=page.locator('body').inner_text()[:9000]
            sources=page.locator('audio').evaluate_all('(els)=>els.map(e=>e.currentSrc||e.src).filter(Boolean)')
            # The initial audio element contains sil-100.mp3, a silent player
            # placeholder. Only the requested song's actual media is evidence.
            if not any(args.download_id in s for s in sources):
                for sel in ['button[aria-label="Play"]','button[aria-label*="Play song"]']:
                    loc=page.locator(sel).first
                    if loc.count():loc.click();page.wait_for_timeout(1800);break
                for _ in range(15):
                    sources=page.locator('audio').evaluate_all('(els)=>els.map(e=>e.currentSrc||e.src).filter(Boolean)')+song_media
                    if any(args.download_id in s and 'sil-100' not in s for s in sources):break
                    page.wait_for_timeout(1000)
            source=next((s for s in sources if args.download_id in s and 'sil-100' not in s),None)
            if not source:
                # v6 can expose a blob player plus audio_url=/api/forbidden.
                # Use the authorized download dialog, never reconstruct/decode
                # protected player media. Unlock consumes the account's download allowance.
                try:
                    page.get_by_role('button',name='More options',exact=True).first.click()
                    page.get_by_role('menuitem',name='Download',exact=True).hover()
                    dialog=page.get_by_role('dialog').filter(has_text='Download').first
                    dialog.wait_for(state='visible',timeout=10000)
                    dialog.get_by_role('button',name='WAV',exact=True).click()
                    confirm=dialog.get_by_role('button',name=re.compile(r'^(Unlock & Download|Download)$')).first
                    with page.expect_download(timeout=max(120000,args.timeout*1000)) as pending:
                        confirm.click()
                    dl=pending.value
                    target=args.out/((args.title or args.download_id)+'.wav');dl.save_as(str(target))
                    if dl.failure():raise RuntimeError(dl.failure())
                    import hashlib,subprocess
                    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(target)]))
                    if float(probe['format']['duration'])<1:raise RuntimeError('Downloaded audio is empty')
                    target.with_suffix('.source.json').write_text(json.dumps({'provider':'Suno','song_id':args.download_id,
                        'song_url':'https://suno.com/song/'+args.download_id,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                        'download_kind':'authorized UI WAV download','duration':float(probe['format']['duration'])},ensure_ascii=False,indent=2),encoding='utf-8')
                    log('Downloaded authorized WAV: '+str(target));ctx.close();return 0
                except Exception as exc:
                    page.screenshot(path=str(args.out/'authorized_download_failed.png'))
                    (args.out/'authorized_download_status.json').write_text(json.dumps({
                        'status':'not-confirmed','error':type(exc).__name__,
                        'detail':str(exc).splitlines()[0][:240],
                        'dialogs':page.locator('[role="dialog"]').all_inner_texts()},ensure_ascii=False,indent=2),encoding='utf-8')
                    log('Authorized download UI did not complete: '+type(exc).__name__+'; use the existing normal browser session if needed.')
                (args.out/'download_probe.json').write_text(json.dumps({'text':metadata,'buttons':page.locator('button').evaluate_all('(els)=>els.map(e=>({text:e.innerText,aria:e.getAttribute("aria-label")}))')},ensure_ascii=False,indent=2),encoding='utf-8')
                ctx.close();return 4
            from urllib.parse import urlsplit
            parsed=urlsplit(source);host=parsed.hostname or ''
            if parsed.scheme!='https' or not (host.endswith('.suno.com') or host.endswith('.suno.ai')):raise RuntimeError('Unexpected audio source host')
            response=ctx.request.get(source)
            if response.status!=200:raise RuntimeError('Audio download status '+str(response.status))
            payload=response.body()
            if len(payload)<100000:raise RuntimeError('Audio response is implausibly short; refusing placeholder')
            target=args.out/((args.title or args.download_id)+'.mp3');target.write_bytes(payload)
            import hashlib
            target.with_suffix('.source.json').write_text(json.dumps({'provider':'Suno','song_id':args.download_id,'song_url':'https://suno.com/song/'+args.download_id,'audio_source':source,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'download_kind':'existing library song; not generated during this run'},ensure_ascii=False,indent=2),encoding='utf-8')
            log('Downloaded existing song playback audio: '+str(target));ctx.close();return 0
        if args.library_probe:
            button=page.locator('button:has-text("Filters")')
            log('Filters controls: '+str(button.count()))
            if button.count():button.first.click();page.wait_for_timeout(1500)
            data={'text':page.locator('body').inner_text()[:24000],
              'controls':page.locator('input,button,[role="checkbox"],[role="switch"]').evaluate_all('(els)=>els.filter(e=>e.offsetParent).map(e=>({tag:e.tagName,role:e.getAttribute("role"),text:e.innerText,aria:e.getAttribute("aria-label"),checked:e.getAttribute("aria-checked"),type:e.type,placeholder:e.placeholder}))')}
            (args.out/'library_probe.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            ctx.close();return 0
        if args.probe:
            dump = {
                'url': page.url,
                'textareas': page.locator('textarea').evaluate_all(
                    '(els)=>els.map(e=>({ph:e.placeholder,name:e.name,id:e.id,testid:e.getAttribute("data-testid")}))'),
                'buttons': page.locator('button').evaluate_all(
                    '(els)=>els.filter(e=>e.offsetParent).map(e=>e.innerText.trim()).filter(Boolean).slice(0,60)'),
                'toggles': page.locator('[role="switch"],[role="tab"],[role="checkbox"]').evaluate_all(
                    '(els)=>els.map(e=>e.innerText.trim()||e.getAttribute("aria-label")||"").slice(0,40)'),
                'body_text':page.locator('body').inner_text()[:18000],
                'song_links':page.locator('a[href*="/song/"]').evaluate_all('(els)=>els.map(e=>e.getAttribute("href")).slice(0,60)'),
                'image_sources':page.locator('img').evaluate_all('(els)=>els.map(e=>e.getAttribute("src")).filter(Boolean).slice(0,80)'),
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

        # The persistent create page may reopen in Speech or Sounds. Select the
        # actual product mode before looking for the song's Advanced editor.
        songs = page.get_by_role('tab', name='Songs', exact=True)
        if songs.count() and songs.first.is_visible():
            songs.first.click()
            page.wait_for_timeout(800)
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
            # Current v6 explicitly labels an empty lyric editor as instrumental.
            if page.get_by_text('Start writing lyrics, or leave this empty for instrumental',exact=False).count():
                fill_first(page,LYRICS_SELECTORS,'','instrumental-empty-lyrics')
            else:
                click_first(page, INSTRUMENTAL_SELECTORS, 'instrumental')
        elif lyrics:
            if not fill_first(page, LYRICS_SELECTORS, lyrics, 'lyrics'):
                page.screenshot(path=str(args.out / 'suno_fail_lyrics.png'))
                ctx.close()
                return 1

        if args.voice:
            page.keyboard.press('Escape')
            click_first(page, ['button:has-text("Voice")'], 'voice-dialog')
            page.wait_for_timeout(1200)
            v = page.locator(f'text={args.voice}').first
            if v.count():
                v.click()
                log(f'voice 已选: {args.voice}')
                page.keyboard.press('Escape')
                page.wait_for_timeout(500)
            else:
                log(f'voice "{args.voice}" 未找到（需先 --create-voice 建档）')
                ctx.close()
                return 1

        # 记录已有 clip uuid，生成后找新增
        def clip_uuids():
            receipt_ids={i for receipt in receipts for i in receipt.get('ids',[])}
            srcs = page.locator('img[src*="suno.ai/image"]').evaluate_all(
                '(els)=>els.map(e=>e.getAttribute("src")||e.getAttribute("data-src")||"")')
            out = set(receipt_ids)
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
                    if page.get_by_text('Generation failed',exact=True).count():
                        page.screenshot(path=str(args.out/'suno_generation_failed.png'))
                        log('页面明确返回 Generation failed；停止，不重复提交。')
                        return False
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
                        # An overlay is not a job receipt. Stop after this one
                        # submission if no clip id has actually been returned.
                        page.wait_for_timeout(2500)
                        return bool(clip_uuids()-before)
                log(f'create: {sel} 已点击但未确认，停止以免重复提交')
                return False
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
            if page.get_by_text('Generation failed',exact=True).count():
                page.screenshot(path=str(args.out/'suno_generation_failed.png'))
                log('页面明确返回 Generation failed；停止等待。')
                ctx.close()
                return 1
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
                # 选完格式后可能需要确认（"Unlock & Download" 或主按钮）。
                # 注意：expect_download 必须包住"触发下载的那次点击"，
                # 先点后等会错过事件（原 AttributeError 的根因）。
                confirm_sel = None
                for csel in ('button:has-text("Unlock & Download")',
                             'button:has-text("Unlock and Download")',
                             'div.fixed.inset-0 button:has-text("Download")',
                             '[role="dialog"] button:has-text("Download")'):
                    cl = page.locator(csel).last
                    if cl.count() and cl.is_visible():
                        confirm_sel = csel
                        break
                with page.expect_download(timeout=30000) as dl_info:
                    if confirm_sel:
                        page.locator(confirm_sel).last.click()
                        log(f'确认下载: {confirm_sel}')
                    else:
                        # 无确认对话框：WAV 项本身就是触发，补点一次
                        page.locator('button:has-text("WAV"), [role="menuitem"]:has-text("WAV"), div[role="button"]:has-text("WAV")').first.click()
                d = dl_info.value
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
