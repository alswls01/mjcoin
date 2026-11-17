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
    d = json.loads(upd_get(f"https://api.github.com/repos/{REPO}/releases/latest").read().decode("utf-8"))
    tag = d.get("tag_name", "")
    a = next((x for x in d.get("assets", []) if x.get("name") == asset_name()), None)
    info = {"current": APP_VERSION, "latest": tag.lstrip("vV"), "notes": (d.get("body") or "")[:2000],
            "newer": ver_tuple(tag) > ver_tuple(APP_VERSION) and a is not None,
            "frozen": bool(getattr(sys, "frozen", False)), "size": a.get("size") if a else 0}
    UPD["info"] = dict(info, url=a.get("browser_download_url") if a else None)
    return info


def update_install():
    info = UPD.get("info")
    if not info or not info.get("newer") or not info.get("url"):
        raise RuntimeError("받을 새 버전이 없습니다")
    if not getattr(sys, "frozen", False):
        raise RuntimeError("소스로 실행 중이라 바꿀 앱이 없습니다. 빌드한 앱에서 업데이트하세요")
    import tempfile, subprocess
    tmp = tempfile.mkdtemp(prefix="mjcoin_upd_")
    path = os.path.join(tmp, asset_name())
    r = upd_get(info["url"], timeout=60)
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
    log("업데이트 받음:", info["latest"], got, "바이트")
    if sys.platform == "win32":
        # 설치 파일을 띄우고 이 프로그램은 끔 (켜져 있으면 MJCoin.exe 를 덮어쓸 수 없음)
        subprocess.Popen([path], creationflags=0x00000008 | 0x00000200, close_fds=True)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        # 새 앱을 풀고, 이 프로그램이 꺼지길 기다렸다가 앱을 통째로 바꾼 뒤 다시 켜는 스크립트를 따로 돌림
        app = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))
        if not app.endswith(".app"):
            raise RuntimeError("앱 위치를 찾지 못했습니다: " + app)
        subprocess.run(["ditto", "-x", "-k", path, tmp], check=True)
        new = os.path.join(tmp, "MJCoin.app")
        if not os.path.isdir(new):
            raise RuntimeError("받은 파일에 MJCoin.app 이 없습니다")
        sh = os.path.join(tmp, "swap.sh")
        with open(sh, "w") as f:
            f.write(f"""#!/bin/bash
while kill -0 {os.getpid()} 2>/dev/null; do sleep 0.3; done
rm -rf "{app}.old" && mv "{app}" "{app}.old" && mv "{new}" "{app}" && rm -rf "{app}.old"
xattr -dr com.apple.quarantine "{app}" 2>/dev/null
open "{app}"
""")
        subprocess.Popen(["/bin/bash", sh], start_new_session=True, close_fds=True)
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
    # 시작 창은 거의 정사각형이고 넉넉하게 (차트 아래 지표 두 줄이 있어도 차트가 잘 보이게, 부장님 지정 2026-11-17). 화면이 작으면 화면에 맞춤
    ww, wh = 1240, 1040
    try:
        sc = webview.screens[0]
        ww, wh = min(ww, sc.width - 40), min(wh, sc.height - 60)
    except Exception as e:
        log("화면 크기 읽기 실패:", e)
    win = webview.create_window("MJ코인", url=HTML, js_api=Api(), width=ww, height=wh, min_size=(800, 500))
    OUT.win = win
    win.events.loaded += on_loaded
    webview.start(private_mode=False, storage_path=DATA)
