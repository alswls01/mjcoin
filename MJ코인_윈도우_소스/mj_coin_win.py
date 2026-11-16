# MJ코인 윈도우판: 업비트 실시간 시세 차트 창
# 화면은 web/index.html (바지트판과 같은 파일), 창은 pywebview(Edge WebView2)
# 인터넷 요청과 실시간 연결은 파이썬이 처리해서 화면에 넘겨 줌 (화면에서 업비트로 직접 요청하면 429로 막힌 적 있음)
# 다이버전스 알림은 윈도우 기본 알림(화면 오른쪽 아래)으로 띄움
import os, sys, json, threading, time, base64, subprocess, urllib.request, urllib.error
import webview, websocket

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, "web", "index.html")
DATA = os.path.join(os.environ.get("LOCALAPPDATA", BASE), "MJCoin")   # 테마 같은 설정 저장 위치
WS_URL = "wss://api.upbit.com/websocket/v1"
CODES = ["KRW-BTC", "USDT-BTC", "KRW-ETH", "KRW-XRP", "KRW-BCH", "KRW-SOL"]
UA = "MJCoin/1.0"
# 화면이 요청할 수 있는 주소 (업비트 + 네이버 증권)
ALLOWED = ("https://api.upbit.com/", "https://api.stock.naver.com/", "https://polling.finance.naver.com/")
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
TOAST_PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml("<toast><visual><binding template='ToastGeneric'><text></text><text></text></binding></visual><audio src='ms-winsoundevent:Notification.Default'/></toast>")
$n = $x.GetElementsByTagName('text')
$n.Item(0).AppendChild($x.CreateTextNode($env:MJ_TITLE)) | Out-Null
$n.Item(1).AppendChild($x.CreateTextNode($env:MJ_BODY)) | Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:MJ_APPID).Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""


PS_APPID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


APP_ID = "kmj.MJCoin"
_app_id = None


def app_id():
    # 알림이 "MJ코인" 이름·아이콘으로 뜨도록 사용자 레지스트리(HKCU)에 앱 ID 등록. 실패하면 PowerShell 이름으로 띄움
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
        _app_id = PS_APPID
    return _app_id


def toast(title, body):
    try:
        env = dict(os.environ, MJ_TITLE=title, MJ_BODY=body, MJ_APPID=app_id())
        enc = base64.b64encode(TOAST_PS.encode("utf-16-le")).decode()
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-EncodedCommand", enc], env=env, capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            log("알림 실패:", r.stderr.decode("utf-8", "replace")[:500])
    except Exception as e:
        log("알림 오류:", e)


# ---------- 화면에서 부르는 함수 ----------
class Api:
    # 화면에서 온 요청: {"id":..,"url":..} 또는 {"notify":{"title":..,"body":..}}
    def post(self, text):
        try:
            req = json.loads(text)
        except Exception:
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
        url = req.get("url", "")
        if url.startswith(ALLOWED):
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
    threading.Thread(target=OUT.loop, daemon=True).start()
    threading.Thread(target=ws_loop, daemon=True).start()


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    win = webview.create_window("MJ코인", url=HTML, js_api=Api(), width=1024, height=640, min_size=(800, 500))
    OUT.win = win
    win.events.loaded += on_loaded
    webview.start(private_mode=False, storage_path=DATA)
