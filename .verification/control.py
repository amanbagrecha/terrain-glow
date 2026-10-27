import argparse
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
PAGE = os.path.join(APP_DIR, "index.html")
RUNS = os.path.join(HERE, "runs")
STATE = os.path.join(RUNS, "current.json")
EXPORTS = os.path.join(APP_DIR, ".fused", "data", "exports")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SIZE = None
READY = "W && W.document.body && W.document.getElementById('gl') && !W.document.body.classList.contains('loading')"
LOGIN = "W && W.document.body && W.document.body.classList.contains('login')"
STUB = """
(() => {
  if (window === window.top) return;
  const S = window.__tgStub = { device: %(device)s, stamp: null, inFlight: false, loginCalls: 0, cancelCalls: 0, signInMs: %(sign_in_ms)s, fail: %(fail)s };
  const LOGIN = { login: true, creds_stamp: null, dem: { state: "login" }, img: { state: "login" } };
  let f;
  Object.defineProperty(window, "fused", { configurable: true, get: () => f, set: (v) => {
    f = v;
    if (S.device) f.device = S.device;
    const run = f.runPython;
    f.runPython = (py, params, opts) => S.stamp === null && String(py).endsWith("terrain.py") ? Promise.resolve(LOGIN) : run(py, params, opts);
  } });
  const real = window.fetch.bind(window);
  const json = (o, status) => new Response(JSON.stringify(o), { status: status || 200, headers: { "Content-Type": "application/json" } });
  let timer = 0;
  window.fetch = async (input, init) => {
    const u = new URL(typeof input === "string" ? input : input.url, location.href);
    if (u.pathname === "/api/canvases/status") return json({ cli_found: true, logged_in: S.stamp !== null, creds_stamp: S.stamp, login_in_flight: S.inFlight });
    if (u.pathname === "/api/canvases/login") {
      S.loginCalls++;
      if (S.fail) return json({ error: "stub failure" }, 500);
      S.inFlight = true;
      if (S.signInMs >= 0) timer = setTimeout(() => { S.inFlight = false; S.stamp = 1; }, S.signInMs);
      return json({ ok: true, login_in_flight: true });
    }
    if (u.pathname === "/api/canvases/login/cancel") { S.cancelCalls++; clearTimeout(timer); S.inFlight = false; return json({ ok: true, canceled: true }); }
    return real(input, init);
  };
})();
"""
CHECK_LAYOUT = """
const d = W.document, vw = W.innerWidth, vh = W.innerHeight, issues = [], info = [], coarse = W.matchMedia("(pointer: coarse)").matches;
const box = (el) => el.getBoundingClientRect(), pen = d.createElement("canvas").getContext("2d");
const shown = (el) => { const s = W.getComputedStyle(el); return s.display !== "none" && s.visibility !== "hidden" && +s.opacity > 0 && el.getClientRects().length > 0; };
const name = (el) => (el.id ? "#" + el.id : el.className ? "." + String(el.className).split(" ")[0] : el.tagName) + (el.textContent.trim() ? " '" + el.textContent.trim().slice(0, 24) + "'" : "");
const meet = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
const inside = (a, b) => a.left >= b.left - 1 && a.right <= b.right + 1 && a.top >= b.top - 1 && a.bottom <= b.bottom + 1;
const view = { left: 0, top: 0, right: vw, bottom: vh };
if (d.documentElement.scrollWidth > vw + 1) issues.push("page scrolls sideways");
const panel = d.getElementById("panel"), pb = box(panel), panelOn = shown(panel) && !d.body.classList.contains("panel-off");
if (panelOn && !inside(pb, view)) issues.push("panel is outside the viewport");
const body = d.getElementById("panelBody");
if (panelOn && body.scrollWidth > body.clientWidth + 1) issues.push("panel scrolls sideways");
if (panelOn) for (const el of panel.querySelectorAll("button, select, input")) {
  if (!shown(el) || el.closest(".pop:not(.on), .menu:not(.on), details:not([open]) .fineBody")) continue;
  const b = box(el);
  if (b.left < pb.left - 1 || b.right > pb.right + 1) issues.push("outside the panel: " + name(el));
  const cs = W.getComputedStyle(el), room = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  if (el.tagName === "SELECT") {
    pen.font = cs.font;
    if (pen.measureText(el.options[el.selectedIndex].text).width > room + 1) issues.push("text cut: " + name(el) + " '" + el.options[el.selectedIndex].text + "'");
    continue;
  }
  for (const t of el.childNodes) {
    if (t.nodeType !== 3 && !(t.nodeType === 1 && t.tagName === "SPAN" && shown(t))) continue;
    const r = d.createRange();
    r.selectNodeContents(t);
    if (r.getBoundingClientRect().width > room + 1) { issues.push("text cut: " + name(el)); break; }
  }
  if (coarse && b.height < 28 && !el.closest(".pop, .menu")) info.push("small target: " + name(el) + " " + Math.round(b.height) + "px");
}
const stage = d.getElementById("stageInner"), sb = box(stage);
const frame = d.getElementById("frame"), fb = box(frame);
if (!d.body.classList.contains("view-map")) {
  if (!inside(fb, view)) issues.push("frame is outside the viewport");
  if (panelOn && meet(fb, pb)) issues.push("frame is under the panel");
  if (fb.width < 120 || fb.height < 120) issues.push("frame is too small: " + Math.round(fb.width) + "x" + Math.round(fb.height));
}
const tb = box(d.getElementById("titleBox")), vs = box(d.getElementById("viewSwitch"));
if (meet(tb, vs)) issues.push("title meets the view switch");
if (!d.body.classList.contains("view-map") && meet(tb, fb)) issues.push("title meets the frame");
const pn = d.getElementById("placeName").firstChild;
if (pn) for (const m of pn.textContent.matchAll(/\\S+/g)) {
  const r = d.createRange();
  r.setStart(pn, m.index);
  r.setEnd(pn, m.index + m[0].length);
  if (new Set([...r.getClientRects()].map((q) => Math.round(q.top))).size > 1) { issues.push("title word broken: " + m[0]); break; }
}
if (panelOn && meet(vs, pb)) issues.push("view switch is under the panel");
for (const id of ["loading", "mapBar", "panelToggle", "tileChip"]) {
  const el = d.getElementById(id);
  if (!shown(el)) continue;
  const b = box(el);
  if (!inside(b, view)) issues.push(id + " is outside the viewport");
  if (panelOn && meet(b, pb)) issues.push(id + " is under the panel");
  if (id !== "mapBar" && meet(b, vs)) issues.push(id + " meets the view switch");
  if (meet(b, tb)) issues.push(id + " meets the title");
}
return { viewport: [vw, vh], coarse, issues, info, frame: [Math.round(fb.width), Math.round(fb.height)], stage: [Math.round(sb.width), Math.round(sb.height)], panel: panelOn ? [Math.round(pb.width), Math.round(pb.height)] : null };
"""


