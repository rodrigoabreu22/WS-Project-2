# F1 Knowledge System

A semantic web application exposing the Formula 1 World Championship (1950–2024) as a queryable RDF knowledge graph with OWL 2 DL inference, SPIN rules, RDF reification, and live enrichment from Wikidata and DBpedia.

**Authors:** Rodrigo Abreu (113626), Hugo Ribeiro — Web Semantics, MEI 2025/2026  
**Project:** TP2 — continuation of TP1 (15/20)

---

## Architecture overview

```
Ergast CSV (data/raw/)
    │
    ▼  scripts/csv_to_rdf.py
formula1.nt  ← N-Triples facts (no rdf:type for Driver/Constructor/Circuit)
    │
    ▼  scripts/merge_integrated.py
formula1_integrated.nt  ← ontology + facts merged
    │
    ▼  GraphDB (OWL-Max + RDFS ruleset)
Triple store  ← base class inference via rdfs:domain at load time
    │
    ▼  python manage.py run_spin_rules
Enriched graph  ← WorldChampion, Veteran, PodiumResult, reification …
    │
    ▼  Django + SPARQL queries
Web application  ← RDFa 1.1 + Microformats 2 + Wikidata/DBpedia enrichment
```

No relational database is used for domain data. Django's SQLite is used only for authentication sessions.

---

## How to Run

### Prerequisites

