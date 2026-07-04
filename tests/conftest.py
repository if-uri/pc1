from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
NODE_PORT = int(os.environ.get("PC1_NODE_PORT", "28765"))
WP_PORT = int(os.environ.get("PC1_WP_PORT", "28080"))
MAILUI_PORT = int(os.environ.get("PC1_MAILUI_PORT", "28025"))
SMTP_PORT = int(os.environ.get("PC1_SMTP_PORT", "21025"))
VENV = ROOT / ".venv"


def urirun_cli() -> str:
    candidate = VENV / "bin" / "urirun"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("urirun")
    if not found:
        pytest.skip("no urirun CLI available; run `make venv` first")
    return found


def run_cmd(command: list[str], *, check: bool = True, timeout: int = 120,
            cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(command, cwd=cwd or ROOT, text=True, encoding="utf-8",
                        errors="replace", capture_output=True, timeout=timeout)
    if check and cp.returncode != 0:
        raise AssertionError(f"command failed with {cp.returncode}: {' '.join(command)}\n{cp.stderr}\n{cp.stdout}")
    return cp


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D102
        return None


def wait_http(url: str, timeout: float = 180.0) -> None:
    """Poll until the URL answers with any HTTP status < 500.

    Redirects are NOT followed: services on the compose network redirect to
    their internal aliases (e.g. http://wordpress), unreachable from the host.
    """
    opener = urllib.request.build_opener(_NoRedirect)
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with opener.open(url, timeout=5) as resp:
                if resp.status < 500:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return
            last = str(exc)
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f"{url} not reachable: {last}")


@pytest.fixture(scope="session")
def workplace():
    """Compose the mini-internet up, register the desktop node in a mesh."""
    if shutil.which("docker") is None:
        pytest.skip("docker is not available")
    cli = urirun_cli()
    run_cmd(["docker", "compose", "up", "-d", "--build"], timeout=900)
    wait_http(f"http://127.0.0.1:{NODE_PORT}/health")
    wait_http(f"http://127.0.0.1:{MAILUI_PORT}/")
    wait_http(f"http://127.0.0.1:{WP_PORT}/")
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "screenshots").mkdir(exist_ok=True)
    mesh = REPORT_DIR / "mesh.json"
    run_cmd([cli, "host", "init", "--config", str(mesh)], check=False)
    run_cmd([cli, "host", "add-node", "pc1", f"http://127.0.0.1:{NODE_PORT}",
             "--kind", "pc", "--tag", "workplace", "--config", str(mesh)])
    yield {"cli": cli, "mesh": mesh}
    if os.environ.get("PC1_KEEP_UP", "") != "1":
        run_cmd(["docker", "compose", "down", "-v"], check=False, timeout=300)


def dispatch(ctx: dict, uri: str, payload: dict) -> dict:
    cp = run_cmd([ctx["cli"], "host", "run", "pc1", uri,
                  "--config", str(ctx["mesh"]), "--payload", json.dumps(payload)])
    document = json.loads(cp.stdout)
    assert document.get("ok") is True, f"{uri} failed: {cp.stdout[:800]}"
    result = document.get("result", document)
    value = result.get("value") if isinstance(result, dict) else None
    return value if isinstance(value, dict) else result


def save_screenshot(ctx: dict, name: str) -> Path:
    import base64

    result = dispatch(ctx, "kvm://host/screen/query/capture", {"base64": True})
    encoded = result.get("pngBase64", "")
    assert encoded, f"no inline image: {json.dumps(result)[:300]}"
    target = REPORT_DIR / "screenshots" / f"{name}.png"
    target.write_bytes(base64.b64decode(encoded))
    return target


def wait_on_screen(ctx: dict, text: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    verdict: dict = {}
    while time.time() < deadline:
        verdict = dispatch(ctx, "kvm://host/ui/query/verify", {"expect": text})
        if verdict.get("present"):
            return
        time.sleep(3)
    raise AssertionError(f"'{text}' never appeared on screen: {verdict}")
