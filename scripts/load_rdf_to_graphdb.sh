#!/usr/bin/env bash
# Load the integrated RDF file into GraphDB using the SERVER-SIDE IMPORT API.
#
# WHY server-side import (not REST POST)?
#   GraphDB's streaming REST POST (`POST /repositories/{id}/statements`) does NOT
#   trigger forward-chaining inference for rdfs:domain/range axioms on bulk loads.
#   The server-side import API uses GraphDB's internal import pipeline (same engine
#   as the Workbench UI) which properly materialises OWL-Max inference including
#   rdfs:domain → rdf:type at load time.
#
# Usage:
#   bash scripts/load_rdf_to_graphdb.sh [rdf_file]
#   Default rdf_file: data/rdf/formula1_integrated.nt
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load environment
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

RDF_FILE="${1:-data/rdf/formula1_integrated.nt}"
GRAPHDB_BASE_URL="${GRAPHDB_BASE_URL:-http://localhost:7200}"
GRAPHDB_REPOSITORY="${GRAPHDB_REPOSITORY:-ws-formula1-owlmax}"

if [[ ! -f "$RDF_FILE" ]]; then
  echo "ERROR: RDF file not found: $RDF_FILE" >&2
  echo "Run: python scripts/csv_to_rdf.py && python scripts/merge_integrated.py" >&2
  exit 1
fi

FILENAME="$(basename "$RDF_FILE")"
IMPORT_DIR="$HOME/graphdb-import"

echo "=== GraphDB Server-Side Import ==="
echo "Repository : $GRAPHDB_REPOSITORY"
echo "File       : $RDF_FILE ($FILENAME)"
echo "Import dir : $IMPORT_DIR"
echo ""

# 1. Put file in GraphDB's server import directory
mkdir -p "$IMPORT_DIR"
if [[ "$(realpath "$RDF_FILE")" != "$(realpath "$IMPORT_DIR/$FILENAME" 2>/dev/null || echo '')" ]]; then
  echo "Linking/copying file to import directory..."
  ln -sf "$(realpath "$RDF_FILE")" "$IMPORT_DIR/$FILENAME" 2>/dev/null || \
    cp "$RDF_FILE" "$IMPORT_DIR/$FILENAME"
fi

# 2. Clear the repository
echo "Clearing repository..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "${GRAPHDB_BASE_URL}/repositories/${GRAPHDB_REPOSITORY}/statements")
if [[ "$HTTP_CODE" != "204" ]]; then
  echo "ERROR: Failed to clear repository (HTTP $HTTP_CODE)" >&2
  exit 1
fi
echo "Repository cleared."

# 3. Trigger server-side import
echo "Triggering import..."
RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"fileNames\": [\"$FILENAME\"]}" \
  "${GRAPHDB_BASE_URL}/rest/repositories/${GRAPHDB_REPOSITORY}/import/server")
echo "Import started: $RESPONSE"

# 4. Poll until complete
echo "Waiting for import to complete..."
ELAPSED=0
while true; do
  sleep 5
  ELAPSED=$((ELAPSED + 5))
  STATUS=$(curl -s "${GRAPHDB_BASE_URL}/rest/repositories/${GRAPHDB_REPOSITORY}/import/server" | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['status'] if d else 'EMPTY')" 2>/dev/null || echo "UNKNOWN")
  echo "  ${ELAPSED}s: $STATUS"
  if [[ "$STATUS" == "DONE" ]]; then
    echo ""
    echo "Import complete."
    break
  elif [[ "$STATUS" == "ERROR" ]]; then
    echo "ERROR: Import failed" >&2
    exit 1
  fi
  if [[ $ELAPSED -gt 600 ]]; then
    echo "ERROR: Import timed out after 10 minutes" >&2
    exit 1
  fi
done

# 5. Quick verification
echo ""
echo "=== Verification ==="
python3 - <<'PY'
import os, sys
from dotenv import load_dotenv
load_dotenv('.env', override=True)
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ws_project.settings')
import django; django.setup()
from championship.services.graphdb import GraphDBClient
db = GraphDBClient()
checks = [
    ('f1:Driver (rdfs:domain)',  'SELECT (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d rdf:type f1:Driver }',       '861'),
    ('f1:Constructor',           'SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c rdf:type f1:Constructor }', '212'),
    ('f1:Circuit',               'SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c rdf:type f1:Circuit }',       '77'),
]
all_ok = True
for name, q, expected in checks:
    val = db.query(q)[0].get('n','?')
    ok = val == expected
    print(f"  [{'OK' if ok else 'FAIL'}] {name}: {val}")
    if not ok: all_ok = False
if all_ok:
    print("\nBase inference working. Now run: python manage.py run_spin_rules")
else:
    print("\nWARNING: Some checks failed. Verify GraphDB config.")
PY
