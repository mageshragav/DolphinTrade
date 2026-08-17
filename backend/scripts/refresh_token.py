"""Olymp Trade session-token auto-refresh (headless Chrome via CDP).

The access_token is a ~48h bearer JWT with no public refresh API. This script
drives a real headless Chrome to the login page, lets the page's own JS run
Cloudflare Turnstile + fingerprinting, fills email/password from env, submits,
and harvests the fresh access_token cookie - then pushes it to the running
DolphinTrade server which hot-swaps it in place (no restart).

Usage:
    python refresh_token.py --push http://127.0.0.1:8000 [--profile DIR]
    python refresh_token.py --grab-only          # just print the cookie

Env:
    DT_OLYMP_EMAIL / DT_OLYMP_PASSWORD   login credentials
    DT_OLYMP_ORIGIN                      default https://olymptrade.com

Watchdog: the scheduler triggers this automatically when the token is within
12h of expiry, or already expired.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

CDP_PORT = 9222
PROFILE = '/tmp/olymp-chrome-profile'
ORIGIN = os.environ.get('DT_OLYMP_ORIGIN', 'https://olymptrade.com')
LOGIN_URL = ORIGIN + '/'  # login is a modal on the main page

WS = None
_msg = 0
CHROME_PROC = None


def _launch_chrome(profile: str):
    global CHROME_PROC
    exe = '/usr/bin/google-chrome'
    if not os.path.exists(exe):
        for c in ('google-chrome-stable', 'chromium', 'chromium-browser'):
            exe = f'/usr/bin/{c}'
            if os.path.exists(exe):
                break
        else:
            raise SystemExit('no chrome binary found (install google-chrome)')
    cmd = [
        exe, '--headless=new',
        f'--remote-debugging-port={CDP_PORT}',
        '--remote-allow-origins=*',
        f'--user-data-dir={profile}',
        '--no-first-run', '--no-default-browser-check',
        '--disable-gpu', '--window-size=1280,900',
        '--disable-blink-features=AutomationControlled',
        'about:blank',
    ]
    CHROME_PROC = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=2):
                return
        except Exception:
            time.sleep(0.5)
    raise SystemExit('chrome CDP did not come up')


def _ws_connect():
    """Connect to the PAGE target (Network/Page domains live there)."""
    global WS
    import websocket
    with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json', timeout=3) as r:
        pages = json.loads(r.read())
    if not pages:
        raise SystemExit('no CDP page target')
    page = next((p for p in pages if p.get('type') == 'page'), pages[0])
    WS = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=120)
    return WS


def _shutdown():
    global WS, CHROME_PROC
    if WS is not None:
        try:
            WS.close()
        except Exception:
            pass
    if CHROME_PROC is not None:
        try:
            CHROME_PROC.terminate()
        except Exception:
            pass


def _cdp(method, params=None):
    global _msg
    _msg += 1
    WS.send(json.dumps({'id': _msg, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(WS.recv())
        if msg.get('id') == _msg:
            if 'error' in msg:
                raise RuntimeError(f'CDP {method}: {msg["error"]}')
            return msg.get('result', {})


def _js(expr):
    res = _cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
    return (res.get('result') or {}).get('value')


def _read_token():
    """Return (access_token, exp_unix) from the browser cookie jar."""
    result = _cdp('Network.getAllCookies')
    for c in result.get('cookies', []):
        if c.get('name') == 'access_token' and c.get('domain', '').endswith('olymptrade.com'):
            tok = c['value']
            try:
                payload = json.loads(base64.urlsafe_b64decode(tok.split('.')[1] + '=='))
                return tok, payload.get('exp', 0)
            except Exception:
                return tok, 0
    return None, 0


def _wait_js(expr, timeout, interval=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _js(expr):
            return True
        time.sleep(interval)
    return False


def _fill_and_submit(email: str, password: str):
    """Open the login modal on the main page, fill the form, submit."""
    _cdp('Page.enable')
    _cdp('Runtime.enable')
    _cdp('Page.navigate', {'url': ORIGIN + '/'})
    _wait_js("document.querySelectorAll('a,button').length > 0", 30)
    # open the login modal
    clicked = _js("""
      (() => { const el = [...document.querySelectorAll('a,button')]
        .find(e => /sign\\s*in/i.test(e.textContent || ''));
        if (el) { el.click(); return true; } return false; })()
    """)
    if not clicked:
        print('[login] no "Sign in" button found')
        return 'no-signin'
    if not _wait_js("document.querySelectorAll('input').length >= 2", 30):
        return 'no-modal'
    js = """
    (() => {
      const byName = n => document.querySelector('input[name="' + n + '"]');
      const set = (el, val) => {
        if (!el) return false;
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(el, val);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        return true;
      };
      const eOk = set(byName('email') || [...document.querySelectorAll('input')]
        .find(i => ['email','text','tel'].includes((i.type||'').toLowerCase())), %E%);
      const pOk = set(byName('password') || [...document.querySelectorAll('input')]
        .find(i => (i.type||'').toLowerCase() === 'password'), %P%);
      // exact submit selector from the live modal DOM
      let clicked = false;
      const btn = document.querySelector('button[data-test="form-signin-button"]')
        || [...document.querySelectorAll('button')].filter(b => {
             const t = (b.textContent||'').trim().toLowerCase();
             return t === 'log in' || t === 'sign in'; }).pop();
      if (btn) { btn.click(); clicked = true; }
      const form = btn && btn.form;
      if (form && !clicked) { form.requestSubmit(); clicked = true; }
      return JSON.stringify({eOk, pOk, clicked, n: document.querySelectorAll('input').length});
    })()
    """.replace('%E%', json.dumps(email)).replace('%P%', json.dumps(password))
    return _js(js)


def _turnstile_iframes():
    """List same-origin-visible iframes that look like a Turnstile challenge."""
    return _js("""
      [...document.querySelectorAll('iframe')].map(f => ({
        src: f.src || '', x: f.getBoundingClientRect().x,
        y: f.getBoundingClientRect().y,
        w: f.getBoundingClientRect().width,
        h: f.getBoundingClientRect().height
      })).filter(b => /turnstile|challenges\\.cloudflare|captcha/i.test(b.src))
    """) or []


def _click_turnstile():
    """Best-effort click on the Turnstile checkbox iframe (cross-origin safe:
    dispatch mouse events at the iframe centre)."""
    for box in _turnstile_iframes():
        cx = box.get('x', 0) + box.get('w', 0) / 2
        cy = box.get('y', 0) + box.get('h', 0) / 2
        if not (cx and cy):
            continue
        for kind, opts in (('Input.dispatchMouseEvent',
                            {'type': 'mousePressed', 'x': cx, 'y': cy,
                             'button': 'left', 'clickCount': 1}),
                           ('Input.dispatchMouseEvent',
                            {'type': 'mouseReleased', 'x': cx, 'y': cy,
                             'button': 'left', 'clickCount': 1})):
            try:
                _cdp(kind, opts)
            except Exception:
                pass
        print('[login] clicked turnstile checkbox')
        return True
    return False


def _auto_login(email: str, password: str) -> tuple[str | None, int]:
    """Drive the full login flow; returns (token, exp) or (None, 0)."""
    print(f'[login] navigating to {LOGIN_URL}')
    state = _fill_and_submit(email, password)
    print(f'[login] form state: {state}')
    time.sleep(3)
    # some flows show the turnstile checkbox only after submit
    _click_turnstile()
    time.sleep(2)
    tok, exp = _read_token()
    if tok:
        return tok, exp
    # wait out the challenge/2FA window
    for i in range(60):
        time.sleep(5)
        tok, exp = _read_token()
        if tok:
            print(f'[login] token acquired after ~{(i + 1) * 5}s')
            return tok, exp
        if i in (2, 8, 20):
            _click_turnstile()
    return None, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--push', help='DolphinTrade API base URL (hot-swap on server)')
    ap.add_argument('--profile', default=PROFILE)
    ap.add_argument('--grab-only', action='store_true', help='just print the cookie')
    ap.add_argument('--force-login', action='store_true', help='log in even if a token exists')
    args = ap.parse_args()

    email = os.environ.get('DT_OLYMP_EMAIL', '')
    password = os.environ.get('DT_OLYMP_PASSWORD', '')
    if not (email and password):
        print('[refresh] DT_OLYMP_EMAIL / DT_OLYMP_PASSWORD not set in env')

    _launch_chrome(args.profile)
    _ws_connect()
    _cdp('Network.enable')

    tok, exp = _read_token()
    now = time.time()
    if tok:
        print(f'[refresh] existing cookie token: exp={exp} ({exp - now:.0f}s left)')
    if args.grab_only:
        print(f'ACCESS_TOKEN={tok}' if tok else 'NO TOKEN')
        return 0 if tok else 2

    if (not tok or args.force_login or (tok and exp and exp - now < 3600 * 24)):
        if not (email and password):
            print('[refresh] NO TOKEN and no credentials - manual paste required: /token <jwt>')
            return 2
        print('[refresh] running auto-login...')
        tok, exp = _auto_login(email, password)
        if not tok:
            print('[refresh] LOGIN FAILED - likely Turnstile/challenge. '
                  'Manual fallback: /token <jwt>')
            return 3

    if args.push and tok:
        body = json.dumps({'access_token': tok}).encode()
        req = urllib.request.Request(args.push.rstrip('/') + '/api/token', body,
                                     {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
            print(f'[refresh] pushed: {resp}')
            return 0 if resp.get('ok') else 1
        except Exception as e:
            print(f'[refresh] push failed: {e}')
            return 1
    print(f'[refresh] token OK (exp {exp}) - not pushing')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    finally:
        _shutdown()
