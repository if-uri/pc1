# pc1 — digital workplace E2E lab for urirun

**net-user-pl** — wirtualny internet: lokalny CA, proxy Caddy z prawdziwym TLS dla wirtualnych domen, DNS (aliasy Dockera), wirtualny bank mbank.pl z logowaniem kodem SMS, portal login.gov.pl (Profil Zaufany stub), bramka SMS (wirtualny operator) i szyna zdarzeń URI — jedno źródło prawdy zapisujące każdą akcję jako adres URI.

**mobile-user-pl** — wirtualny telefon Jana: aplikacja SMS (phone.jan.pl) czytająca skrzynkę operatora; człowiek odczytuje tu kod, a automat czyta tę samą skrzynkę przez sieć.

**pc-user-pl** — komputer Jana Kowalskiego: rozszerza desktop pc1 o zaufanie do CA (systemowe + NSS Chromium) i wpięcie w sieć netpl, więc Chromium widzi ważny HTTPS na mbank.pl jak w prawdziwym internecie. Sterowany wyłącznie przez mesh urirun (kvm://, app://).

**pc1** — orkiestracja: trzy powyższe jako git submodules + compose.twin.yml, cele make twin-* i flagowy test.

Flagowy scenariusz — działa (2 passed, odtworzone z publikacji)

Jan loguje się do banku kodem SMS, cały łańcuch przez mesh, z zamkniętą pętlą OCR i dowodami w zrzutach. Zweryfikowany ślad przyczynowy URI:
```
net://twin/session/command/start
bank://mbank.pl/login/query/form
pc://jan-kowalski/browser/command/navigate      ← Chromium otwiera mbank.pl (ważny TLS)
pc://jan-kowalski/bank/command/submit-login     ← wpisuje login/hasło
bank://mbank.pl/otp/command/request             ← bank żąda kodu
sms://+48500100200/inbox/command/deliver        ← SMS trafia na telefon
phone://jan/sms/query/read                      ← automat czyta kod z telefonu
pc://jan-kowalski/bank/command/submit-otp        ← wpisuje kod w banku
bank://mbank.pl/session/command/login-success
bank://mbank.pl/dashboard/query/view            ← "PULPIT BANKOWY, Jan Kowalski, Saldo 4 812,37 PLN"
```
Dokładnie to, o co prosiłeś: kod, który normalnie odczytałby z telefonu przez SMS, jest przez wirtualną sieć pobierany z wirtualnego telefonu i wpisywany do wirtualnego banku — a każda operacja (sieć, komputer, telefon, artefakty) jest adresem URI, więc cały epizod jest odtwarzalny i pozwala testować dowolną funkcjonalność urirun.



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

## Digital twin: a full isolated internet + computer + phone

Beyond the office stack above, pc1 orchestrates a complete **isolated digital
twin** — a virtual internet, an average citizen's computer, and his phone — so
urirun automations run as if in production, including SMS second factors. The
three worlds are git submodules:

- [net-user-pl](https://github.com/if-uri/net-user-pl) — virtual internet: local CA, TLS proxy, DNS, bank (`mbank.pl`), gov (`login.gov.pl`), SMS carrier, URI event bus.
- [pc-user-pl](https://github.com/if-uri/pc-user-pl) — Jan Kowalski's computer (desktop + urirun kvm node, CA-trusted).
- [mobile-user-pl](https://github.com/if-uri/mobile-user-pl) — Jan's phone (SMS app, `phone.jan.pl`).

```bash
make twin-init    # submodules + CA + desktop images
make twin-up      # bring the whole world up
make twin-test    # Jan logs into his bank with an SMS code, end to end
make twin-events  # print the URI causal trace of the episode
```

**The flagship journey** (`tests/test_twin_bank_sms.py`): Jan opens `https://mbank.pl`
in Chromium (valid HTTPS via the local CA), types his credentials, the bank
sends a one-time code over the virtual carrier, the automat reads it from Jan's
phone inbox — exactly the code a person types off their handset — enters it, and
reaches the dashboard. Every step is a URI event on the bus:

```
net://twin/session/command/start
bank://mbank.pl/login/query/form
pc://jan-kowalski/browser/command/navigate
pc://jan-kowalski/bank/command/submit-login
bank://mbank.pl/otp/command/request
sms://+48500100200/inbox/command/deliver
phone://jan/sms/query/read
pc://jan-kowalski/bank/command/submit-otp
bank://mbank.pl/session/command/login-success
bank://mbank.pl/dashboard/query/view
```

so the whole real-life episode is replayable and every urirun feature can be
exercised against a faithful causal log. Watch it live at
`http://127.0.0.1:26080/vnc.html`.

**Safety:** the twin's root CA is trusted only inside the desktop container,
never on your host — see net-user-pl's README.

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
