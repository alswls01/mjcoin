# MJ코인 맥판: 업비트 실시간 시세 + 네이버 증권 주식 차트 창
# 화면은 web/index.html (바지트·윈도우판과 같은 파일), 창은 pywebview(맥 기본 WebKit)
# 인터넷 요청과 실시간 연결은 파이썬이 처리해서 화면에 넘겨 줌 (화면에서 업비트로 직접 요청하면 429로 막힌 적 있음)
# 다이버전스 알림은 맥 기본 알림(화면 오른쪽 위)으로 띄움 (osascript)
import os, sys, json, threading, time, subprocess, urllib.request, urllib.error
import webview, websocket

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, "web", "index.html")
DATA = os.path.expanduser("~/Library/Application Support/MJCoin")   # 테마 같은 설정, 오류 기록 위치
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


# ---------- 맥 알림 (오른쪽 위) ----------
# 처음 한 번 맥이 알림 허용을 물어볼 수 있음 (시스템 설정 > 알림 에서 "스크립트 편집기" 또는 osascript 허용)
NOTIFY_AS = ['on run argv', 'display notification (item 2 of argv) with title (item 1 of argv) sound name "default"', 'end run']


def toast(title, body):
    try:
        cmd = ["osascript"]
        for line in NOTIFY_AS:
            cmd += ["-e", line]
        r = subprocess.run(cmd + [title, body], capture_output=True, timeout=20)
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