def origin():
    env = os.environ.get("FUSED_RENDER_ORIGIN")
    if env:
        return env.rstrip("/")
    with open(os.path.expanduser("~/.fused-render/server.json")) as f:
        return json.load(f)["origin"].rstrip("/")


def embed_url(query=""):
    url = f"{origin()}/explorer/embed/{PAGE.lstrip('/')}"
    return f"{url}?{query}" if query else url


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except OSError:
        sys.exit("No run. Start one with: control.py launch")


class Page:
    def __init__(self, state):
        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{state['port']}/json", timeout=5))
        page = [t for t in tabs if t["type"] == "page"][0]
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=180, suppress_origin=True)
        self.n = 0
        if SIZE:
            self.size(*SIZE)

    def bar(self):
        return round(self.js("const i = document.querySelector('iframe'); return i ? i.getBoundingClientRect().top : 0;"))

    def size(self, width, height, settle=0.8):
        self.send("Emulation.setDeviceMetricsOverride", width=width, height=height + self.bar(), deviceScaleFactor=1, mobile=False)
        time.sleep(settle)

    def shot(self, path, clip=None):
        extra = {"clip": {**clip, "scale": 1}} if clip else {}
        with open(path, "wb") as f:
            f.write(base64.b64decode(self.send("Page.captureScreenshot", format="png", **extra)["data"]))
        return path

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def js(self, body):
        expr = ("(async () => { const W = document.querySelector('iframe') && "
                "document.querySelector('iframe').contentWindow; " + body + " })()")
        r = self.send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:600])
        return r.get("result", {}).get("value")

    def wait(self, cond, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.js(f"return !!({cond});"):
                    return round(time.time() - t0, 1)
            except RuntimeError:
                pass
            time.sleep(0.5)
        raise TimeoutError(f"not true after {timeout} s: {cond}")

    def center(self, selector):
        return self.js(f"const e = W.document.querySelector({json.dumps(selector)}); e.scrollIntoView({{block: 'nearest'}}); "
                       "const b = e.getBoundingClientRect(); const f = document.querySelector('iframe').getBoundingClientRect(); "
                       "return [f.left + b.left + b.width / 2, f.top + b.top + b.height / 2];")

    def click_at(self, x, y):
        for kind in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)


