# MJ코인 윈도우판: 업비트 실시간 시세 차트 창
# 화면은 web/index.html (바지트판과 같은 파일), 창은 pywebview(Edge WebView2)
# 인터넷 요청과 실시간 연결은 파이썬이 처리해서 화면에 넘겨 줌 (화면에서 업비트로 직접 요청하면 429로 막힌 적 있음)
# 다이버전스 알림은 윈도우 기본 알림(화면 오른쪽 아래)으로 띄움
import os, sys, json, threading, time, urllib.request, urllib.error
import webview, websocket

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, "web", "index.html")
DATA = os.path.join(os.environ.get("LOCALAPPDATA", BASE), "MJCoin")   # 테마 같은 설정 저장 위치
WS_URL = "wss://api.upbit.com/websocket/v1"
CODES = ["KRW-BTC", "USDT-BTC", "KRW-ETH", "KRW-XRP", "KRW-BCH", "KRW-SOL"]
UA = "MJCoin/1.0"
# 화면이 요청할 수 있는 주소 (업비트 + 네이버 증권)
ALLOWED = ("https://api.upbit.com/", "https://api.stock.naver.com/", "https://polling.finance.naver.com/",
           "https://api.alternative.me/", "https://fapi.binance.com/", "https://api.binance.com/",
           "https://api.bitcoin-data.com/", "https://api.exchange.coinbase.com/", "https://api.coingecko.com/")   # 공포탐욕지수, 바이낸스 롱숏·펀딩비·미결제약정·시세, MVRV, 코인베이스 시세, 도미넌스 (환율·금은 네이버)
LOG = os.path.join(DATA, "mjcoin.log")
SUB = {"codes": list(CODES), "ws": None, "lock": threading.Lock()}   # 화면에서 코인을 추가/빼면 codes가 바뀜


def sub_msg():
    return json.dumps([{"ticket": f"mj-coin-{int(time.time())}"},
                       {"type": "ticker", "codes": SUB["codes"]},
                       {"type": "trade", "codes": SUB["codes"]},
                       {"format": "SIMPLE"}])


def log(*a):
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except Exception:
        pass


# ---------- 화면(JS)으로 보내기: 한 스레드에서 모아서 보냄 ----------
class JsOut:
    def __init__(self):
        self.win = None
        self.lock = threading.Lock()
        self.calls = []      # 일반 호출
        self.ws = []         # 실시간 시세 메시지 (0.2초마다 묶어서)
        self.title = None

    def call(self, code):
        with self.lock:
            self.calls.append(code)

    def ws_msg(self, text):
        with self.lock:
            self.ws.append(text)

    def loop(self):
        last_title = 0
        while True:
            time.sleep(0.2)
            with self.lock:
                calls, self.calls = self.calls, []
                msgs, self.ws = self.ws, []
            try:
                if calls:
                    self.win.evaluate_js(";".join(calls))
                if msgs:
                    self.win.evaluate_js(f"window.mjWsBatch({json.dumps(msgs)})")
                # 창 제목을 화면 제목(document.title)에 맞춤 (엑셀 테마면 "통합 문서1 - Excel")
                if time.time() - last_title > 1:
                    last_title = time.time()
                    t = self.win.evaluate_js("document.title")
                    if t and t != self.title:
                        self.title = t
                        self.win.set_title(t)
            except Exception as e:
                log("js 오류:", e)


OUT = JsOut()


# ---------- 윈도우 알림 (오른쪽 아래) ----------
# PowerShell 을 숨겨 실행하던 방식은 백신이 악성으로 오인해서 windows-toasts 라이브러리로 바꿈
APP_ID = "kmj.MJCoin"
_app_id = None


def app_id():
    # 알림이 "MJ코인" 이름·아이콘으로 뜨도록 사용자 레지스트리(HKCU)에 앱 ID 등록. 실패하면 명령 프롬프트 이름으로 띄움
    global _app_id
    if _app_id:
        return _app_id
    try:
        import shutil, winreg
        ico = os.path.join(DATA, "mjcoin.ico")
        src = os.path.join(BASE, "mjcoin.ico")
        if os.path.exists(src) and not os.path.exists(ico):
            shutil.copyfile(src, ico)
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\AppUserModelId\\" + APP_ID)
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "MJ코인")
        if os.path.exists(ico):
            winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, ico)
        winreg.CloseKey(k)
        _app_id = APP_ID
    except Exception as e:
        log("알림 앱 ID 등록 실패:", e)
        _app_id = None   # 등록 실패하면 라이브러리 기본값(명령 프롬프트 이름)으로 띄움
    return _app_id


