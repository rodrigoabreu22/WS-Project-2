#!/usr/bin/env bash
# =============================================================================
# F1 Knowledge System — Full Setup Script
# =============================================================================
# Run this once on a fresh clone to go from zero to a working application.
#
# Prerequisites (must be installed and running before you start):
#   1. Python 3.12+
#   2. GraphDB Desktop  — https://www.ontotext.com/products/graphdb/download/
#      Start it and leave it running at http://localhost:7200
#   3. Kaggle Formula 1 CSV files — place the Ergast-style CSVs in data/raw/
#
# Usage:
#   bash scripts/setup.sh
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # always run from project root

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
info() { echo -e "${YELLOW}[--]${NC}  $*"; }
fail() { echo -e "${RED}[!!]${NC}  $*" >&2; exit 1; }

echo "============================================================"
echo "  F1 Knowledge System — Setup"
echo "============================================================"
echo ""

# ── Step 0: Verify prerequisites ─────────────────────────────────────────────
info "Checking prerequisites..."

python3 --version >/dev/null 2>&1 || fail "Python 3 not found."

if ! curl -sf "http://localhost:7200/rest/info/version" >/dev/null 2>&1; then
  fail "GraphDB is not running at http://localhost:7200. Start GraphDB Desktop and try again."
fi
ok "GraphDB is running."

if [[ ! -f "data/raw/races.csv" ]]; then
  fail "Formula 1 CSV files not found in data/raw/. Add the Kaggle/Ergast-style CSVs there."
fi
ok "Formula 1 CSV files found."

echo ""

# ── Step 1: Python virtual environment ───────────────────────────────────────
info "Setting up Python virtual environment..."
if [[ ! -d "venv" ]]; then
  python3 -m venv venv
  ok "Virtual environment created."
else
  ok "Virtual environment already exists."
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Dependencies installed."

echo ""

# ── Step 2: Environment file ──────────────────────────────────────────────────
info "Configuring environment..."
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    info ".env created from .env.example — edit it to add your GEMINI_KEY if needed."
  else
    cat > .env <<'ENV'
DJANGO_SECRET_KEY=replace-this-with-a-long-random-string
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
GRAPHDB_BASE_URL=http://localhost:7200
GRAPHDB_REPOSITORY=ws-formula1-owlmax
GRAPHDB_USERNAME=
GRAPHDB_PASSWORD=
GRAPHDB_GRAPH_URI=
GEMINI_KEY=
ENV
    info ".env created with defaults — add your GEMINI_KEY for the F1 Assistant."
  fi
else
  ok ".env already exists."
fi
# Load env for subsequent steps
set -a; source .env; set +a

echo ""

# ── Step 3: Create GraphDB repository ────────────────────────────────────────
info "Creating GraphDB repository '${GRAPHDB_REPOSITORY}'..."
bash scripts/create_graphdb_repo.sh
echo ""

# ── Step 4: Generate RDF facts ────────────────────────────────────────────────
info "Converting CSV → RDF N-Triples..."
if [[ -f "data/rdf/formula1.nt" ]]; then
  ok "data/rdf/formula1.nt already exists — skipping (delete it to regenerate)."
else
  python scripts/csv_to_rdf.py
  ok "data/rdf/formula1.nt generated."
fi

echo ""

# ── Step 5: Merge ontology + facts ───────────────────────────────────────────
# The integrated file must always be regenerated when the ontology changes.
# Comparison is done by modification timestamp: if the ontology TTL is newer
# than the integrated NT, the merge runs unconditionally.
info "Merging ontology + facts into integrated file..."
ONTO_TIME=$(stat -c '%Y' data/rdf/formula1_ontology.ttl 2>/dev/null || echo 0)
INTG_TIME=$(stat -c '%Y' data/rdf/formula1_integrated.nt 2>/dev/null || echo 0)
if [[ -f "data/rdf/formula1_integrated.nt" && "$INTG_TIME" -ge "$ONTO_TIME" ]]; then
  ok "data/rdf/formula1_integrated.nt is up to date."
  info "(To force regeneration after an ontology change: rm data/rdf/formula1_integrated.nt)"
else
  python scripts/merge_integrated.py
  ok "data/rdf/formula1_integrated.nt generated (389 ontology triples + 6.6M fact triples)."
fi

echo ""

# ── Step 6: Load data into GraphDB ───────────────────────────────────────────
info "Loading data into GraphDB (server-side import, ~2 min)..."
bash scripts/load_rdf_to_graphdb.sh
echo ""

# ── Step 7: Run SPIN inference rules ─────────────────────────────────────────
# 21 rules in order: race facts → championships → classifications.
# infer_wasTeammate is the slowest (~45 s). Total: ~50 s on first run.
info "Running 21 SPIN inference rules (~1 min)..."
python manage.py run_spin_rules
echo ""

# ── Step 8: Django setup ──────────────────────────────────────────────────────
info "Setting up Django (SQLite for authentication only)..."
python manage.py migrate --run-syncdb 2>/dev/null || python manage.py migrate
ok "Database migrated."

if ! python manage.py shell -c "from django.contrib.auth.models import User; exit(0 if User.objects.filter(is_staff=True).exists() else 1)" 2>/dev/null; then
  info "No staff user found. Creating superuser for the admin panel..."
  python manage.py createsuperuser
fi

echo ""
echo "============================================================"
echo "  Setup complete!"
echo ""
echo "  Start the server:"
echo "    bash scripts/run_webserver.sh"
echo ""
echo "  Application : http://localhost:9000"
echo "  Admin panel : http://localhost:9000/admin-panel/login/"
echo ""
echo "  To reload GraphDB after an ontology change:"
echo "    rm data/rdf/formula1_integrated.nt"
echo "    bash scripts/setup.sh        (re-runs from step 5)"
echo "  OR for a full reload from scratch:"
echo "    rm data/rdf/formula1.nt data/rdf/formula1_integrated.nt"
echo "    bash scripts/setup.sh"
echo "============================================================"