def cmd_launch(args):
    os.makedirs(RUNS, exist_ok=True)
    if os.path.exists(STATE):
        sys.exit("A run is active. Run control.py cleanup first.")
    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(RUNS, run_id)
    profile = os.path.join(run_dir, "chrome-profile")
    os.makedirs(profile)
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={args.port}", f"--user-data-dir={profile}",
                             "--use-angle=metal", "--enable-gpu", "--hide-scrollbars",
                             f"--window-size={args.width},{args.height}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{args.port}/json/version", timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    state = {"run": run_id, "dir": run_dir, "port": args.port, "pid": proc.pid, "width": args.width,
             "height": args.height, "exports_before": sorted(os.listdir(EXPORTS)) if os.path.isdir(EXPORTS) else []}
    with open(STATE, "w") as f:
        json.dump(state, f)
    page = Page(state)
    page.send("Emulation.setDeviceMetricsOverride", width=args.width, height=args.height, deviceScaleFactor=1, mobile=False)
    if args.dark:
        page.send("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark"}])
    print(json.dumps({"run": run_id, "evidence": run_dir, "port": args.port, "origin": origin()}))


def cmd_doctor(args):
    state = load_state()
    out = {"origin": origin(), "run": state["run"]}
    cfg = json.load(urllib.request.urlopen(f"{out['origin']}/api/config", timeout=5))
    out["server_home"] = cfg.get("home")
    out["chrome_alive"] = subprocess.call(["kill", "-0", str(state["pid"])], stderr=subprocess.DEVNULL) == 0
    out["fused_login"] = os.path.exists(os.path.expanduser("~/.fused/credentials"))
    out["package_cached"] = os.path.isdir(os.path.join(APP_DIR, ".fused", "cache", "sentinel_utils"))
    out["page_marker"] = '<meta name="fused-app"' in open(PAGE).read(4096)
    out["ok"] = all((out["chrome_alive"], out["page_marker"]))
    print(json.dumps(out))
    sys.exit(0 if out["ok"] else 1)


def cmd_open(args):
    page = Page(load_state())
    page.send("Page.enable")
    if args.stub:
        source = STUB % {"device": json.dumps("phone-web" if args.stub == "login-phone" else None),
                         "sign_in_ms": json.dumps(args.sign_in_ms), "fail": json.dumps(args.stub == "login-fail")}
        page.send("Page.addScriptToEvaluateOnNewDocument", source=source)
    page.send("Page.navigate", url=embed_url(args.query))
    time.sleep(1.5)
    if SIZE:
        page.size(*SIZE)
    print(json.dumps({"url": embed_url(args.query), "stub": args.stub, "ready_s": page.wait(LOGIN if args.stub else READY, args.timeout)}))


