#!/usr/bin/env bash
#
# Install (or update) the equal-loudness filter API as a systemd service.
#
#     sudo ./deploy/install.sh
#
# Idempotent: run it again to ship a new presets.json or a changed app.py, and
# it will reinstall what differs and restart the service. It is the same script
# on a development box and on the droplet -- the unit uses DynamicUser, so
# there is no account to create and nothing here is distribution-specific.
#
# What it does NOT do: fit anything. presets.json is built by
# precompute_presets.py on a machine that holds the ISO Table 1 data, and is
# copied here as data. The service never imports NumPy or SciPy.

set -euo pipefail

PREFIX="${PREFIX:-/opt/iso226}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
SERVICE="iso226-api"

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname -- "$HERE")"

die() {
    echo "install.sh: $*" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || die "run me with sudo -- this writes $PREFIX and $UNIT_DIR"

for required in "$REPO/web/app.py" "$REPO/web/presets.json" \
                "$REPO/web/requirements.txt" "$HERE/$SERVICE.service"; do
    [[ -f $required ]] || die "missing $required"
done

# Python comes from the host. A venv keeps Flask off the system site-packages,
# which is what the distribution's own packaging expects of an application.
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || die "no $PYTHON on PATH"

echo "Installing to $PREFIX"
install -d -m 755 "$PREFIX"

if [[ ! -x "$PREFIX/venv/bin/python" ]]; then
    echo "  creating venv"
    "$PYTHON" -m venv "$PREFIX/venv"
fi

echo "  installing runtime dependencies (flask, gunicorn -- no numpy or scipy)"
"$PREFIX/venv/bin/pip" install --quiet --upgrade \
    --requirement "$REPO/web/requirements.txt"

# World-readable, root-owned: the service reads these as a transient user and
# must never be able to write them.
echo "  installing app.py and presets.json"
install -m 644 -o root -g root "$REPO/web/app.py" "$PREFIX/app.py"
install -m 644 -o root -g root "$REPO/web/presets.json" "$PREFIX/presets.json"

echo "  installing $SERVICE.service"
install -m 644 -o root -g root "$HERE/$SERVICE.service" \
    "$UNIT_DIR/$SERVICE.service"

systemctl daemon-reload
systemctl enable "$SERVICE.service"
systemctl restart "$SERVICE.service"

# The unit reports started as soon as gunicorn execs, which is before the
# workers have loaded the grid. Wait for an actual answer rather than declaring
# success on the strength of the process existing. Probed with the venv's own
# Python so the installer depends on nothing the service does not already have.
probe() {
    "$PREFIX/venv/bin/python" - "$1" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
    body = json.load(response)
coverage = body.get("coverage")
if coverage:
    print(f"  serving {coverage['preset_count']} presets, "
          f"offsets {coverage['offset_range_db']}")
PY
}

echo -n "  waiting for the service to answer"
for _ in $(seq 1 30); do
    if probe http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo " -- ok"
        probe http://127.0.0.1:8000/v1/meta
        exit 0
    fi
    echo -n "."
    sleep 1
done

echo " -- FAILED" >&2
systemctl --no-pager --lines=20 status "$SERVICE.service" >&2 || true
die "the service did not answer on 127.0.0.1:8000 within 30 s"
