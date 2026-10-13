"""Low-frequency Tripo Studio browser driver; credentials only from environment.

The web UI and API use separate credit balances. This driver uses Studio.
No automatic generation retries, subscription purchases or export-gate bypasses.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[3]
STORY = ROOT / 'dula-story'
STUDIO = 'https://studio.tripo3d.ai'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['probe', 'login', 'authenticate'])
    ap.add_argument('--profile', type=Path, default=STORY / '.tripo_profile')
    ap.add_argument('--url', default=STUDIO + '/workspace/generate')
    ap.add_argument('--out', type=Path, default=STORY / 'tmp/tripo_headless')
    ap.add_argument('--headed', action='store_true', help='Only for explicitly requested interactive login')
    ap.add_argument('--wait-seconds', type=int, default=300)
    ap.add_argument('--channel', choices=['chrome','chromium'], default='chromium')
    args = ap.parse_args()
    from urllib.parse import urlsplit
    if urlsplit(args.url).hostname != 'studio.tripo3d.ai':
        ap.error('--url must be on studio.tripo3d.ai')
    args.out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(args.profile.resolve()),
            channel=args.channel, headless=not args.headed, viewport={'width':1440,'height':1000})
        account = {}
        def observe(response):
            if response.url.startswith('https://api.tripo3d.ai/v2/studio/user/profile/payment') and response.status == 200:
                try:
                    result = response.json()
                    if result.get('code') == 0 and 'wallet' in result.get('data', {}):
                        data = result['data']
                        account.update({'authenticated':True,'credits':data['wallet'].get('total_credit'),
                                        'membership':data.get('member',{}).get('type')})
                except Exception:
                    pass
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on('response', observe)
            page.goto(args.url, wait_until='domcontentloaded', timeout=60000)
            if args.command == 'authenticate':
                if not args.headed:
                    raise RuntimeError('authenticate requires --headed for manual verification')
                print('Interactive Tripo profile opened. Complete site verification and sign in in this window.', flush=True)
                deadline = time.monotonic() + args.wait_seconds
                while time.monotonic() < deadline:
                    text = page.locator('body').inner_text()
                    # Account workspace without a visible sign-in action is a UI observation;
                    # the later headless probe must independently establish reuse.
                    if account.get('authenticated'):
                        print('Authenticated account response received; preserving profile.', flush=True)
                        break
                    page.wait_for_timeout(2000)
            page.wait_for_timeout(7000)
            # Let automatic site verification finish naturally. Never click CAPTCHA challenges.
            deadline = time.monotonic() + 30
            challenge = re.compile(r'Performing security verification|Verify you are human|Just a moment|checking your browser|正在进行安全验证|验证您不是自动程序|验证您是真人', re.I)
            while challenge.search(page.locator('body').inner_text()) and time.monotonic() < deadline:
                page.wait_for_timeout(2000)
            blocked = bool(challenge.search(page.locator('body').inner_text()))
            if args.command == 'login' and not blocked:
                email, password = os.environ.get('TRIPO_EMAIL'), os.environ.get('TRIPO_PASSWORD')
                # A valid existing session should never be logged out just to test credentials.
                if not page.get_by_role('button', name=re.compile(r'^(Log in|Login|Sign in)$', re.I)).count():
                    pass
                elif not email or not password:
                    raise RuntimeError('Set TRIPO_EMAIL and TRIPO_PASSWORD for login; do not pass passwords as command arguments')
                else:
                    page.get_by_role('button', name=re.compile(r'^(Log in|Login|Sign in)$', re.I)).first.click()
                    page.wait_for_timeout(1200)
                    em = page.locator('input[type=email]').first
                    if em.count() and em.is_visible():
                        em.fill(email)
                    pw = page.locator('input[type=password]').first
                    if pw.count() and pw.is_visible():
                        pw.fill(password)
                        page.get_by_role('button',name=re.compile(r'^(Log in|Login|Sign in|Continue)$',re.I)).last.click()
                        page.wait_for_timeout(8000)
            body = page.locator('body').inner_text()
            # Only visible UI text and input metadata; never values, cookies, tokens or storage.
            inputs = page.locator('input').evaluate_all('(els)=>els.map(e=>({type:e.type,placeholder:e.placeholder,name:e.name}))')
            report = {'headless':not args.headed, 'url':page.url, 'visibleText':body,
                      'status':'site_verification_required' if blocked else 'authenticated' if account.get('authenticated') else 'ui_loaded_not_authenticated',
                      'account':account,
                      'inputs':inputs, 'generationSubmitted':False}
            (args.out/'probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            page.screenshot(path=str(args.out/'probe.png'))
            print(json.dumps(report,ensure_ascii=False))
        except Exception as exc:
            if args.command == 'authenticate' and 'closed' in str(exc).lower():
                print(json.dumps({'status':'interactive_window_closed','account':account}))
            else:
                raise
        finally:
            ctx.close()


if __name__ == '__main__':
    main()
