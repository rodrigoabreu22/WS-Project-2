#!/usr/bin/env bash
# Create the GraphDB repository with the owl-max-optimized ruleset.
#
# This ruleset is REQUIRED: it enables forward-chaining rdfs:domain inference
# at load time, which is what classifies Driver/Constructor/Circuit entities
# from their property usage without explicit rdf:type assertions in the facts.
#
# Usage: bash scripts/create_graphdb_repo.sh
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ -f .env ]]; then set -a; source .env; set +a; fi

GRAPHDB_BASE_URL="${GRAPHDB_BASE_URL:-http://localhost:7200}"
GRAPHDB_REPOSITORY="${GRAPHDB_REPOSITORY:-ws-formula1-owlmax}"

# Check if repo already exists via the REST management endpoint
EXISTING=$(curl -s "${GRAPHDB_BASE_URL}/rest/repositories" | \
  python3 -c "import json,sys; repos=json.load(sys.stdin); print('yes' if any(r['id']=='${GRAPHDB_REPOSITORY}' for r in repos) else 'no')" 2>/dev/null || echo "no")

if [[ "$EXISTING" == "yes" ]]; then
  echo "[OK]  Repository '${GRAPHDB_REPOSITORY}' already exists — skipping creation."
  exit 0
fi

echo "[--]  Creating repository '${GRAPHDB_REPOSITORY}' with owl-max-optimized ruleset..."

# Build the repository config payload
CONFIG=$(python3 -c "
import json
config = {
  'id': '${GRAPHDB_REPOSITORY}',
  'title': 'F1 Knowledge System (TP2)',
  'type': 'graphdb',
  'sesameType': 'graphdb:SailRepository',
  'location': '',
  'params': {
    'ruleset':               {'name': 'ruleset',               'value': 'owl-max-optimized'},
    'disableSameAs':         {'name': 'disableSameAs',         'value': 'false'},
    'rdfsSubClassReasoning': {'name': 'rdfsSubClassReasoning', 'value': 'true'},
    'entityIndexSize':       {'name': 'entityIndexSize',       'value': '10000000'},
    'entityIdSize':          {'name': 'entityIdSize',          'value': '32'},
    'inMemoryLiteralProperties': {'name': 'inMemoryLiteralProperties', 'value': 'true'},
    'enablePredicateList':   {'name': 'enablePredicateList',   'value': 'true'},
    'storageFolder':         {'name': 'storageFolder',         'value': 'storage'},
    'repositoryType':        {'name': 'repositoryType',        'value': 'file-repository'},
    'cacheSelectNodes':      {'name': 'cacheSelectNodes',      'value': 'true'},
    'queryTimeout':          {'name': 'queryTimeout',          'value': '0'},
    'queryLimitResults':     {'name': 'queryLimitResults',     'value': '0'},
    'baseURL':               {'name': 'baseURL',               'value': 'http://example.org/owlim#'},
  }
}
print(json.dumps(config))
")

HTTP_CODE=$(curl -s -o /tmp/create_repo_response.txt -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d "$CONFIG" \
  "${GRAPHDB_BASE_URL}/rest/repositories")

if [[ "$HTTP_CODE" == "201" ]]; then
  echo "[OK]  Repository '${GRAPHDB_REPOSITORY}' created successfully."
else
  echo "[!!]  Failed to create repository (HTTP $HTTP_CODE):" >&2
  cat /tmp/create_repo_response.txt >&2
  exit 1
fi