def cmd_sweep(args):
    state = load_state()
    page = Page(state)
    if args.touch:
        page.send("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    bad = 0
    for size in args.sizes or [None]:
        if size:
            page.size(*size, args.settle)
        out = page.js(CHECK_LAYOUT)
        bad += bool(out["issues"])
        spec = "x".join(map(str, out["viewport"]))
        if args.shots:
            clip = {"x": 0, "y": page.bar(), "width": out["viewport"][0], "height": out["viewport"][1]}
            out["shot"] = page.shot(os.path.join(state["dir"], f"{args.shots}-{spec}.png"), clip)
        print(json.dumps({"size": spec, **out}))
    sys.exit(1 if bad else 0)


def cmd_eval(args):
    page = Page(load_state())
    print(json.dumps(page.js(args.body)))


def cmd_set(args):
    page = Page(load_state())
    pairs = dict(p.split("=", 1) for p in args.pairs)
    page.js(f"for (const [k, v] of Object.entries({json.dumps(pairs)})) W.fused.params.set(k, v); return 1;")
    time.sleep(1.0)
    print(json.dumps({"set": pairs, "ready_s": page.wait(READY, args.timeout)}))


def refuse_real_sign_in(page, selector):
    hit = page.js(f"const e = W.document.querySelector({json.dumps(selector)}); return !!(e && e.closest('#signIn') && !W.__tgStub);")
    if hit:
        sys.exit("Refused: Sign in without --stub starts a real Fused sign-in in the browser of this computer.")


def cmd_click(args):
    page = Page(load_state())
    refuse_real_sign_in(page, args.selector)
    x, y = page.center(args.selector)
    page.click_at(x, y)
    time.sleep(args.settle)
    print(json.dumps({"clicked": args.selector, "at": [round(x), round(y)]}))


def cmd_type(args):
    page = Page(load_state())
    x, y = page.js(f"const e = W.document.querySelector({json.dumps(args.selector)}); const b = e.getBoundingClientRect(); "
                   "const f = document.querySelector('iframe').getBoundingClientRect(); return [f.left + b.left + 12, f.top + b.top + b.height / 2];")
    page.click_at(x, y)
    page.js(f"const e = W.document.querySelector({json.dumps(args.selector)}); const r = W.document.createRange(); "
            "r.selectNodeContents(e); const s = W.getSelection(); s.removeAllRanges(); s.addRange(r); return 1;")
    page.send("Input.insertText", text=args.text)
    time.sleep(0.4)
    print(json.dumps({"typed": args.text, "into": args.selector}))


def cmd_keys(args):
    page = Page(load_state())
    page.send("Input.insertText", text=args.text)
    time.sleep(args.settle)
    print(json.dumps({"typed": args.text}))


def cmd_select(args):
    page = Page(load_state())
    page.js(f"const e = W.document.querySelector({json.dumps(args.selector)}); e.focus(); e.value = {json.dumps(args.value)}; "
            "e.dispatchEvent(new W.Event('change', {bubbles: true})); return 1;")
    time.sleep(1.0)
    print(json.dumps({"selected": args.value, "in": args.selector}))


def cmd_turn_wheel(args):
    import math

    page = Page(load_state())
    cx, cy = page.center("#dial")
    radius = page.js("return W.document.getElementById('dial').getBoundingClientRect().width / 2;") * 0.8
    start = float(page.js("return W.fused.params.get('az') || '315';"))
    steps = 12
    path = [start + (args.degrees - start) * i / steps for i in range(steps + 1)]
    pts = [(cx + math.sin(math.radians(a)) * radius, cy - math.cos(math.radians(a)) * radius) for a in path]
    page.send("Input.dispatchMouseEvent", type="mousePressed", x=pts[0][0], y=pts[0][1], button="left", buttons=1, clickCount=1)
    for x, y in pts[1:]:
        page.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y, button="left", buttons=1)
        time.sleep(0.04)
    page.send("Input.dispatchMouseEvent", type="mouseReleased", x=pts[-1][0], y=pts[-1][1], button="left", clickCount=1)
    time.sleep(0.6)
    print(json.dumps({"from": start, "to": args.degrees, "az_now": page.js("return W.fused.params.get('az');")}))