- Python 3.12+
- [GraphDB Free](https://www.ontotext.com/products/graphdb/download/) running on `http://localhost:7200`
- A GraphDB repository named **`ws-formula1-owlmax`** created with the **`owl-max-optimized`** ruleset (see step 6 below — this is critical for `rdfs:domain` inference to work)
- Ergast CSV files in `data/raw/` (download from [ergast.com](https://ergast.com/mrd/db/))
- A Google Gemini API key (only needed for the F1 Assistant page)

> **Why `owl-max-optimized`?** GraphDB's `rdfsplus-optimized` ruleset does not materialise `rdfs:domain` inference during bulk REST API loads. The `owl-max-optimized` ruleset + server-side import (used by this project's load script) is the only configuration that correctly triggers `rdfs:domain → rdf:type` forward-chaining, enabling the ontology to classify Driver/Constructor/Circuit entities without explicit `rdf:type` in the facts file.

### Quick start (single command)

```bash
# Clone the repo, ensure GraphDB is running and data/raw/ has Ergast CSVs, then:
bash scripts/setup.sh
```

`setup.sh` handles everything: creates the virtual environment, installs dependencies,
creates the GraphDB repository, generates RDF files, loads data, runs all inference
rules, and sets up Django. You only need to start the server after:

```bash
source venv/bin/activate && python manage.py runserver
```

### Manual step-by-step

If you prefer to run each step individually:

```bash
# 1. Virtual environment and dependencies
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# The defaults in .env.example work as-is. Add GEMINI_KEY for the F1 Assistant.

# 3. Create GraphDB repository (owl-max-optimized ruleset — required)
#    GraphDB must be running at http://localhost:7200 first.
bash scripts/create_graphdb_repo.sh

# 4. Generate RDF facts from CSV (Ergast files must be in data/raw/)
python scripts/csv_to_rdf.py          # → data/rdf/formula1.nt (~798 MB)

# 5. Merge ontology + facts
python scripts/merge_integrated.py    # → data/rdf/formula1_integrated.nt

# 6. Load into GraphDB (server-side import, ~2 min)
bash scripts/load_rdf_to_graphdb.sh

# 7. Run SPIN inference rules (15 rules, ~1 min)
python manage.py run_spin_rules        # expected: 15/15 rules applied successfully

# 8. Django setup
python manage.py migrate
python manage.py createsuperuser       # for admin panel access

# 9. Start the server
python manage.py runserver
```

Open `http://localhost:8000`. Admin panel: `http://localhost:8000/admin-panel/login/`

### Re-running inference after data changes

```bash
python manage.py run_spin_rules   # all 15 rules are idempotent
```

### Why `owl-max-optimized` + server-side import?

GraphDB's `rdfsplus-optimized` ruleset and the streaming REST API
(`POST /repositories/{id}/statements`) do **not** trigger forward-chaining
`rdfs:domain → rdf:type` inference during bulk loads. The combination of:

- **`owl-max-optimized` ruleset** — enables full OWL-Max inference including
  `rdfs:domain`, `owl:inverseOf`, `owl:SymmetricProperty`
- **Server-side import** (`load_rdf_to_graphdb.sh`) — uses GraphDB's internal import
  pipeline (same as the Workbench UI) which correctly fires inference during ingestion

This is what allows the ontology to classify Driver/Constructor/Circuit entities
from their property usage (`f1:driverRef`, `f1:constructorRef`, `f1:circuitRef`)
without any explicit `rdf:type` in the facts file — exactly as the TP2 assignment requires.

### Why all 15 SPIN rules are still needed

The `owl-max-optimized` ruleset handles *ontological* inference (property → type via
`rdfs:domain`, inverse properties, subClassOf chains). The SPIN rules handle
*data-driven* inference that OWL DL fundamentally cannot express:

| Category | Examples |
|---|---|
| Aggregation | `COUNT(results) ≥ 100` (Veteran), `COUNT(championships) ≥ 2` (MultichampionDriver) |
| `GROUP BY + MAX` | Final round detection for championship rules |
| Arithmetic on data | `positionOrder = 1` (wonRace), `positionOrder ≤ 3` (PodiumResult) |
| Complex joins | Same race + same constructor + different driver (wasTeammate) |
| Negation-as-failure | `FILTER NOT EXISTS` for HistoricCircuit |
| RDF reification | `rdf:Statement` nodes with `f1:finalPoints` annotation |

None of these overlap with what OWL-Max provides.

---

## Pages

| URL | Page | Notes |
|-----|------|-------|
| `/` | Home | Live stats from GraphDB |
| `/drivers/` | All Drivers | Filter by name, nationality, medals; card + table view |
| `/drivers/<id>/` | Driver Detail | Career stats, constructor timeline, teammates, async Wikidata enrichment |
| `/champions/` | World Champions | Inferred via `f1:WorldChampion` SPIN rule |
| `/champions/multi/` | Multi-Champions | Inferred via `f1:MultichampionDriver` (≥2 titles) |
| `/champions/veterans/` | Veterans | Inferred via `f1:Veteran` (≥100 race entries) |
| `/constructors/` | All Constructors | Filter + card view |
| `/constructors/<id>/` | Constructor Detail | Pilots, circuits, async Wikidata (logo, founder, website) |
| `/constructors/champions/` | Constructor Champions | Inferred via `f1:ConstructorChampion` |
| `/circuits/` | All Circuits | Filter + card view |
| `/circuits/<id>/` | Circuit Detail | Race history, fastest laps, async DBpedia (turns, capacity, lap record) |
| `/races/` | All Races | Filter by season and search |
| `/races/<id>/` | Race Detail | Podium, full results with driver + constructor links |
| `/seasons/` | All Seasons | Card/table toggle, sortable |
| `/seasons/<year>/` | Season Detail | Calendar, driver + constructor standings, deep links |
| `/tools/` | Semantic Tools | Live reification viewer, Microformats 2 parser, RDFa Play links |
| `/assistant/` | F1 Assistant | Natural-language Q&A over the knowledge graph (Gemini) |
| `/admin-panel/` | Admin Panel | CRUD for all entities, CSV import, run inference |

---

## Semantic web features

### Ontology (`data/rdf/formula1_ontology.ttl`)

OWL 2 DL ontology with 18 classes and 15+ properties. **This file is hand-authored and tracked in git** — it is the source of truth for the semantic layer.

**Key constructs:**

- `owl:equivalentClass` + `owl:someValuesFrom` — bidirectional class inference for Driver/Constructor/Circuit from their `*Ref` properties
- `rdfs:domain` on `f1:driverRef / constructorRef / circuitRef` — GraphDB infers `rdf:type` at load time; **the facts file contains no explicit `rdf:type`** for these base classes
- `owl:SymmetricProperty` on `f1:wasTeammate`
- `owl:inverseOf` on `f1:hadDriver ↔ f1:drovFor`
- `rdfs:subPropertyOf`: `wonRace ⊑ competedIn`, `achievedPodium ⊑ competedIn`
- `owl:disjointWith`: Driver↔Constructor, Driver↔Circuit, Race↔Season, Result↔QualifyingResult

### SPIN rules (`championship/spin_rules.py`)

15 SPARQL `INSERT WHERE` rules that express patterns OWL DL cannot (aggregation, arithmetic, negation-as-failure):

| Rule | What it infers |
|------|---------------|
| `infer_wonRace` | `f1:wonRace` triples (positionOrder = 1) |
| `infer_achievedPodium` | `f1:achievedPodium` triples (positionOrder ≤ 3) |
| `infer_drovFor` | `f1:drovFor` (driver → constructor, cross-table join) |
| `infer_wasTeammate` | `f1:wasTeammate` (same race, same constructor, different driver) |
| `infer_wonChampionship` | `f1:wonChampionship` (position 1 at MAX round per season) |
| `reify_wonChampionship` | 75 `rdf:Statement` nodes with `f1:finalPoints` |
| `infer_heldAt` | `f1:heldAt` (materialised from `f1:circuit` on Race) |
| `classify_WorldChampion` | `rdf:type f1:WorldChampion` |
| `classify_MultichampionDriver` | `rdf:type f1:MultichampionDriver` (COUNT ≥ 2 titles) |
| `classify_Veteran` | `rdf:type f1:Veteran` (COUNT ≥ 100 race entries) |
| `classify_ActiveCircuit` | `rdf:type f1:ActiveCircuit` (last race = dataset max year) |
| `classify_HistoricCircuit` | `rdf:type f1:HistoricCircuit` (no race in last 10 years) |
| `classify_PodiumResult` | `rdf:type f1:PodiumResult` (positionOrder ≤ 3) |
| `infer_wonConstructorChampionship` | `f1:wonConstructorChampionship` |
| `classify_ConstructorChampion` | `rdf:type f1:ConstructorChampion` |

### RDF Reification

`reify_wonChampionship` creates 75 `rdf:Statement` nodes — one per F1 season — annotating each `driver wonChampionship season` triple with `f1:finalPoints` (the driver's final championship points). Visible on `/tools/`.

### RDFa 1.1 Lite + Microformats 2

All detail pages embed both standards simultaneously:

- **RDFa 1.1 Lite** (Schema.org): `vocab`, `typeof`, `property`, `resource` — consumed by Google's Knowledge Graph and the W3C pyRDFa distiller
- **Microformats 2**: `h-card`, `h-event`, `h-adr`, `p-name`, `dt-bday`, `u-url` — parsed by IndieWeb tools

Parse Microformats from any page: `GET /api/parse-microformats/?url=<url>` (returns JSON).  
Validate RDFa: use the W3C distiller links on `/tools/`, or paste HTML into [rdfa.info/play](https://rdfa.info/play/).

### External enrichment (Wikidata + DBpedia)

All enrichment is loaded **asynchronously** after page render — the page loads instantly and enrichment is injected once the `fetch()` resolves.

| Entity | Source | Data fetched |
|--------|--------|-------------|
| Driver | Wikidata | Death date (†), height, birth place, family links (F1 dynasties) |
| Constructor | Wikidata | Logo (P154), website (P856), country (P17), founder (P112), dissolved (P576) |
| Circuit | DBpedia | Turns, spectator capacity, year opened, lap record |
| All | Wikipedia REST | Description text, thumbnail image |

DBpedia circuits are queried via direct resource URI (`dbr:Circuit_de_Monaco`) rather than label-matching, since F1 circuits in DBpedia are not typed as `dbo:RaceTrack`.

---

## Namespaces

| Prefix | IRI |
|--------|-----|
| `f1:` | `http://example.org/f1/` |
| `res:` | `http://example.org/resource/` |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` |
| `owl:` | `http://www.w3.org/2002/07/owl#` |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` |

Entity URI patterns: `res:driver/{id}`, `res:constructor/{id}`, `res:circuit/{id}`, `res:race/{id}`, `res:season/{year}`, `res:result/{id}`

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Web framework | Django 6.0 |
| Triple store | GraphDB Free (OWL-Max + RDFS ruleset) |
| SPARQL client | SPARQLWrapper 2.0 |
| RDF library | rdflib 7.6 |
| MF2 parser | mf2py 2.0 |
| HTTP client | requests 2.32 |
| NLU assistant | Google Gemini API |
| Front-end | Vanilla HTML/CSS (dark + light theme, Barlow Condensed) |

---

## Project structure

```
data/
  raw/                          — Ergast CSV files (not in git)
  rdf/
    formula1_ontology.ttl       — OWL 2 DL ontology (hand-authored, in git)
    formula1.nt                 — Generated facts (gitignored, ~798 MB)
    formula1_integrated.nt      — Merged ontology + facts (gitignored)

scripts/
  csv_to_rdf.py                 — CSV → N-Triples (suppresses rdf:type for base classes)
  merge_integrated.py           — Merges ontology + facts for GraphDB load
  load_rdf_to_graphdb.sh        — Optional: loads via GraphDB REST API

championship/
  spin_rules.py                 — 15 SPARQL inference rules
  views.py                      — All Django views + /api/entity-info/ endpoint
  services/
    graphdb.py                  — GraphDBClient (query + run_update)
    external_data.py            — Wikidata / DBpedia / Wikipedia enrichment
  management/commands/
    run_spin_rules.py           — `python manage.py run_spin_rules`

templates/championship/
  base.html                     — Nav, theme toggle, card hover, wiki-img-slot JS
  driver_detail.html            — h-card + RDFa; async Wikidata enrichment
  constructor_detail.html       — h-card + RDFa; async Wikidata enrichment
  circuit_detail.html           — h-adr + RDFa; async DBpedia enrichment
  race_detail.html              — h-event + RDFa
  season_detail.html            — h-event + RDFa
  champions.html                — SPIN-inferred WorldChampion
  multichampions.html           — SPIN-inferred MultichampionDriver
  veterans.html                 — SPIN-inferred Veteran
  constructor_champions.html    — SPIN-inferred ConstructorChampion
  semantic_tools.html           — Reification viewer, MF2 parser, RDFa links

docs/
  tp2_documentation.md          — Full project documentation for the report
  ontology_diagram.md           — Mermaid class diagram of the ontology
  ONTOLOGY_INFERENCE.md         — Inference verification (15/15 checks with real counts)
```