def toast(title, body):
    try:
        from windows_toasts import InteractableWindowsToaster, Toast
        InteractableWindowsToaster("MJ코인", notifierAUMID=app_id()).show_toast(Toast(text_fields=[title, body]))
    except Exception as e:
        log("알림 오류:", e)


# ---------- 미국 경제지표 발표 수치 (BLS 공개 API, 키 없이 하루 25번까지) ----------
# 일정은 web/econ_events.js 에 들어 있고, 여기서는 발표된 수치만 받아 DATA/econ.json 에 저장해 둠
ECON_SERIES = [
    "CUSR0000SA0", "CUUR0000SA0", "CUSR0000SA0L1E", "CUUR0000SA0L1E",   # CPI, 근원 CPI (계절조정, 원계열)
    "WPSFD4", "WPUFD4", "WPSFD49104", "WPUFD49104",                     # PPI 최종수요, 근원 PPI
    "CES0000000001", "LNS14000000",                                     # 비농업 고용, 실업률
    "JTS000000000000000JOL", "CIS1010000000000Q",                       # 구인건수, 고용비용지수 분기 변화율
]
ECON_FILE = os.path.join(DATA, "econ.json")
ECON_LOCK = threading.Lock()


def econ_get(force):
    # 평소에는 3시간, 발표 직후 화면이 다시 달라고 하면(force) 10분 지난 것만 새로 받음
    with ECON_LOCK:
        cache = None
        try:
            with open(ECON_FILE, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
        age = time.time() - cache.get("fetched", 0) if cache else 1e9
        if cache and age < (600 if force else 10800):
            return 200, cache
        y = int(time.strftime("%Y"))
        body = json.dumps({"seriesid": ECON_SERIES, "startyear": str(y - 2), "endyear": str(y)}).encode()
        try:
            req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body,
                                         headers={"Content-Type": "application/json", "User-Agent": UA})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
            if d.get("status") != "REQUEST_SUCCEEDED":
                raise RuntimeError(f"{d.get('status')} {d.get('message')}")
            series = {}
            for sr in d["Results"]["series"]:
                pts = []
                for x in sr.get("data", []):
                    per = x.get("period", "")
                    if per.startswith("M") and per != "M13":
                        pts.append([f"{x['year']}-{per[1:]}", x["value"]])
                    elif per.startswith("Q"):
                        pts.append([f"{x['year']}-Q{int(per[1:])}", x["value"]])
                series[sr["seriesID"]] = pts
            cache = {"fetched": time.time(), "series": series}
            with open(ECON_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f)
            log("경제지표 수치 받음:", len(series), "개 시리즈")
            return 200, cache
        except Exception as e:
            log("경제지표 수치 받기 실패:", e)
            if cache:
                return 200, dict(cache, stale=True)
            return 0, {"error": str(e)}


def econ_run(rid, force):
    try:
        st, body = econ_get(bool(force))
    except Exception as e:
        st, body = 0, {"error": str(e)}
    OUT.call(f"window.mjEconReply({rid}, {st}, {json.dumps(json.dumps(body))})")


# ---------- AI 견해 (Claude API) ----------
# 화면이 봉 데이터를 글로 묶어 보내면 여기서 Claude 에게 묻고 답을 돌려줌.
# API 키는 맥 키체인 / 윈도우 자격 증명 관리자에만 저장 (화면, 파일에는 남기지 않음)
try:
    import keyring as _ai_keyring
except Exception:
    _ai_keyring = None
