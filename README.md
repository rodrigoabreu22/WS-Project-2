# F1 Knowledge System

A semantic web application exposing the Formula 1 World Championship (1950–2024) as a queryable RDF knowledge graph with OWL 2 DL inference, 21 SPIN materialisation rules, RDF reification, and live enrichment from Wikidata and DBpedia.

**Authors:** Rodrigo Abreu (113626), Hugo Ribeiro (113402) — Web Semantics, MEI 2025/2026  
**Project:** TP2 — continuation of TP1

---

## Quick Start

Ensure GraphDB is running at `http://localhost:7200` and the dataset CSV files are in `data/raw/` (see [Dataset](#dataset) below), then:

```bash
bash scripts/setup.sh
bash scripts/run_webserver.sh
```

Open **`http://localhost:9000`**. Admin panel: `http://localhost:9000/admin-panel/login/`

| | |
|---|---|
| **Username** | `admin` |
| **Password** | `admin` |

`setup.sh` handles everything: virtual environment, dependencies, GraphDB repository creation, RDF generation, load, and SPIN inference. It skips steps that are already complete and can be re-run safely.

---

## Manual Setup

```bash
# 1. Virtual environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Environment configuration
cp .env.example .env
# Defaults work as-is. Add GEMINI_KEY for the F1 Assistant page.

# 3. Create GraphDB repository (owl-max-optimized ruleset — required)
bash scripts/create_graphdb_repo.sh

# 4. Generate RDF facts from CSV
# Requires Kaggle dataset CSVs in data/raw/ — see README ## Dataset
python3 scripts/csv_to_rdf.py            # → data/rdf/formula1.nt (~798 MB)

# 5. Merge ontology + facts
python3 scripts/merge_integrated.py      # → data/rdf/formula1_integrated.nt

# 6. Load into GraphDB (~2 min, server-side import)
bash scripts/load_rdf_to_graphdb.sh

# 7. Run 21 SPIN inference rules (~1 min)
python3 manage.py run_spin_rules         # expected: 21/21 rules applied successfully

# 8. Django setup
python3 manage.py migrate
python3 manage.py createsuperuser

# 9. Start the server
bash scripts/run_webserver.sh
```

### Re-running after an ontology change

If `formula1_ontology.ttl` is modified, delete the integrated file and reload:

```bash
rm data/rdf/formula1_integrated.nt
bash scripts/setup.sh   # re-runs from step 5, skips earlier steps
```

All 21 SPIN rules are idempotent and can be re-run at any time:

```bash
python manage.py run_spin_rules
```

---

## Dataset

The application uses the **Formula 1 World Championship (1950–2024)** dataset by Rohan Rao, available on Kaggle:

**Download:** <https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020>

After downloading, extract the CSV files and place them in `data/raw/`:

```
data/raw/
  circuits.csv
  constructor_results.csv
  constructors.csv
  constructor_standings.csv
  drivers.csv
  lap_times.csv
  pit_stops.csv
  qualifying.csv
  races.csv
  results.csv
  seasons.csv
  sprint_results.csv
  status.csv
```

The dataset follows the [Ergast API](http://ergast.com/mrd/) schema and is updated after each season. Once the files are in place, `scripts/csv_to_rdf.py` converts them to N-Triples (`data/rdf/formula1.nt`, ~798 MB).

---

## Why `owl-max-optimized` + server-side import?

GraphDB's `rdfsplus-optimized` ruleset does **not** materialise `rdfs:domain → rdf:type`
inference during bulk REST POST loads. Only the combination of:

- **`owl-max-optimized` ruleset** — fires `rdfs:domain`, `owl:inverseOf`, `owl:SymmetricProperty`
- **Server-side import** — uses GraphDB's internal import pipeline (same as Workbench UI)

…correctly classifies Driver/Constructor/Circuit entities purely from their property
usage (`f1:driverRef`, `f1:constructorRef`, `f1:circuitRef`) with no explicit
`rdf:type` in the facts file.

---

## Why 21 SPIN rules on top of OWL?

The `owl-max-optimized` ruleset handles *structural* inference (property → type, inverse properties, subclass chains). SPIN handles *data-driven* patterns that OWL 2 DL cannot express:

| Pattern | Examples |
|---|---|
| Aggregation | `COUNT(results) ≥ 100` (Veteran), `COUNT(titles) ≥ 2` (MultichampionDriver) |
| `GROUP BY + MAX` | Final-round detection for championship rules |
| Arithmetic | `positionOrder = 1` (wonRace), `positionOrder ≤ 3` (achievedPodium) |
| Layered inference | `convertedP1ToWin` requires both `startedFromP1` and `wonRace` to already exist |
| Three-way join | `wonRace ∧ startedFromP1 ∧ setFastestLap` → `achievedHatTrick` |
| Complex join | Same race + same constructor + different driver → `wasTeammate` |
| Negation-as-failure | `FILTER NOT EXISTS` for HistoricCircuit |
| RDF reification | `rdf:Statement` nodes with `f1:finalPoints` annotation |

---

## Pages

| URL | Page | Semantic source |
|-----|------|----------------|
| `/` | Home | Live counts from graph |
| `/drivers/` | All Drivers | Wins via `f1:wonRace` SPIN · podiums via `f1:finishedSecond`/`f1:finishedThird` SPIN |
| `/drivers/<id>/` | Driver Detail | Full SPIN stats + OWL-Max types + Wikidata enrichment |
| `/constructors/` | All Constructors | Wins/podiums via SPIN |
| `/constructors/<id>/` | Constructor Detail | `f1:hadDriver` (OWL inverseOf) + Wikidata enrichment |
| `/circuits/` | All Circuits | Active/Historic status via SPIN classification |
| `/circuits/<id>/` | Circuit Detail | `f1:heldAt` (SPIN) + DBpedia enrichment |
| `/races/` | All Races | — |
| `/races/<id>/` | Race Detail | Podium via `f1:wonRace`/`f1:finishedSecond`/`f1:finishedThird` SPIN · DBpedia weather/attendance |
| `/seasons/` | All Seasons | — |
| `/seasons/<year>/` | Season Detail | Wikipedia enrichment |
| `/hall-of-fame/` | Hall of Fame dashboard | All SPIN-inferred classes (record holders live from graph) |
| `/champions/` | World Champions | `rdf:type f1:WorldChampion` SPIN |
| `/champions/multi/` | Multi-Champions | `rdf:type f1:MultichampionDriver` SPIN |
| `/champions/veterans/` | Veterans | `rdf:type f1:Veteran` SPIN (≥100 race entries) |
| `/constructors/champions/` | Constructor Champions | `rdf:type f1:ConstructorChampion` SPIN |
| `/p1/` | Pole Position Leaders | `f1:startedFromP1` + `f1:convertedP1ToWin` SPIN |
| `/hat-tricks/` | Hat Trick Hall of Fame | `f1:achievedHatTrick` SPIN (69 perfect races) |
| `/assistant/` | F1 Assistant | Natural-language Q&A (Gemini API) |
| `/admin-panel/` | Admin Panel | CRUD, CSV import, run inference |

---

## Semantic Web Features

### Ontology (`data/rdf/formula1_ontology.ttl`)

OWL 2 DL ontology — **hand-authored, tracked in git**. 27 classes total (20 asserted + 7 SPIN-inferred), 21 object properties, 35 datatype properties.

Key constructs:
- `rdfs:domain` on `f1:driverRef / constructorRef / circuitRef` — GraphDB infers `rdf:type` at load time; the facts file contains **no explicit `rdf:type`** for base classes
- `owl:equivalentClass` + `owl:someValuesFrom` — for Protégé/HermiT bidirectional class inference
- `owl:SymmetricProperty` on `f1:wasTeammate`
- `owl:inverseOf`: `f1:hadDriver ↔ f1:drovFor`
- `rdfs:subPropertyOf`: `wonRace ⊑ achievedPodium ⊑ competedIn`, `finishedSecond ⊑ achievedPodium`, `finishedThird ⊑ achievedPodium`, `achievedHatTrick ⊑ wonRace`
- `owl:disjointWith`: 7 pairs (Driver↔Constructor, Driver↔Circuit, Race↔Season, …)
- Verified with HermiT 1.4.3 via owlready2: consistent, 0 unsatisfiable classes, ~1,333 ms

### SPIN Rules (`championship/spin_rules.py`)

21 SPARQL `INSERT WHERE` rules. Verified triple counts from live GraphDB:

| Rule | Output | Triples |
|------|--------|---------|
| `infer_wonRace` | `f1:wonRace` | 1,128 |
| `infer_finishedSecond` | `f1:finishedSecond` | 1,134 |
| `infer_finishedThird` | `f1:finishedThird` | 1,135 |
| `infer_achievedPodium` | `f1:achievedPodium` | 3,395 |
| `infer_startedFromP1` | `f1:startedFromP1` | 1,135 |
| `infer_convertedP1ToWin` | `f1:convertedP1ToWin` | 486 |
| `infer_setFastestLap` | `f1:setFastestLap` | 410 |
| `infer_achievedHatTrick` | `f1:achievedHatTrick` | 69 |
| `infer_wasTeammate` | `f1:wasTeammate` | 10,012 |
| `infer_wonChampionship` | `f1:wonChampionship` | 75 |
| `reify_wonChampionship` | `rdf:Statement` nodes | 75 |
| `infer_wonConstructorChampionship` | `f1:wonConstructorChampionship` | 17 |
| `classify_WorldChampion` | `rdf:type f1:WorldChampion` | 34 |
| `classify_MultichampionDriver` | `rdf:type f1:MultichampionDriver` | 17 |
| `classify_Veteran` | `rdf:type f1:Veteran` | 86 |
| `classify_ActiveCircuit` | `rdf:type f1:ActiveCircuit` | 24 |
| `classify_HistoricCircuit` | `rdf:type f1:HistoricCircuit` | 45 |
| `classify_PodiumResult` | `rdf:type f1:PodiumResult` | 3,397 |
| `classify_ConstructorChampion` | `rdf:type f1:ConstructorChampion` | 17 |
| `infer_drovFor` / `infer_heldAt` | `f1:drovFor`, `f1:heldAt` | 2,150 / 1,125 |

**Total SPIN-generated triples: 22,921** (on top of 6,627,434 fact triples).

### RDF Reification

`reify_wonChampionship` creates 75 `rdf:Statement` nodes — one per F1 season — annotating each `driver wonChampionship season` triple with `f1:finalPoints`. This is the canonical RDF pattern for attaching metadata to an existing triple.

### RDFa 1.1 Lite + Microformats 2

All detail pages embed both standards simultaneously on the same HTML elements:

| Page | RDFa `typeof` | MF2 root class |
|------|--------------|----------------|
| `/drivers/<id>/` | `schema:Person` | `h-card` |
| `/constructors/<id>/` | `schema:SportsOrganization` | `h-card` |
| `/circuits/<id>/` | `schema:SportsActivityLocation` | `h-card h-adr` |
| `/races/<id>/` | `schema:SportsEvent` | `h-event` |
| `/seasons/<year>/` | `schema:SportsEvent` | `h-event` |
| `/` | `schema:Dataset` | — |

**Validate Microformats 2 locally** (no external service needed — mf2py is a standalone Python parser):

```bash
# From project root, with server running:
curl -s "http://localhost:9000/api/parse-microformats/?url=http://localhost:9000/drivers/1/" | python3 -m json.tool
```

**Validate RDFa locally** (pyrdfa3 is in requirements.txt):

```bash
pip install pyrdfa3
# Then in Python:
# import pyRdfa, io
# from rdflib import Graph
# g = Graph()
# pyRdfa.pyRdfa(base="http://localhost:9000/drivers/1/").graph_from_source(io.StringIO(html), graph=g)
# print(g.serialize(format="turtle"))
```

### Semantic Provenance in the UI

Every page that uses inference displays explicit provenance badges:
- **Purple `SPIN` badge** — data comes from a SPIN `INSERT WHERE` rule
- **Blue `OWL-MAX` badge** — data comes from OWL-Max reasoning at import time
- **Teal `WIKIDATA` badge** — data fetched from Wikidata SPARQL endpoint
- **Orange `DBPEDIA` badge** — data fetched from DBpedia SPARQL endpoint
- **Grey `WIKIPEDIA` badge** — data fetched from Wikipedia REST API

A collapsible **Semantic Provenance panel** on each detail page lists every inference and enrichment source for that specific entity.

### External Enrichment (Wikidata + DBpedia)

All enrichment is loaded **asynchronously** after page render — the page loads instantly and data is injected once the `fetch()` resolves. Results are cached in-process.

| Entity | Source | Properties |
|--------|--------|-----------|
| Driver | Wikidata | P570 death†, P2048 height, P19 birthPlace, P22 father, P40 children |
| Constructor | Wikidata | P154 logo, P856 website, P17 country, P112 founder, P576 dissolved |
| Circuit | DBpedia | turns, capacity, opened, lapRecord, surface, thumbnail |
| Race | DBpedia | weather, attendance, thumbnail |
| All | Wikipedia REST | description, extract, thumbnail |

DBpedia circuits and races are queried via direct resource URI (`dbr:Circuit_de_Monaco`, `dbr:2024_Monaco_Grand_Prix`) because F1 entities in DBpedia are not typed as `dbo:RaceTrack` or similar.

---

## Namespaces

| Prefix | IRI |
|--------|-----|
| `f1:` | `http://example.org/f1/` |
| `res:` | `http://example.org/resource/` |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` |
| `owl:` | `http://www.w3.org/2002/07/owl#` |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` |

Entity URI patterns: `res:driver/{id}`, `res:constructor/{id}`, `res:circuit/{id}`, `res:race/{id}`, `res:result/{id}`, `res:season/{year}`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Django 5 |
| Triple store | GraphDB Free 11 (owl-max-optimized ruleset) |
| SPARQL client | SPARQLWrapper 2 |
| RDF library | rdflib 7 |
| MF2 parser | mf2py |
| RDFa validator | pyrdfa3 (local validation) |
| External data | SPARQLWrapper → Wikidata / DBpedia; urllib → Wikipedia REST API |
| LLM assistant | Google Gemini API |
| Front-end | Vanilla HTML/CSS (dark/light theme, Barlow Condensed font) |

---

## Project Structure

```
data/
  raw/                          — Ergast/Kaggle CSV files (gitignored)
  rdf/
    formula1_ontology.ttl       — OWL 2 DL ontology (hand-authored, in git)
    formula1.nt                 — Generated facts (gitignored, ~798 MB)
    formula1_integrated.nt      — Merged ontology + facts (gitignored)

scripts/
  setup.sh                      — Full zero-to-running setup
  create_graphdb_repo.sh        — Creates ws-formula1-owlmax repository
  csv_to_rdf.py                 — CSV → N-Triples
  merge_integrated.py           — Merges ontology + facts for GraphDB load
  load_rdf_to_graphdb.sh        — Server-side import + inference verification
  run_webserver.sh              — Starts Django on port 9000

championship/
  spin_rules.py                 — 21 SPARQL inference rules
  views.py                      — All Django views + API endpoints
  urls.py                       — URL routing
  services/
    graphdb.py                  — GraphDBClient (query, run_update, healthcheck)
    external_data.py            — Wikidata / DBpedia / Wikipedia enrichment
  management/commands/
    run_spin_rules.py           — `python manage.py run_spin_rules`

templates/championship/
  base.html                     — Nav, theme toggle, src-badge CSS, wiki-img-slot JS
  driver_detail.html            — schema:Person + h-card; SPIN provenance panel
  constructor_detail.html       — schema:SportsOrganization + h-card
  circuit_detail.html           — schema:SportsActivityLocation + h-card + h-adr
  race_detail.html              — schema:SportsEvent + h-event; DBpedia weather/photo
  season_detail.html            — schema:SportsEvent + h-event
  home.html                     — schema:Dataset
  hall_of_fame.html             — Hall of Fame dashboard
  champions.html                — f1:WorldChampion SPIN
  multichampions.html           — f1:MultichampionDriver SPIN
  veterans.html                 — f1:Veteran SPIN
  constructor_champions.html    — f1:ConstructorChampion SPIN
  pole_positions.html           — f1:startedFromP1 SPIN
  hat_tricks.html               — f1:achievedHatTrick SPIN
  [+ races, circuits, seasons, constructors, drivers list pages]

report/
  report_tp2.tex                — TP2 LaTeX report (40 pages)
  report_tp2.pdf                — Compiled report PDF
  build.sh                      — Compile report: cd report && ./build.sh
  figures/                      — Rendered Mermaid diagram PNGs (fig1–fig4)
  tables/                       — Reusable LaTeX table fragments
```

### Building the report PDF

```bash
cd report
./build.sh
```

Requires `pdflatex` (`texlive-latex-extra` on Ubuntu, MacTeX on macOS).
