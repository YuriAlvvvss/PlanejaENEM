#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ -x "$PWD/venv/bin/python" ]; then
  PYTHON_BIN="$PWD/venv/bin/python"
elif [ -x "$PWD/.venv/bin/python" ]; then
  PYTHON_BIN="$PWD/.venv/bin/python"
else
  echo "[INFO] Virtual environment not found. Creating one..."
  python3 -m venv venv
  PYTHON_BIN="$PWD/venv/bin/python"
fi

if [ ! -f "$PWD/requirements.txt" ]; then
  echo "[ERROR] requirements.txt not found in project root."
  exit 1
fi

"$PYTHON_BIN" -m pip install --quiet -r "$PWD/requirements.txt"

export FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_DEBUG="${FLASK_DEBUG:-1}"
export PORT="${PORT:-5000}"
URL="http://localhost:${PORT}"

echo "[INFO] Starting PlanejaENEM on ${URL}"
nohup "$PYTHON_BIN" -c 'import os; from app import create_app; app = create_app(); app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}, use_reloader=False)' >/tmp/planejaenem.log 2>&1 &

sleep 2

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"
elif command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v wslview >/dev/null 2>&1; then
  wslview "$URL"
else
  echo "[INFO] Abra o navegador em: ${URL}"
fi
