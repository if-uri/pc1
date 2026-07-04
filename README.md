# pc1 — digital workplace E2E lab for urirun

A self-contained "human at a desk" test environment: one Docker network hosts a
virtual desktop and a local mini-internet of real office applications. Test
scenarios automate daily work the way a person does it — open the browser, read
mail, log into the CMS — driven **exclusively through urirun mesh URIs**
(`kvm://`, `app://`) against a real `urirun node` running inside the desktop.

```
┌─ docker network ────────────────────────────────────────────────┐
│ desktop   Xvfb+openbox+Chromium+noVNC + urirun node (kvm://)    │
│ mail      Mailpit  — real SMTP + webmail UI    http://mail:8025 │
│ wordpress WordPress+MariaDB (auto-installed)   http://wordpress │
│ intranet  nginx static start page              http://intranet  │
└─────────────────────────────────────────────────────────────────┘
```

Watch every test live in your browser: **http://127.0.0.1:26080/vnc.html**

## Scenarios (tests/test_daily_work.py)

1. **Workplace up** — node surface (`kvm://host/doctor`), services reachable.
2. **Invoice mail journey** — a real SMTP message lands in Mailpit; the agent
   opens Chromium at the webmail, OCR-verifies the subject on screen, clicks
   the message like a human (`ui/command/click-text`), verifies the amount.
3. **CMS login journey** — navigates to `wp-login.php` via ctrl+L typing,
   types credentials (autofocus + Tab), OCR-verifies the WordPress Dashboard.

Each step is closed-loop (act → `ui/query/verify` → screenshot) with evidence
in `reports/screenshots/`.

## Run

```bash
make venv   # host-side urirun CLI (mesh) + pytest, from vendored wheels
make test   # composes the workplace up and runs the journeys
make watch  # prints the live-view URLs
make down   # tear down + wipe volumes
```

`PC1_KEEP_UP=1 make test` leaves the workplace running afterwards.

## Notes

- Wheels in `desktop/vendor/` are vendored because the urirun dependency chain
  (`urirun-contract`, `urirun-connector-router`, `urirun-flow>=0.2.2`) is not
  on PyPI yet. The urirun wheel also bundles a stale `urirun_connector_router`
  copy, so install order matters (core first) — see desktop/Dockerfile.
- OCR practices: antialiased fonts, `--force-device-scale-factor=1.4`, and
  markers without O/0/I/l lookalikes (`FAKTURA E2E-77 READY`).
- WordPress admin: `admin` / `urirun-e2e-Pass1` (test-only).
- Roadmap: Roundcube (IMAP webmail), LibreOffice journeys, Ollama NL planner,
  Nextcloud, xrdp — see the phase plan in the parent discussion.
