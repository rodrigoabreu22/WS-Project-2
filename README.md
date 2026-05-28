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
- A GraphDB repository named **`ws-formula1`** (create via the Workbench UI)
- Ergast CSV files in `data/raw/` (download from [ergast.com](https://ergast.com/mrd/db/))
- A Google Gemini API key (only needed for the F1 Assistant page)

### Steps

```bash
# 1. Clone and create virtual environment
git clone <repo-url> && cd WS-Project-2
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set at minimum:
#   DJANGO_SECRET_KEY=<any-long-random-string>
#   GRAPHDB_BASE_URL=http://localhost:7200
#   GRAPHDB_REPOSITORY=ws-formula1
#   GEMINI_KEY=<your-gemini-api-key>   (optional, for F1 Assistant only)

# 4. Generate RDF facts from CSV
python scripts/csv_to_rdf.py
# Output: data/rdf/formula1.nt  (~798 MB, gitignored)

# 5. Merge ontology + facts into one file
python scripts/merge_integrated.py
# Output: data/rdf/formula1_integrated.nt  (~798 MB, gitignored)

# 6. Load into GraphDB
#    Open http://localhost:7200 → ws-formula1 repository
#    Import → Server files → select data/rdf/formula1_integrated.nt
#    (or: bash scripts/load_rdf_to_graphdb.sh)

# 7. Run SPIN inference rules (15 rules, ~1 min)
python manage.py run_spin_rules
# Materialises WorldChampion, Veteran, HistoricCircuit, PodiumResult,
# wasTeammate, wonChampionship, reification nodes, and more.

# 8. Set up Django (SQLite — auth only)
python manage.py migrate
python manage.py createsuperuser   # needed for the admin panel

# 9. Start the dev server
python manage.py runserver
```

Open `http://localhost:8000`.  
Admin panel: `http://localhost:8000/admin-panel/login/`

### Re-running inference

If you change the SPIN rules or reload GraphDB data:

```bash
python manage.py run_spin_rules
```

All 15 rules are idempotent — safe to run multiple times.

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
