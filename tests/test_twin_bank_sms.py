"""Flagship digital-twin journey: Jan Kowalski logs into his bank with an SMS code.

The whole isolated world runs in Docker (net-user-pl + mobile-user-pl +
pc-user-pl). Jan's desktop is driven purely through the urirun mesh (`kvm://`).
The bank sends a one-time code over the virtual carrier; the automat reads it
from Jan's phone inbox — exactly the second factor a person types off their
handset — and completes the login. Every real-world step exists as a URI event
on the eventbus, so the episode is fully replayable.

    net (virtual internet) --TLS--> bank mbank.pl --SMS--> carrier --> phone
                                                                         |
    desktop Chromium (kvm://) types login + OTP <----- automat reads ----+

Gated: URIRUN_TWIN_E2E=1 (needs Docker + the built images).
Live view: http://127.0.0.1:26080/vnc.html
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TWIN_COMPOSE = ROOT / "compose.twin.yml"
NODE_PORT = int(os.environ.get("PC1_NODE_PORT", "28765"))
EVENTBUS_PORT = int(os.environ.get("EVENTBUS_PORT", "28800"))
MSISDN = "+48500100200"
REPORT_DIR = ROOT / "reports"
SHOTS = REPORT_DIR / "screenshots" / "twin"

pytestmark = pytest.mark.skipif(
    os.environ.get("URIRUN_TWIN_E2E", "") != "1",
    reason="twin E2E runs only with URIRUN_TWIN_E2E=1 (needs Docker + built images)",
)

CHROMIUM_ARGS = ["--no-sandbox", "--disable-gpu", "--no-first-run",
                 "--disable-features=Translate", "--force-device-scale-factor=1.35",
                 "--start-maximized"]


def _cli() -> str:
    cand = ROOT / ".venv" / "bin" / "urirun"
    return str(cand) if cand.exists() else "urirun"


def _run(cmd: list[str], *, check=True, timeout=180, cwd=None):
    cp = subprocess.run(cmd, cwd=cwd or ROOT, text=True, capture_output=True, timeout=timeout)
    if check and cp.returncode != 0:
        raise AssertionError(f"failed: {' '.join(cmd)}\n{cp.stderr}\n{cp.stdout}")
    return cp


def _dispatch(ctx, uri, payload):
    cp = _run([ctx["cli"], "host", "run", "pc1", uri, "--config", ctx["mesh"],
               "--payload", json.dumps(payload)])
    doc = json.loads(cp.stdout)
    assert doc.get("ok") is True, f"{uri}: {cp.stdout[:600]}"
    res = doc.get("result", doc)
    val = res.get("value") if isinstance(res, dict) else None
    return val if isinstance(val, dict) else res


def _shot(ctx, name):
    res = _dispatch(ctx, "kvm://host/screen/query/capture", {"base64": True})
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / f"{name}.png").write_bytes(base64.b64decode(res["pngBase64"]))


def _wait_screen(ctx, text, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        if _dispatch(ctx, "kvm://host/ui/query/verify", {"expect": text}).get("present"):
            return
        time.sleep(3)
    raise AssertionError(f"'{text}' never appeared on screen")


def _type(ctx, text):
    _dispatch(ctx, "kvm://host/input/command/type", {"text": text})


def _key(ctx, key):
    _dispatch(ctx, "kvm://host/input/command/key", {"key": key})


def _open(ctx, url):
    _key_combo(ctx, "ctrl+l")
    _type(ctx, url)
    _key(ctx, "Return")


def _key_combo(ctx, keys):
    _dispatch(ctx, "kvm://host/input/command/key", {"keys": keys})


def _events(scheme=None):
    url = f"http://127.0.0.1:{EVENTBUS_PORT}/events"
    if scheme:
        url += f"?scheme={scheme}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.load(resp)["events"]


def _emit(uri, actor="jan.kowalski", **payload):
    body = json.dumps({"uri": uri, "actor": actor, "payload": payload}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{EVENTBUS_PORT}/emit", data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5).read()


def _read_otp_from_phone(since_id=0) -> str:
    """Glance at Jan's phone: read the latest OTP from the SMS inbox."""
    out = _run(["docker", "run", "--rm", "--network", "netpl", "curlimages/curl:latest",
                "-s", f"http://sms-gateway:9810/inbox/{MSISDN}?since_id={since_id}"]).stdout
    msgs = json.loads(out).get("messages", [])
    for m in reversed(msgs):
        digits = "".join(c for c in m["text"] if c.isdigit())
        if len(digits) >= 6:
            _emit("phone://jan/sms/query/read", actor="jan.kowalski", code=digits[-6:])
            return digits[-6:]
    raise AssertionError(f"no OTP in phone inbox: {msgs}")


