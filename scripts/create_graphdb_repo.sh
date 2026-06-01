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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

GRAPHDB_BASE_URL="${GRAPHDB_BASE_URL:-http://localhost:7200}"
GRAPHDB_REPOSITORY="${GRAPHDB_REPOSITORY:-ws-formula1-owlmax}"
GRAPHDB_BASE_URL="${GRAPHDB_BASE_URL%/}"

CURL_OPTS=(-sS)
if [[ -n "${GRAPHDB_USERNAME:-}" ]]; then
  CURL_OPTS+=(-u "${GRAPHDB_USERNAME}:${GRAPHDB_PASSWORD:-}")
fi

fail() {
  echo "[!!]  $*" >&2
  exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl not found."
command -v python3 >/dev/null 2>&1 || fail "python3 not found."

if ! [[ "$GRAPHDB_REPOSITORY" =~ ^[A-Za-z0-9._-]+$ ]]; then
  fail "Invalid GRAPHDB_REPOSITORY '$GRAPHDB_REPOSITORY'. Use only letters, numbers, dot, underscore and hyphen."
fi

if ! curl "${CURL_OPTS[@]}" -fsS "${GRAPHDB_BASE_URL}/rest/info/version" >/dev/null; then
  fail "GraphDB is not reachable at ${GRAPHDB_BASE_URL}. Start GraphDB and try again."
fi

# Check if repo already exists via the REST management endpoint
REPOS_JSON=$(curl "${CURL_OPTS[@]}" -fsS \
  -H "Accept: application/json" \
  "${GRAPHDB_BASE_URL}/rest/repositories") || fail "Could not list GraphDB repositories."

EXISTING=$(GRAPHDB_REPOSITORY="$GRAPHDB_REPOSITORY" python3 -c '
import json
import os
import sys

repos = json.load(sys.stdin)
target = os.environ["GRAPHDB_REPOSITORY"]
print("yes" if any(repo.get("id") == target for repo in repos) else "no")
' <<<"$REPOS_JSON") || fail "GraphDB returned an invalid repositories JSON response."

if [[ "$EXISTING" == "yes" ]]; then
  echo "[OK]  Repository '${GRAPHDB_REPOSITORY}' already exists — skipping creation."
  exit 0
fi

echo "[--]  Creating repository '${GRAPHDB_REPOSITORY}' with owl-max-optimized ruleset..."

CONFIG_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$CONFIG_FILE" "$RESPONSE_FILE"' EXIT

# GraphDB creates repositories from an RDF4J Turtle repository config sent as
# multipart/form-data. JSON is accepted for editing an existing repository, not
# for creating a new one.
cat > "$CONFIG_FILE" <<TTL
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
@prefix rep: <http://www.openrdf.org/config/repository#>.
@prefix sr: <http://www.openrdf.org/config/repository/sail#>.
@prefix sail: <http://www.openrdf.org/config/sail#>.
@prefix graphdb: <http://www.ontotext.com/config/graphdb#>.

[] a rep:Repository ;
    rep:repositoryID "${GRAPHDB_REPOSITORY}" ;
    rdfs:label "F1 Knowledge System (TP2)" ;
    rep:repositoryImpl [
        rep:repositoryType "graphdb:SailRepository" ;
        sr:sailImpl [
            sail:sailType "graphdb:Sail" ;

            graphdb:read-only "false" ;

            graphdb:ruleset "owl-max-optimized" ;
            graphdb:disable-sameAs "false" ;
            graphdb:check-for-inconsistencies "false" ;

            graphdb:entity-id-size "32" ;
            graphdb:enable-context-index "false" ;
            graphdb:enablePredicateList "true" ;
            graphdb:enable-fts-index "false" ;
            graphdb:fts-indexes ("default" "iri") ;
            graphdb:fts-string-literals-index "default" ;
            graphdb:fts-iris-index "none" ;

            graphdb:query-timeout "0" ;
            graphdb:throw-QueryEvaluationException-on-timeout "false" ;
            graphdb:query-limit-results "0" ;

            graphdb:base-URL "http://example.org/owlim#" ;
            graphdb:defaultNS "" ;
            graphdb:imports "" ;
            graphdb:repository-type "file-repository" ;
            graphdb:storage-folder "storage" ;
            graphdb:entity-index-size "10000000" ;
            graphdb:in-memory-literal-properties "true" ;
            graphdb:enable-literal-index "true" ;
        ]
    ].
TTL

HTTP_CODE=$(curl "${CURL_OPTS[@]}" -o "$RESPONSE_FILE" -w "%{http_code}" \
  -X POST \
  -H "Accept: application/json" \
  -F "config=@${CONFIG_FILE};type=text/turtle" \
  "${GRAPHDB_BASE_URL}/rest/repositories")

if [[ "$HTTP_CODE" == "201" || "$HTTP_CODE" == "200" ]]; then
  echo "[OK]  Repository '${GRAPHDB_REPOSITORY}' created successfully."
else
  echo "[!!]  Failed to create repository (HTTP $HTTP_CODE):" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi
