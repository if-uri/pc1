# pc1 — a "digital workplace" desktop node.
#   Xvfb -> openbox -> x11vnc -> noVNC (live human view on :6080)
#   + Chromium (real browser for the office web apps on the compose network)
#   + urirun node serve --execute with urirun-connector-kvm (kvm:// app://).
# Debian base: chromium is a real package here (on Ubuntu it is a snap).
#
# The urirun dependency chain is not published on PyPI yet, so wheels are
# vendored under ./vendor. The urirun wheel also bundles a STALE copy of
# urirun_connector_router (upstream packaging bug), so the core is installed
# first and the real dependency wheels afterwards to win the file clobber.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl procps \
      python3 python3-venv python3-pip \
      xvfb x11-utils openbox x11vnc novnc websockify \
      xdotool wmctrl scrot imagemagick tesseract-ocr \
      chromium xterm fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY vendor/ /opt/vendor/
RUN python3 -m venv /opt/urirun \
    && /opt/urirun/bin/pip install --no-cache-dir -U pip \
    && /opt/urirun/bin/pip install --no-cache-dir --no-deps /opt/vendor/urirun-0*.whl \
    && /opt/urirun/bin/pip install --no-cache-dir \
         /opt/vendor/urirun_contract-*.whl /opt/vendor/urirun_connector_router-*.whl \
         /opt/vendor/urirun_flow-*.whl /opt/vendor/urirun_connector_kvm-*.whl \
         jsonschema pydantic mss Pillow pytesseract \
    && /opt/urirun/bin/python -c "import urirun.node.mesh" \
    && /opt/urirun/bin/urirun --version

COPY entrypoint.sh /usr/local/bin/pc1-desktop
RUN chmod +x /usr/local/bin/pc1-desktop

EXPOSE 6080 8765
ENTRYPOINT ["/usr/local/bin/pc1-desktop"]
