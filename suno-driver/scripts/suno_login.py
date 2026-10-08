# Suno 自动登录：把会话写进持久 profile（供 suno_generate.py 无头使用）。
# 凭据走环境变量 SUNO_EMAIL / SUNO_PASSWORD（Google 账号），不落盘。
# Suno 无邮箱+密码登录，只能 OAuth；本脚本走 Google 通道自动填表。
# 注意：Google 会拒绝无头自动化（/v3/signin/rejected），请用默认 headed 运行——
# 脚本会自动填完邮箱和密码，只在需要额外验证时才需要人工接管窗口。
# SUNO_HEADLESS=1 可强制无头（仅当 Google 段预期能过，如已有会话续期）。
import json
import os
import sys
import time
from pathlib import Path

STORY = Path(__file__).resolve().parents[3] / 'dula-story'  # 与 suno_generate.py 同约定
PROFILE = STORY / '.suno_profile'

def log(m):
    print(f'[suno-login] {m}', flush=True)

def main():
    email, password = os.environ.get('SUNO_EMAIL'), os.environ.get('SUNO_PASSWORD')
    headless = os.environ.get('SUNO_HEADLESS') == '1'
    if not email or not password:
        sys.exit('需要 SUNO_EMAIL / SUNO_PASSWORD 环境变量')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=headless,
            viewport={'width': 1440, 'height': 900},
            args=['--disable-blink-features=AutomationControlled'])
        page = ctx.new_page()
        page.goto('https://suno.com/create', wait_until='domcontentloaded')
        page.wait_for_timeout(3000)

        def creation_ui(tab):
            return (tab.locator('div.lyrics-editor-content[contenteditable="true"], textarea[placeholder*="song" i], textarea[placeholder*="style" i]').count()
                    or tab.get_by_text('My Workspace', exact=True).count())

        def find_logged_in():
            for tab in ctx.pages:
                if not tab.is_closed() and 'suno.com' in tab.url and creation_ui(tab):
                    return tab
            return None

        if find_logged_in():
            log('会话仍有效，无需登录')
        else:
            log('尝试自动登录…')
            try:
                page.goto('https://suno.com', wait_until='domcontentloaded')
                page.wait_for_timeout(2500)
                for sel in ('button:has-text("Accept All")', 'button:has-text("Accept")'):
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.click(); page.wait_for_timeout(600); break
                # 打开登录表单（wait_for_selector 在本页不稳定，直接 JS 按文本点击）
                clicked = page.evaluate('''()=>{
                    const els=[...document.querySelectorAll('button,a')];
                    const el=els.find(e=>e.offsetParent&&(e.innerText||'').trim()==='Log in');
                    if(el){el.click();return true;}return false;}''')
                log('登录入口 JS 点击: ' + ('成功' if clicked else '未找到'))
                page.wait_for_timeout(2500)
                page.screenshot(path=str(STORY / 'tmp/suno_login_step1.png'))
                # Suno 无邮箱密码登录：Google OAuth（该账号 Last used 通道）
                g = page.locator('button:has-text("Continue with Google")').first
                if g.count() and g.is_visible():
                    g.click(); log('点击 Continue with Google')
                    try:
                        page.wait_for_selector('#identifierId, input[name="identifier"], input[type="email"]', timeout=45000, state='visible')
                    except Exception:
                        pass
                    page.screenshot(path=str(STORY / 'tmp/suno_login_step2.png'))
                    try:
                        em = page.locator('#identifierId, input[name="identifier"], input[type="email"]').first
                        if em.count() and em.is_visible():
                            em.fill(email)
                            page.locator('button:has-text("Next"), #identifierNext').first.click()
                            log('Google: 已填邮箱并 Next')
                            try:
                                page.wait_for_selector('input[name="Passwd"]', timeout=45000, state='visible')
                            except Exception:
                                pass
                            pw = page.locator('input[name="Passwd"]').first
                            if pw.count() and pw.is_visible():
                                pw.fill(password)
                                page.locator('button:has-text("Next"), #passwordNext').first.click()
                                log('Google: 已填密码并 Next')
                            else:
                                log('Google: 未出现密码框（可能要二次验证/被拦）')
                        else:
                            log('Google: 未出现邮箱框')
                    except Exception as exc:
                        log(f'Google OAuth 异常（{type(exc).__name__}）：{exc}')
                    page.wait_for_timeout(6000)
                    page.screenshot(path=str(STORY / 'tmp/suno_login_step3.png'))
                else:
                    log('未找到 Google 登录按钮')
            except Exception as exc:
                log(f'自动登录异常（{type(exc).__name__}）：{exc}')

        log(f'等待登录态（{"无头" if headless else "自动+手动兜底"}，最长 {"3" if headless else "10"} 分钟）…')
        deadline = time.time() + (180 if headless else 600)
        ok = False
        while time.time() < deadline:
            try:
                page.wait_for_timeout(5000)
            except Exception:
                break
            tab = find_logged_in()
            if tab is not None:
                ok = True
                log('检测到创作界面，已登录')
                break
            log('等待登录…')
        if not ok:
            try:
                log(f'失败时页面: {page.url}')
                page.screenshot(path=str(STORY / 'tmp/suno_login_fail.png'))
            except Exception:
                pass
            ctx.close()
            sys.exit('超时未检测到登录，截图 tmp/suno_login_fail.png')
        cookies = ctx.cookies('https://suno.com')
        (PROFILE / 'cookies.json').write_text(json.dumps(cookies), encoding='utf-8')
        log(f'cookies 已导出（{len(cookies)} 条），会话保存在 .suno_profile')
        ctx.close()

if __name__ == '__main__':
    main()
