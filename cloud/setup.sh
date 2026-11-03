#!/usr/bin/env bash
# Cloud-session bootstrap for /SIPs (Claude Code on the web / cloud container).
# Idempotent. Safe to run every time. Does nothing harmful on a local machine.
set -e
cd "$(dirname "$0")/.."

# 1) `py` launcher shim — the SIPs skill calls `py <script>` (Windows launcher) everywhere.
#    Pins TZ=Asia/Taipei so date.today()/datetime.now() behave exactly like the user's local box.
if ! command -v py >/dev/null 2>&1; then
  SHIM_DIR=/usr/local/bin; [ -w "$SHIM_DIR" ] || { SHIM_DIR="$HOME/.local/bin"; mkdir -p "$SHIM_DIR"; }
  printf '#!/bin/sh\nexport TZ="${TZ:-Asia/Taipei}"\nexec python3 "$@"\n' > "$SHIM_DIR/py"
  chmod +x "$SHIM_DIR/py"
  echo "[cloud-setup] created py shim at $SHIM_DIR/py"
fi

# 2) Playwright: the container ships `playwright` + Chromium preinstalled. Scripts fall back to it
#    when @playwright/test is absent. NEVER run `npm install` / `playwright install` here.
node -e "require('playwright')" 2>/dev/null && echo "[cloud-setup] playwright OK" || echo "[cloud-setup] WARN: playwright missing"

# 3) scikit-learn pinned to the version model_spike.pkl was pickled with (else model_predict.py
#    silently falls back to the coarse bucket table). Version is read from the pickle itself.
NEED_SK=$(python3 -c "import re;m=re.search(rb'_sklearn_version.{0,20}?([0-9]+\.[0-9]+\.[0-9]+)',open('model_spike.pkl','rb').read());print(m.group(1).decode() if m else '')" 2>/dev/null || true)
HAVE_SK=$(python3 -c "import sklearn;print(sklearn.__version__)" 2>/dev/null || true)
if [ -n "$NEED_SK" ] && [ "$NEED_SK" != "$HAVE_SK" ]; then
  pip install -q --disable-pip-version-check "scikit-learn==$NEED_SK" 2>&1 | grep -v "as the 'root' user" || true
fi
python3 -c "import pickle;pickle.load(open('model_spike.pkl','rb'))" 2>/dev/null \
  && echo "[cloud-setup] spike GBM loads (sklearn ${NEED_SK})" \
  || echo "[cloud-setup] WARN: model_spike.pkl failed to load — model_predict will use bucket fallback"

# 4) Git: shallow clone → sync with origin/main before any work so the final push is a fast-forward.
git fetch --quiet origin main && git rebase --quiet --autostash origin/main && echo "[cloud-setup] synced to origin/main $(git rev-parse --short HEAD)"

# 5) Clock check (scripts assume Taipei local time).
echo "[cloud-setup] Taipei $(TZ=Asia/Taipei date '+%F %R')  |  New York $(TZ=America/New_York date '+%F %R')"