AI_SERVICE = "MJCoin.claude"
AI_MODEL = "claude-opus-5-5"
AI_PRICE = (4.0, 20.0)   # claude-opus-5-5 백만 토큰당 달러 (입력, 출력)
AI_SYSTEM = """너는 암호화폐와 주식 차트를 보는 단기 시세 분석가다. 사용자가 보낸 봉 데이터(1분, 10분, 1시간, 4시간, 일봉)와 참고 지표만 근거로 판단한다.
데이터에 없는 뉴스, 사건, 숫자를 지어내지 않는다. 확실하지 않은 것은 확실하지 않다고 쓴다.
판단 순서: 일봉으로 큰 흐름과 위치를 잡고, 4시간과 1시간봉으로 중간 흐름을, 10분과 1분봉으로 최근 한 시간의 힘(거래량, 고점과 저점의 변화, 꼬리)을 본다.
답은 한국어로, 아래 제목과 순서를 그대로 쓴다. 마크다운 기호(#, *, **, 표)와 줄표(긴 줄표, 짧은 줄표, 문장을 끊는 하이픈)는 쓰지 않는다. 목록이 필요하면 줄을 바꾸고 "·" 로 시작한다. 가격은 데이터와 같은 단위로 쓴다.

■ 지금 상황
(3~4줄 요약)
■ 봉별로 본 것
· 일봉: (한 줄)
· 4시간봉: (한 줄)
· 1시간봉: (한 줄)
· 10분봉: (한 줄)
· 1분봉: (한 줄)
■ 앞으로 1~4시간
방향: 오름 / 내림 / 옆걸음 중 하나, 확신: 낮음 / 보통 / 높음 중 하나
(이유 2~3줄)
■ 앞으로 1~6시간
방향과 확신, 이유 (같은 형식)
■ 볼 가격
· 지지: 
· 저항: 
· 이 견해가 틀렸다고 볼 가격: 
■ 조심할 점
(1~3줄)"""


# 구독 계정으로 쓰기: 이 컴퓨터에 깔린 Claude Code(claude) 를 불러 답을 받음. 로그인도 Claude Code 의 공식 로그인 창으로 함
AI_DIR = os.path.join(DATA, "ai")