@pytest.fixture(scope="module")
def twin():
    if not TWIN_COMPOSE.exists():
        pytest.skip("compose.twin.yml missing")
    _run(["docker", "network", "create", "netpl"], check=False)
    _run(["bash", str(ROOT.parent / "net-user-pl" / "ca" / "gen.sh")], check=False)
    _run(["docker", "compose", "-f", str(TWIN_COMPOSE), "up", "-d"], timeout=900)
    # wait for the desktop node
    end = time.time() + 180
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{NODE_PORT}/health", timeout=4)
            break
        except Exception:
            time.sleep(3)
    else:
        pytest.fail("desktop node never came up")
    mesh = str(REPORT_DIR / "mesh.json")
    REPORT_DIR.mkdir(exist_ok=True)
    cli = _cli()
    _run([cli, "host", "init", "--config", mesh], check=False)
    _run([cli, "host", "add-node", "pc1", f"http://127.0.0.1:{NODE_PORT}",
          "--kind", "pc", "--tag", "twin", "--config", mesh])
    ctx = {"cli": cli, "mesh": mesh}
    yield ctx
    if os.environ.get("PC1_KEEP_UP", "") != "1":
        _run(["docker", "compose", "-f", str(TWIN_COMPOSE), "down", "-v"], check=False, timeout=300)


def test_twin_services_and_uri_bus(twin):
    assert "capture" in str(_dispatch(twin, "kvm://host/doctor/query/report", {}))
    _emit("net://twin/session/command/start", actor="harness")
    assert any(e["uri"].startswith("net://") for e in _events(scheme="net"))


def test_jan_logs_into_bank_with_sms_code(twin):
    seen_before = _events()
    last_sms_id = 0

    # 1. Jan opens his bank in the browser
    _dispatch(twin, "app://host/desktop/command/launch",
              {"app": "chromium", "args": [*CHROMIUM_ARGS, "https://mbank.pl/"], "settle": 7})
    _emit("pc://jan-kowalski/browser/command/navigate", url="https://mbank.pl/")
    _wait_screen(twin, "Login", timeout=90)
    _shot(twin, "10-bank-login")

    # 2. types credentials like a human (login autofocus, Tab to password)
    _type(twin, "jan.kowalski")
    _key(twin, "Tab")
    _type(twin, "Haslo123")
    _emit("pc://jan-kowalski/bank/command/submit-login")
    _key(twin, "Return")

    # 3. bank asks for the SMS code
    _wait_screen(twin, "kod", timeout=90)
    _shot(twin, "11-otp-prompt")

    # 4. Jan glances at his phone and reads the one-time code
    code = _read_otp_from_phone(since_id=last_sms_id)
    assert len(code) == 6

    # 5. types the code into the bank
    _type(twin, code)
    _emit("pc://jan-kowalski/bank/command/submit-otp", code=code)
    _key(twin, "Return")

    # 6. dashboard reached
    _wait_screen(twin, "PULPIT", timeout=90)
    _shot(twin, "12-bank-dashboard")

    # 7. the full URI causal chain exists on the bus
    all_uris = [e["uri"] for e in _events()]
    assert any(u.startswith("bank://mbank.pl/otp/command/request") for u in all_uris)
    assert any(u.startswith(f"sms://{MSISDN}/inbox/command/deliver") for u in all_uris)
    assert any(u.startswith("phone://jan/sms/query/read") for u in all_uris)
    assert any(u.startswith("bank://mbank.pl/session/command/login-success") for u in all_uris)
    assert any(u.startswith("pc://jan-kowalski/") for u in all_uris)
    (REPORT_DIR / "twin-uri-trace.json").write_text(
        json.dumps(_events(), indent=2, ensure_ascii=False), encoding="utf-8")
