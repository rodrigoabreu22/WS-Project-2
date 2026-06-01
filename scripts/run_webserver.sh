#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load environment variables
if [[ -f .env ]]; then set -a; source .env; set +a; fi

# Activate whichever virtual environment exists
if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python manage.py migrate --run-syncdb 2>/dev/null || python manage.py migrate
python manage.py runserver "${1:-127.0.0.1:9000}"