def cmd_touch(args):
    page = Page(load_state())
    refuse_real_sign_in(page, args.selector)
    page.send("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    cx, cy = page.center(args.selector)
    read = "return {dist: W.fused.params.get('dist'), yaw: W.fused.params.get('yaw'), pitch: W.fused.params.get('pitch')};"
    before = page.js(read)

    def points(t):
        if args.pinch:
            r = 40 + 40 * (args.pinch - 1) * t
            return [{"x": cx - r, "y": cy, "id": 0}, {"x": cx + r, "y": cy, "id": 1}]
        return [{"x": cx + args.drag * t, "y": cy, "id": 0}]

    page.send("Input.dispatchTouchEvent", type="touchStart", touchPoints=points(0))
    for i in range(1, 11):
        page.send("Input.dispatchTouchEvent", type="touchMove", touchPoints=points(i / 10))
        time.sleep(0.03)
    page.send("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    time.sleep(0.8)
    print(json.dumps({"before": before, "after": page.js(read)}))


def cmd_state(args):
    page = Page(load_state())
    keys = ["place", "name", "ratio", "quality", "comp", "layer", "look", "az", "alt", "view", "cap", "ct"]
    print(json.dumps(page.js(
        "const P = W.fused.params; const d = W.document; return {params: Object.fromEntries("
        + json.dumps(keys) + ".map((k) => [k, P.get(k)])), loading: d.body.classList.contains('loading'), "
        "login: d.body.classList.contains('login'), title: d.getElementById('placeName').textContent, "
        "resolution: d.getElementById('resInfo').textContent, footer: d.getElementById('footInfo').textContent, "
        "caption: d.querySelector('#cap .ct').textContent, toast: d.getElementById('toast').textContent, "
        "error: d.getElementById('loadErr').classList.contains('on') ? d.getElementById('loadErrMsg').textContent : ''};")))


def cmd_wait(args):
    page = Page(load_state())
    print(json.dumps({"waited_s": page.wait(args.condition, args.timeout)}))


def cmd_shot(args):
    state = load_state()
    page = Page(state)
    path = os.path.join(state["dir"], args.name if args.name.endswith(".png") else args.name + ".png")
    print(json.dumps({"screenshot": page.shot(path)}))


def cmd_exports(args):
    state = load_state()
    now = sorted(os.listdir(EXPORTS)) if os.path.isdir(EXPORTS) else []
    new = [n for n in now if n not in state["exports_before"] or os.path.getmtime(os.path.join(EXPORTS, n)) > os.path.getmtime(STATE)]
    files = []
    for n in new:
        src = os.path.join(EXPORTS, n)
        shutil.copy2(src, os.path.join(state["dir"], n))
        files.append({"name": n, "bytes": os.path.getsize(src)})
    print(json.dumps({"new_exports": files, "copied_to": state["dir"]}))


def cmd_cleanup(args):
    state = load_state()
    try:
        os.killpg(state["pid"], signal.SIGTERM)
    except OSError:
        pass
    time.sleep(0.5)
    shutil.rmtree(os.path.join(state["dir"], "chrome-profile"), ignore_errors=True)
    os.remove(STATE)
    print(json.dumps({"stopped_pid": state["pid"], "evidence_kept": state["dir"], "files": sorted(os.listdir(state["dir"]))}))


def size_arg(text):
    try:
        w, h = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"size must be WIDTHxHEIGHT, for example 390x844, not {text!r}")
    return w, h


def main():
    ap = argparse.ArgumentParser(description="Drive Terrain Glow in a headless Chrome for verification.")
    ap.add_argument("--size", type=size_arg, help="app size for this command, for example 390x844 (the override ends with the command)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("launch", help="start a private headless Chrome and a run folder")
    p.add_argument("--port", type=int, default=9411)
    p.add_argument("--width", type=int, default=1440)
    p.add_argument("--height", type=int, default=900)
    p.add_argument("--dark", action="store_true")
    p.set_defaults(fn=cmd_launch)
    sub.add_parser("doctor", help="check server, browser, login, package").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("open", help="open the app with URL params and wait until it is drawn")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--stub", choices=["login", "login-phone", "login-fail"],
                   help="answer terrain.py and the sign-in API in the page as if signed out, then wait for the login card")
    p.add_argument("--sign-in-ms", type=int, default=3000, help="with --stub, the stub sign-in ends after this time (-1: never)")
    p.set_defaults(fn=cmd_open)
    p = sub.add_parser("sweep", help="check layout (and take screenshots) at each app size, for example 390x844; no size: the current one")
    p.add_argument("sizes", nargs="*", type=size_arg)
    p.add_argument("--touch", action="store_true", help="touch input on, so (pointer: coarse) rules apply")
    p.add_argument("--shots", default="", help="screenshot name prefix; no screenshots without it")
    p.add_argument("--settle", type=float, default=1.0)
    p.set_defaults(fn=cmd_sweep)
    p = sub.add_parser("eval", help="print the value of a JS function body (W = app window)")
    p.add_argument("body")
    p.set_defaults(fn=cmd_eval)
    p = sub.add_parser("set", help="set URL params for preconditions only (not proof), then wait until drawn")
    p.add_argument("pairs", nargs="+")
    p.add_argument("--timeout", type=int, default=180)
    p.set_defaults(fn=cmd_set)
    p = sub.add_parser("click", help="click an element (CSS selector in the app frame) with a real mouse event")
    p.add_argument("selector")
    p.add_argument("--settle", type=float, default=0.8)
    p.set_defaults(fn=cmd_click)
    p = sub.add_parser("type", help="replace the text of an editable element (caption)")
    p.add_argument("selector")
    p.add_argument("text")
    p.set_defaults(fn=cmd_type)
    p = sub.add_parser("keys", help="type text into the focused field (for example after: click '#q')")
    p.add_argument("text")
    p.add_argument("--settle", type=float, default=0.5)
    p.set_defaults(fn=cmd_keys)
    p = sub.add_parser("select", help="choose an option of a native select and fire its change event")
    p.add_argument("selector")
    p.add_argument("value")
    p.set_defaults(fn=cmd_select)
    p = sub.add_parser("turn-wheel", help="drag the sun around the light wheel to an azimuth in degrees")
    p.add_argument("degrees", type=float)
    p.set_defaults(fn=cmd_turn_wheel)
    p = sub.add_parser("touch", help="touch gesture on an element: --pinch <spread factor> or --drag <px to the right>")
    p.add_argument("selector")
    p.add_argument("--pinch", type=float, default=0)
    p.add_argument("--drag", type=float, default=0)
    p.set_defaults(fn=cmd_touch)
    sub.add_parser("state", help="print params and visible status as JSON").set_defaults(fn=cmd_state)
    p = sub.add_parser("wait", help="wait until a JS condition (W = app window) is true")
    p.add_argument("condition")
    p.add_argument("--timeout", type=int, default=60)
    p.set_defaults(fn=cmd_wait)
    p = sub.add_parser("shot", help="save a screenshot into the run folder")
    p.add_argument("name")
    p.set_defaults(fn=cmd_shot)
    sub.add_parser("exports", help="copy files the app exported during this run into the run folder").set_defaults(fn=cmd_exports)
    sub.add_parser("cleanup", help="stop this run's Chrome, keep the evidence").set_defaults(fn=cmd_cleanup)
    args = ap.parse_args()
    global SIZE
    SIZE = args.size
    args.fn(args)


if __name__ == "__main__":
    main()
