#!/bin/bash
# Boot the virtual desktop stack, then serve the urirun node in the foreground.
set -euo pipefail

SCREEN="${SCREEN_GEOMETRY:-1440x900x24}"
NODE_NAME="${NODE_NAME:-pc1}"

Xvfb :99 -screen 0 "$SCREEN" -nolisten tcp &
for _ in $(seq 1 50); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep 0.2; done

openbox &
x11vnc -display :99 -forever -shared -nopw -quiet -bg
websockify --web=/usr/share/novnc 6080 localhost:5900 &

# Expose every installed connector binding (kvm://, app://) as the node registry.
/opt/urirun/bin/urirun discover > /opt/registry.json

exec /opt/urirun/bin/urirun node serve \
  --registry /opt/registry.json \
  --name "$NODE_NAME" \
  --host 0.0.0.0 \
  --port 8765 \
  --execute \
  --allow 'kvm://*' \
  --allow 'app://*'
