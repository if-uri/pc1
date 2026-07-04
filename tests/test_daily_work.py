"""Daily-work user journeys on the pc1 digital workplace.

Every action goes through the urirun mesh (`urirun host run pc1 ...`) —
the harness never touches the container directly. The desktop's Chromium
browses the LOCAL mini-internet (Mailpit webmail, WordPress, intranet),
and each step is closed-loop: act -> wait/verify on screen (OCR) -> screenshot.
Watch live: http://127.0.0.1:26080/vnc.html
"""

from __future__ import annotations

import smtplib
import time
import urllib.request
from email.message import EmailMessage

from tests.conftest import SMTP_PORT, WP_PORT, dispatch, save_screenshot, wait_on_screen

# OCR-safe marker: no O/0, I/l/1 lookalikes
MAIL_SUBJECT = "FAKTURA E2E-77 READY"

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-gpu",
    "--no-first-run",
    "--disable-features=Translate",
    "--force-device-scale-factor=1.4",
    "--start-maximized",
]


def _open_url(ctx: dict, url: str) -> None:
    dispatch(ctx, "kvm://host/input/command/key", {"keys": "ctrl+l"})
    dispatch(ctx, "kvm://host/input/command/type", {"text": url})
    dispatch(ctx, "kvm://host/input/command/key", {"key": "Return"})


def test_node_up_and_services_reachable(workplace):
    report = dispatch(workplace, "kvm://host/doctor/query/report", {})
    assert "capture" in str(report)
    with urllib.request.urlopen(f"http://127.0.0.1:{WP_PORT}/?rest_route=/", timeout=10) as resp:
        assert resp.status == 200


def test_journey_read_invoice_mail_in_webmail(workplace):
    message = EmailMessage()
    message["From"] = "ksiegowosc@example.com"
    message["To"] = "pracownik@example.com"
    message["Subject"] = MAIL_SUBJECT
    message.set_content("Prosze zaksiegowac fakture E2E-77 na kwote 1234,56 PLN.")
    with smtplib.SMTP("127.0.0.1", SMTP_PORT, timeout=10) as smtp:
        smtp.send_message(message)

    dispatch(
        workplace, "app://host/desktop/command/launch",
        {"app": "chromium", "args": [*CHROMIUM_ARGS, "http://mail:8025"], "settle": 6},
    )
    wait_on_screen(workplace, "FAKTURA", timeout=90)
    save_screenshot(workplace, "10-webmail-inbox")

    # open the message like a human: click its subject line
    dispatch(workplace, "kvm://host/ui/command/click-text", {"text": "FAKTURA"})
    time.sleep(2)
    wait_on_screen(workplace, "1234", timeout=60)
    save_screenshot(workplace, "11-webmail-message")


def test_journey_login_to_wordpress_dashboard(workplace):
    _open_url(workplace, "http://wordpress/wp-login.php")
    wait_on_screen(workplace, "Password", timeout=90)
    save_screenshot(workplace, "20-wp-login")

    # wp-login autofocuses the username field; Tab moves to the password field
    dispatch(workplace, "kvm://host/input/command/type", {"text": "admin"})
    dispatch(workplace, "kvm://host/input/command/key", {"key": "Tab"})
    dispatch(workplace, "kvm://host/input/command/type", {"text": "urirun-e2e-Pass1"})
    dispatch(workplace, "kvm://host/input/command/key", {"key": "Return"})

    wait_on_screen(workplace, "Dashboard", timeout=90)
    save_screenshot(workplace, "21-wp-dashboard")