def ai_cli():
    import shutil
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        cands = [os.path.join(home, ".local", "bin", "claude.exe"),
                 os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"), shutil.which("claude")]
    else:
        cands = [os.path.join(home, ".local", "bin", "claude"), os.path.join(home, ".npm-global", "bin", "claude"),
                 "/usr/local/bin/claude", "/opt/homebrew/bin/claude", os.path.join(home, ".claude", "local", "claude"),
                 shutil.which("claude")]
    return next((c for c in cands if c and os.path.isfile(c)), None)


def ai_token():
    # 계정 주인이 claude setup-token 으로 만들어 보내 준 1년짜리 연결 코드 (AI 질문만 됨, 비밀번호 아님)
    if not _ai_keyring:
        return None
    try:
        return _ai_keyring.get_password(AI_SERVICE, "oauth_token")
    except Exception:
        return None


def ai_cli_run(args, stdin=None, timeout=30):
    import subprocess
    cli = ai_cli()
    if not cli:
        raise FileNotFoundError("claude")
    os.makedirs(AI_DIR, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([os.path.dirname(cli), env.get("PATH", ""), "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"])
    tok = ai_token()
    if tok:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = tok
    return subprocess.run([cli] + args, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=AI_DIR, env=env, creationflags=0x08000000 if sys.platform == "win32" else 0)


def ai_cli_status():
    if ai_token():
        return {"cli": bool(ai_cli()), "loggedIn": True, "email": "", "method": "token"}
    if not ai_cli():
        return {"cli": False, "loggedIn": False}
    try:
        p = ai_cli_run(["auth", "status"], timeout=20)
        d = json.loads(p.stdout or "{}")
        return {"cli": True, "loggedIn": bool(d.get("loggedIn")), "email": d.get("email") or "", "method": d.get("authMethod") or ""}
    except Exception as e:
        log("claude 상태 확인 실패:", e)
        return {"cli": True, "loggedIn": False}


def ai_cli_login():
    import subprocess
    cli = ai_cli()
    if not cli:
        raise RuntimeError("이 컴퓨터에 Claude Code 가 없습니다")
    if sys.platform == "win32":
        subprocess.Popen(f'start "Claude 로그인" cmd /c ""{cli}" auth login --claudeai"', shell=True)
    else:
        q = cli.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "\\"{q}\\" auth login --claudeai"', "-e", 'tell application "Terminal" to activate'])
    return {"ok": True}


def ai_cli_install():
    # 공식 설치 명령을 앱이 대신 실행 (관리자 권한 필요 없음). 윈도우는 %USERPROFILE%\\.local\\bin\\claude.exe 에 깔림
    import subprocess
    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://claude.ai/install.ps1 | iex"]
    else:
        cmd = ["/bin/bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"]
    log("Claude Code 설치 시작")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    log("Claude Code 설치 끝:", p.returncode, (p.stdout or "")[-300:], (p.stderr or "")[-300:])
    return ai_cli()


def ai_cli_setup():
    # "Claude 연결하기" 단추: 없으면 설치하고, 로그인이 안 돼 있으면 공식 로그인 창을 띄움
    if not ai_cli() and not ai_cli_install():
        return 0, {"error": "Claude Code 를 설치하지 못했습니다. 인터넷 연결을 확인하고 다시 눌러 주세요"}
    st = ai_cli_status()
    if not st.get("loggedIn"):
        ai_cli_login()
        st["loginOpened"] = True
    return 200, st


def ai_cli_mktoken():
    import subprocess
    cli = ai_cli()
    if not cli:
        raise RuntimeError("이 컴퓨터에 Claude Code 가 없습니다")
    if sys.platform == "win32":
        subprocess.Popen(f'start "연결 코드 만들기" cmd /k ""{cli}" setup-token"', shell=True)
    else:
        q = cli.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "\\"{q}\\" setup-token"', "-e", 'tell application "Terminal" to activate'])
    return {"ok": True}


def ai_cli_ask(prompt):
    os.makedirs(AI_DIR, exist_ok=True)
    sp = os.path.join(AI_DIR, "system.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write(AI_SYSTEM)
    try:
        p = ai_cli_run(["-p", "--model", "opus", "--effort", "high", "--output-format", "json", "--tools", "",
                        "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
                        "--system-prompt-file", sp], stdin=prompt, timeout=300)
    except Exception as e:
        return 0, {"error": "Claude Code 실행 실패: " + str(e)[:200], "charged": False}
    try:
        d = json.loads(p.stdout)
    except Exception:
        return 0, {"error": "Claude Code 답을 읽지 못했습니다: " + (p.stderr or p.stdout or "")[:300], "charged": False}
    res = str(d.get("result") or "").strip()
    if d.get("is_error") or not res:
        if any(w in res.lower() for w in ("login", "logged in", "token", "401", "unauthorized", "authenticat")):
            return 0, {"error": "Claude 계정 로그인이 필요합니다", "needLogin": True, "charged": False}
        return 0, {"error": "Claude 오류: " + res[:300], "charged": d.get("terminal_reason") != "api_error"}
    u = d.get("usage") or {}
    models = list((d.get("modelUsage") or {}).keys())
    log("AI 견해 받음 (구독):", models, u.get("input_tokens"), u.get("output_tokens"))
    return 200, {"text": res, "model": (models[0] if models else "opus") + " · 구독 계정", "sub": True,
                 "in": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0),
                 "out": u.get("output_tokens") or 0, "cost": round(float(d.get("total_cost_usd") or 0), 4)}


def ai_key():
    if not _ai_keyring:
        return None
    try:
        return _ai_keyring.get_password(AI_SERVICE, "api_key")
    except Exception as e:
        log("AI 키 읽기 실패:", e)
        return None


def ai_op(t):
    op = t.get("op")
    if op == "status":
        return 200, dict(ai_cli_status(), hasKey=bool(ai_key()), store=bool(_ai_keyring))
    if op == "login":
        return 200, ai_cli_login()
    if op == "setup":
        return ai_cli_setup()
    if op == "mktoken":
        if sys.platform == "win32":
            return 0, {"error": "연결 코드는 계정 주인의 맥에서만 만듭니다"}
        return 200, ai_cli_mktoken()
    if op == "settoken":
        k = str(t.get("token") or "").strip()
        if not _ai_keyring:
            return 0, {"error": "코드를 안전하게 저장할 곳(keyring)이 없습니다"}
        if not k.startswith("sk-ant-oat") or len(k) < 40:
            return 0, {"error": "연결 코드는 sk-ant-oat 로 시작합니다. 받은 글을 통째로 다시 붙여 넣어 주세요"}
        _ai_keyring.set_password(AI_SERVICE, "oauth_token", k)
        log("AI 연결 코드 저장함")
        return 200, ai_cli_status()
    if op == "deltoken":
        try:
            _ai_keyring.delete_password(AI_SERVICE, "oauth_token")
        except Exception:
            pass
        return 200, ai_cli_status()
    if op == "setkey":
        k = str(t.get("key") or "").strip()
        if not _ai_keyring:
            return 0, {"error": "키를 안전하게 저장할 곳(keyring)이 없습니다"}
        if not k.startswith("sk-ant-") or len(k) < 30:
            return 0, {"error": "Anthropic API 키는 sk-ant- 로 시작합니다"}
        _ai_keyring.set_password(AI_SERVICE, "api_key", k)
        log("AI 키 저장함")
        return 200, {"hasKey": True}
    if op == "delkey":
        try:
            _ai_keyring.delete_password(AI_SERVICE, "api_key")
        except Exception:
            pass
        return 200, {"hasKey": False}
    if op != "ask":
        return 0, {"error": "모르는 요청"}
    prompt = str(t.get("prompt") or "")[:80000]
    if len(prompt) < 50:
        return 0, {"error": "보낼 데이터가 없습니다", "charged": False}
    key = ai_key()
    if not key:   # API 키가 없으면 구독 계정(Claude Code) 으로
        if not ai_cli() and not ai_cli_install():
            return 0, {"error": "필요한 프로그램(Claude Code)을 설치하지 못했습니다. 인터넷 연결을 확인하고 다시 눌러 주세요", "charged": False}
        return ai_cli_ask(prompt)
    import anthropic
    client = anthropic.Anthropic(api_key=key, timeout=240.0, max_retries=1)
    try:
        r = client.beta.messages.create(
            model=AI_MODEL, max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",   # 안전 검사에 걸리면 서버가 다른 모델로 다시 답함
            output_config={"effort": "high"},
            system=AI_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        return 0, {"error": "API 키가 맞지 않습니다. 키를 다시 넣어 주세요", "needKey": True, "charged": False}
    except anthropic.PermissionDeniedError as e:
        return 0, {"error": "이 키로는 쓸 수 없습니다: " + str(e)[:300], "charged": False}
    except anthropic.RateLimitError:
        return 0, {"error": "요청이 너무 많다고 합니다. 잠시 뒤 다시 해 주세요", "charged": False}
    except anthropic.BadRequestError as e:
        m = str(e)
        if "credit balance" in m:
            return 0, {"error": "Anthropic 계정 잔액이 부족합니다 (console.anthropic.com 에서 충전)", "charged": False}
        return 0, {"error": "요청 오류: " + m[:300], "charged": False}
    except anthropic.APIStatusError as e:
        return 0, {"error": f"Claude 서버 오류 ({e.status_code}). 잠시 뒤 다시 해 주세요", "charged": False}
    except anthropic.APIConnectionError:
        return 0, {"error": "Claude 서버에 연결하지 못했습니다 (인터넷 확인)", "charged": False}
    u = r.usage
    cost = (u.input_tokens * AI_PRICE[0] + u.output_tokens * AI_PRICE[1]) / 1e6
    if r.stop_reason == "refusal":
        return 0, {"error": "AI 가 답을 거절했습니다", "charged": True}
    text = "".join(b.text for b in r.content if b.type == "text").strip()
    if not text:
        return 0, {"error": f"빈 답이 왔습니다 ({r.stop_reason})", "charged": True}
    log("AI 견해 받음:", r.model, u.input_tokens, u.output_tokens)
    return 200, {"text": text, "model": r.model, "in": u.input_tokens, "out": u.output_tokens,
                 "cost": round(cost, 4), "stop": r.stop_reason}


def ai_run(rid, t):
    try:
        st, body = ai_op(t)
    except Exception as e:
        log("AI 오류:", e)
        st, body = 0, {"error": str(e)[:300], "charged": False}
    OUT.call(f"window.mjAiReply({rid}, {st}, {json.dumps(json.dumps(body))})")


# ---------- 업데이트 (깃허브 릴리스가 업데이트 서버) ----------
# 버전은 web/version.txt 한 곳. 깃허브에 v1.0.1 같은 꼬리표를 올리면 빌드가 릴리스에 설치 파일을 붙이고,
# 프로그램은 켤 때와 6시간마다 최신 릴리스를 물어봄. 새 버전이 있으면 화면에 단추가 뜨고 누르면 받아서 바꿈
REPO = "alswls01/mjcoin"
try:
    with open(os.path.join(BASE, "web", "version.txt"), encoding="utf-8") as _f:
        APP_VERSION = _f.read().strip() or "0.0.0"
except Exception:
    APP_VERSION = "0.0.0"
UPD = {"info": None}


def ver_tuple(v):
    try:
        return tuple(int(x) for x in str(v).lstrip("vV").split("-")[0].split("."))
    except Exception:
        return (0,)


def asset_name():
    if sys.platform == "win32":
        return "MJCoin_Setup.exe"
    import platform
    return "MJCoin_mac_arm.zip" if platform.machine() == "arm64" else "MJCoin_mac_intel.zip"


def upd_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout, context=globals().get("SSL_CTX"))


def update_check():
    try:
        d = json.loads(upd_get(f"https://api.github.com/repos/{REPO}/releases/latest").read().decode("utf-8"))
    except Exception as e:
        # 깃허브 API 는 IP 마다 시간당 60번까지라 막히면, 최신 릴리스 페이지 주소(…/releases/tag/v1.0.6)로 버전을 알아냄
        log("릴리스 API 실패, 페이지 주소로 확인:", e)
        tag = upd_get(f"https://github.com/{REPO}/releases/latest").geturl().rstrip("/").rsplit("/", 1)[-1]
        if not tag.startswith("v"):
            raise
        d = {"tag_name": tag, "body": "", "assets": [{"name": asset_name(), "size": 0,
             "browser_download_url": f"https://github.com/{REPO}/releases/download/{tag}/{asset_name()}"}]}
    tag = d.get("tag_name", "")
    a = next((x for x in d.get("assets", []) if x.get("name") == asset_name()), None)
    info = {"current": APP_VERSION, "latest": tag.lstrip("vV"), "notes": (d.get("body") or "")[:2000],
            "newer": ver_tuple(tag) > ver_tuple(APP_VERSION) and a is not None,
            "frozen": bool(getattr(sys, "frozen", False)), "size": a.get("size") if a else 0}
    UPD["info"] = dict(info, url=a.get("browser_download_url") if a else None)
    return info


def update_install():
    """새 설치 파일을 직접 받아 조용히(/S) 실행하고 이 프로그램은 끈다.
    설치 파일이 켜져 있는 MJ코인을 끄고, 옛 파일을 지운 뒤 새로 깔고, 다 깔리면 MJ코인을 다시 켠다."""
    info = UPD.get("info")
    if not info or not info.get("newer") or not info.get("url"):
        raise RuntimeError("받을 새 버전이 없습니다")
    url = info["url"]
    if not url.startswith(f"https://github.com/{REPO}/releases/download/"):
        raise RuntimeError("받기 주소가 이상합니다: " + url)
    if not getattr(sys, "frozen", False):
        raise RuntimeError("소스로 실행 중이라 바꿀 프로그램이 없습니다. 설치한 프로그램에서 업데이트하세요")
    import tempfile, subprocess
    tmp = tempfile.mkdtemp(prefix="mjcoin_upd_")
    path = os.path.join(tmp, "MJCoin_Setup.exe")
    r = upd_get(url, timeout=60)
    total, got, last = int(r.headers.get("Content-Length") or info.get("size") or 0), 0, 0
    with open(path, "wb") as f:
        while True:
            b = r.read(262144)
            if not b:
                break
            f.write(b)
            got += len(b)
            if total and got * 100 // total >= last + 5:
                last = got * 100 // total
                OUT.call(f"window.mjUpdateProgress({last})")
    if total and got != total:
        raise RuntimeError(f"받다가 끊겼습니다 ({got}/{total})")
    if got < 1000000:
        raise RuntimeError(f"받은 파일이 너무 작습니다 ({got} 바이트)")
    log("업데이트 받음:", info["latest"], got, "바이트, 조용히 설치 시작")
    subprocess.Popen([path, "/S"], creationflags=0x00000008 | 0x00000200, close_fds=True, cwd=tmp)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    OUT.call("window.mjUpdateProgress(100)")
    threading.Timer(1.2, lambda: os._exit(0)).start()
    return {"ok": True}


def update_run(rid, op):
    try:
        body = update_check() if op == "check" else update_install()
        st = 200
    except Exception as e:
        log("업데이트 오류:", e)
        st, body = 0, {"error": str(e)}
    OUT.call(f"window.mjUpdateReply({rid}, {st}, {json.dumps(json.dumps(body))})")


def set_alpha(a):
    """프로그램 창 전체 투명도 (화면 투명도 막대). 20~100%"""
    try:
        a = max(0.2, min(1.0, float(a)))
        n = win.native if "win" in globals() and win else None
        if n is None:
            return
        from System import Func, Type

        def _s():
            n.Opacity = a
        if n.InvokeRequired:
            n.Invoke(Func[Type](_s))
        else:
            _s()
    except Exception as e:
        log("투명도 오류:", e)


# ---------- 화면에서 부르는 함수 ----------
class Api:
    # 화면에서 온 요청: {"id":..,"url":..} 또는 {"notify":{"title":..,"body":..}}
    def post(self, text):
        try:
            req = json.loads(text)
        except Exception:
            return
        if "alpha" in req:
            set_alpha(req["alpha"])
            return
        if "subscribe" in req:
            codes = [c for c in req["subscribe"] if isinstance(c, str) and c.startswith(("KRW-", "USDT-", "BTC-"))]
            if codes and codes != SUB["codes"]:
                SUB["codes"] = codes
                ws = SUB["ws"]
                if ws:
                    try:
                        with SUB["lock"]:
                            ws.send(sub_msg())   # 새로 보내면 업비트가 구독을 통째로 바꿈
                    except Exception as e:
                        log("구독 변경 실패:", e)
            return
        if "notify" in req:
            n = req["notify"]
            threading.Thread(target=toast, args=(n.get("title", "MJ코인"), n.get("body", "")), daemon=True).start()
            return
        if "ai" in req and isinstance(req.get("id"), int) and isinstance(req["ai"], dict):
            threading.Thread(target=ai_run, args=(req["id"], req["ai"]), daemon=True).start()
            return
        if "update" in req and isinstance(req.get("id"), int) and req["update"] in ("check", "install"):
            threading.Thread(target=update_run, args=(req["id"], req["update"]), daemon=True).start()
            return
        if "econ" in req and isinstance(req.get("id"), int):
            threading.Thread(target=econ_run, args=(req["id"], (req["econ"] or {}).get("force") if isinstance(req["econ"], dict) else False), daemon=True).start()
            return
        url = req.get("url", "")
        if url.startswith(ALLOWED) and isinstance(req.get("id"), int):
            threading.Thread(target=self._fetch, args=(req["id"], url), daemon=True).start()

    def _fetch(self, rid, url):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=15)
            body, status = r.read().decode("utf-8", "replace"), r.status
        except urllib.error.HTTPError as e:
            body, status = e.read().decode("utf-8", "replace"), e.code
        except Exception as e:
            body, status = json.dumps(str(e)), 0
        OUT.call(f"window.mjReply({rid}, {status}, {json.dumps(body)})")


# ---------- 실시간 연결 ----------
def ws_loop():
    first, retry = True, 2
    while True:
        try:
            ws = websocket.create_connection(WS_URL, timeout=30, header=[f"User-Agent: {UA}"])
            with SUB["lock"]:
                ws.send(sub_msg())
            SUB["ws"] = ws
            OUT.call(f"window.mjWsState({json.dumps('open' if first else 'reopen')})")
            first, retry = False, 2
            last_ping = time.time()
            while True:
                data = ws.recv()
                if isinstance(data, bytes):
                    data = data.decode("utf-8", "replace")
                if data:
                    OUT.ws_msg(data)
                if time.time() - last_ping > 30:
                    with SUB["lock"]:
                        ws.ping()
                    last_ping = time.time()
        except Exception as e:
            SUB["ws"] = None
            log("실시간 연결 끊김:", e)
            OUT.call("window.mjWsState('closed')")
            time.sleep(retry)
            retry = min(retry * 2, 60)


started = False


def on_loaded():
    global started
    if started:
        return
    started = True
    OUT.call(f"window.mjVersion && window.mjVersion({json.dumps(APP_VERSION)})")   # 화면에 버전 표시, 업데이트 확인 시작
    threading.Thread(target=OUT.loop, daemon=True).start()
    threading.Thread(target=ws_loop, daemon=True).start()


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    # 시작 창은 가로로 넓게 (정사각형이면 엑셀 테마 글자가 잘림, 부장님 지정 2026-11-17). 화면이 작으면 화면에 맞춤
    ww, wh = 1600, 1000
    try:
        sc = webview.screens[0]
        ww, wh = min(ww, sc.width - 40), min(wh, sc.height - 60)
    except Exception as e:
        log("화면 크기 읽기 실패:", e)
    win = webview.create_window("MJ코인", url=HTML, js_api=Api(), width=ww, height=wh, min_size=(800, 500))
    OUT.win = win
    win.events.loaded += on_loaded
    webview.start(private_mode=False, storage_path=DATA)
