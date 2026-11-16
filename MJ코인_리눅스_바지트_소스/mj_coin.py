#!/usr/bin/python3
# MJ코인: 업비트 실시간 시세 차트 창
# 화면은 index.html(WebKit), 인터넷 요청과 실시간 연결은 파이썬(libsoup)이 처리해서 화면에 넘겨 줌
import os, sys, json, gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0")
from gi.repository import Gtk, WebKit, GLib, Soup, Gio

HERE = os.path.dirname(os.path.abspath(__file__))
WS_URL = "wss://api.upbit.com/websocket/v1"
CODES = ["KRW-BTC", "USDT-BTC", "KRW-ETH", "KRW-XRP", "KRW-BCH", "KRW-SOL"]
UA = "MJCoin/1.0"
# 화면이 요청할 수 있는 주소 (업비트 + 네이버 증권)
ALLOWED = ("https://api.upbit.com/", "https://api.stock.naver.com/", "https://polling.finance.naver.com/")


class Bridge:
    def __init__(self, view):
        self.view = view
        self.session = Soup.Session(user_agent=UA, timeout=15)
        self.ws = None
        self.retry = 2
        self.connected_once = False
        self.codes = list(CODES)   # 화면에서 코인을 추가/빼면 바뀜
        ucm = view.get_user_content_manager()
        ucm.register_script_message_handler("mjcoin", None)
        ucm.connect("script-message-received::mjcoin", self.on_message)

    def js(self, code):
        self.view.evaluate_javascript(code, -1, None, None, None, None, None)

    # 화면에서 온 요청: {"id":..,"url":..}
    def on_message(self, _ucm, value):
        try:
            req = json.loads(value.to_string())
        except Exception:
            return
        if "notify" in req:
            n = Gio.Notification.new(req["notify"].get("title", "MJ코인"))
            n.set_body(req["notify"].get("body", ""))
            n.set_priority(Gio.NotificationPriority.HIGH)
            Gtk.Application.get_default().send_notification(None, n)
            return
        if "subscribe" in req:
            codes = [c for c in req["subscribe"] if isinstance(c, str) and c.startswith(("KRW-", "USDT-", "BTC-"))]
            if codes and codes != self.codes:
                self.codes = codes
                if self.ws:
                    self.send_sub()
            return
        url = req.get("url", "")
        if not url.startswith(ALLOWED):
            return
        msg = Soup.Message.new("GET", url)
        self.session.send_and_read_async(msg, GLib.PRIORITY_DEFAULT, None, self.on_reply, (req["id"], msg))

    def on_reply(self, session, res, data):
        rid, msg = data
        try:
            body = session.send_and_read_finish(res).get_data().decode("utf-8", "replace")
            status = msg.get_status()
        except Exception as e:
            body, status = json.dumps(str(e)), 0
        self.js(f"window.mjReply({rid}, {status}, {json.dumps(body)})")

    # 실시간 연결
    def connect_ws(self):
        msg = Soup.Message.new("GET", WS_URL)
        self.session.websocket_connect_async(msg, None, None, GLib.PRIORITY_DEFAULT, None, self.on_ws_open)
        return False

    def on_ws_open(self, session, res):
        try:
            self.ws = session.websocket_connect_finish(res)
        except Exception as e:
            print("websocket 연결 실패:", e, file=sys.stderr)
            self.schedule_reconnect()
            return
        self.ws.set_keepalive_interval(30)
        self.ws.connect("message", self.on_ws_message)
        self.ws.connect("closed", lambda *_: self.schedule_reconnect())
        self.send_sub()
        self.retry = 2
        self.js(f"window.mjWsState({json.dumps('reopen' if self.connected_once else 'open')})")
        self.connected_once = True

    # 구독 보내기 (새로 보내면 업비트가 이전 구독을 통째로 바꿈)
    def send_sub(self):
        sub = [{"ticket": f"mj-coin-{GLib.get_real_time()}"},
               {"type": "ticker", "codes": self.codes},
               {"type": "trade", "codes": self.codes},
               {"format": "SIMPLE"}]
        self.ws.send_text(json.dumps(sub))

    def on_ws_message(self, _ws, _type, data):
        text = data.get_data().decode("utf-8", "replace")
        self.js(f"window.mjWs({json.dumps(text)})")

    def schedule_reconnect(self):
        self.ws = None
        self.js("window.mjWsState('closed')")
        GLib.timeout_add_seconds(self.retry, self.connect_ws)
        self.retry = min(self.retry * 2, 60)


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, title="MJ코인")
    win.set_default_size(1024, 640)
    view = WebKit.WebView()
    s = view.get_settings()
    s.set_allow_file_access_from_file_urls(True)
    s.set_enable_developer_extras(False)
    app.bridge = Bridge(view)
    def on_load(v, event):
        if event == WebKit.LoadEvent.FINISHED and app.bridge.ws is None and not app.bridge.connected_once:
            app.bridge.connect_ws()
    view.connect("load-changed", on_load)
    view.connect("notify::title", lambda v, _: win.set_title(v.get_title() or "MJ코인"))
    view.load_uri("file://" + os.path.join(HERE, "index.html"))
    win.set_child(view)
    win.present()


if __name__ == "__main__":
    app = Gtk.Application(application_id="io.github.kmj.MJCoin")
    app.connect("activate", on_activate)
    sys.exit(app.run(sys.argv))
