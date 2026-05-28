# TP2 — F1 Knowledge System: Full Project Documentation

> MEI Web Semantics — Rodrigo Abreu  
> Continuation of TP1 (15/20). This document covers everything implemented in TP2 and serves as the basis for the LaTeX report.

---

## 1. Project Overview

TP2 extends the TP1 F1 website by adding a **semantic knowledge layer**: a formal OWL ontology, a GraphDB triple store, SPARQL inference via SPIN rules, RDF reification, and semantic markup (RDFa 1.1 Lite + Microformats 2) embedded in HTML pages. The system automatically classifies F1 entities (World Champions, Veterans, Constructor Champions, etc.) by reasoning over the raw data — none of these classifications exist in the source CSV files.

**Stack:**
- Django 6.0 + Python 3.12
- GraphDB Desktop (OWL-Max with RDFS ruleset)
- RDFlib 7.6 + SPARQLWrapper 2.0
- mf2py 2.0 (Microformats 2 parser)
- Wikidata + DBpedia via SPARQLWrapper (live semantic enrichment)
- Wikipedia REST API (entity summaries and images)

**Data source:** Ergast F1 dataset (CSV) — 75 seasons (1950–2024), 861 drivers, 212 constructors, 77 circuits, ~25,000 race results.

---

## 2. Data Pipeline

```
Ergast CSV files
       │
       ▼  scripts/csv_to_rdf.py
N-Triples facts (formula1.nt)
— no rdf:type for Driver/Constructor/Circuit (inferred by ontology)
       │
       ▼  scripts/merge_integrated.py
Integrated file = ontology.ttl + formula1.nt
       │
       ▼  GraphDB (OWL-Max + RDFS ruleset, load at startup)
Triple store — base classes inferred at load time via rdfs:domain
       │
       ▼  python manage.py run_spin_rules  (15 SPARQL INSERT WHERE rules)
Enriched graph — classifications, properties, reification nodes
```

### Key design decision: no explicit `rdf:type` for base classes

`csv_to_rdf.py` emits **no** `rdf:type f1:Driver` (or Constructor, Circuit). The `infer_type: True` flag in `TABLE_CONFIG` suppresses the type triple. Instead, GraphDB's OWL-Max ruleset infers the type from `rdfs:domain`:

```turtle
f1:driverRef rdfs:domain f1:Driver .
```

So `<driver/1> f1:driverRef "hamilton"` → GraphDB infers `<driver/1> rdf:type f1:Driver` automatically. The ontology does the classification, not the raw data.

---

## 3. Ontology (`data/rdf/formula1_ontology.ttl`)

### 3.1 Class Hierarchy

```
owl:Thing
├── f1:Entity
│   ├── f1:Person → f1:Driver → f1:WorldChampion → f1:MultichampionDriver
│   │                         → f1:Veteran
│   ├── f1:Team   → f1:Constructor → f1:ConstructorChampion
│   └── f1:Venue  → f1:Circuit    → f1:ActiveCircuit
│                                  → f1:HistoricCircuit
├── f1:Event
│   ├── f1:Race
│   └── f1:Season
├── f1:PerformanceRecord
│   ├── f1:Result → f1:PodiumResult
│   ├── f1:QualifyingResult
│   ├── f1:LapTime
│   ├── f1:PitStop
│   └── f1:ConstructorResult
└── f1:Standing
    ├── f1:DriverStanding
    └── f1:ConstructorStanding
```

### 3.2 OWL Profile: OWL 2 DL

The ontology uses **OWL 2 DL** — a decidable fragment of first-order logic. GraphDB is configured with the **OWL-Max with RDFS** ruleset which handles all RDFS axioms plus the OWL subset it supports at load time.

**OWL constructs used:**

| Construct | Where | Purpose |
|---|---|---|
| `owl:equivalentClass` + `owl:someValuesFrom` | Driver, Constructor, Circuit | Bidirectional inference: entity with `driverRef` ≡ Driver |
| `rdfs:domain` | `driverRef`, `constructorRef`, `circuitRef` | GraphDB infers `rdf:type` from property usage |
| `rdfs:subClassOf` | Full hierarchy | Class inheritance |
| `owl:disjointWith` | Driver↔Constructor, Race↔Season, etc. | Prevents cross-entity type confusion |
| `owl:FunctionalProperty` | `race`, `driver`, `status`, `circuit`, `season`, `heldAt` | At most one value per subject |
| `owl:SymmetricProperty` | `wasTeammate` | `x wasTeammate y → y wasTeammate x` |
| `owl:inverseOf` | `hadDriver ↔ drovFor` | Constructor↔Driver bidirectional traversal |
| `rdfs:subPropertyOf` | `wonRace ⊑ competedIn`, `achievedPodium ⊑ competedIn` | Property hierarchy |
| `owl:maxCardinality` | `Race ⊑ ≤1 circuit` | Race held at exactly one circuit |

### 3.3 Why `rdfs:domain` is NOT declared on FK properties

Properties like `f1:driverId`, `f1:constructorId`, `f1:raceId` appear as literal columns on **multiple entity types** (e.g., a `Result` row contains `driverId`, `constructorId`, `raceId` as literals). Declaring `rdfs:domain f1:Driver` on `f1:driverId` would cause GraphDB to infer that every `Result` individual is also a `Driver`, triggering the `owl:disjointWith f1:Constructor` inconsistency. Domain is intentionally omitted.

### 3.4 Inference verified (15/15 checks pass)

| Mechanism | Inferred | Count |
|---|---|---|
| `rdfs:domain driverRef` | `f1:Driver` entities | 861 |
| `rdfs:domain constructorRef` | `f1:Constructor` entities | 212 |
| `rdfs:domain circuitRef` | `f1:Circuit` entities | 77 |
| SPIN: `classify_WorldChampion` | `f1:WorldChampion` | 34 |
| SPIN: `classify_MultichampionDriver` | `f1:MultichampionDriver` | 17 |
| SPIN: `classify_Veteran` | `f1:Veteran` | 86 |
| SPIN: `classify_ConstructorChampion` | `f1:ConstructorChampion` | 17 |
| SPIN: `classify_ActiveCircuit` | `f1:ActiveCircuit` | 24 |
| SPIN: `classify_HistoricCircuit` | `f1:HistoricCircuit` | 45 |
| SPIN: `classify_PodiumResult` | `f1:PodiumResult` | 3,397 |
| SPIN: `infer_wonRace` | `f1:wonRace` triples | 1,128 |
| SPIN: `infer_wasTeammate` | `f1:wasTeammate` triples | 10,012 |
| SPIN: `infer_wonChampionship` | `f1:wonChampionship` triples | 75 |
| `owl:inverseOf` | `f1:hadDriver` triples | 2,150 |
| SPIN: `infer_heldAt` | `f1:heldAt` triples | 1,125 |

---

## 4. SPIN Rules (`championship/spin_rules.py`)

SPIN (SPARQL Inference Notation) fills the gap where OWL DL cannot express classification — specifically: **aggregation** (`COUNT`, `MAX`, `GROUP BY`), **arithmetic comparisons** (`positionOrder ≤ 3`), and **negation-as-failure** (`FILTER NOT EXISTS`).

**15 rules, run via `python manage.py run_spin_rules`:**

| Rule | Why OWL cannot express it |
|---|---|
| `infer_wonRace` | Requires `positionOrder = 1` arithmetic check |
| `infer_achievedPodium` | Requires `positionOrder ≤ 3` |
| `infer_drovFor` | Cross-table join: Result → constructor link |
| `infer_wasTeammate` | Cross-entity join: same race + same constructor, different driver |
| `infer_wonChampionship` | `GROUP BY + MAX(round)` to find final round per season |
| `reify_wonChampionship` | Creates `rdf:Statement` nodes with final points annotation |
| `infer_heldAt` | Materialises `f1:heldAt` from `f1:circuit` on Race |
| `classify_WorldChampion` | Depends on SPIN-inferred `wonChampionship` |
| `classify_MultichampionDriver` | `COUNT(championships) ≥ 2` aggregation |
| `classify_Veteran` | `COUNT(results) ≥ 100` aggregation |
| `classify_ActiveCircuit` | `MAX(year)` = dataset maximum |
| `classify_HistoricCircuit` | `MAX(year) + 10 < dataset maximum` + negation-as-failure |
| `classify_PodiumResult` | `positionOrder ≤ 3` arithmetic |
| `infer_wonConstructorChampionship` | `GROUP BY + MAX(round)` for constructors |
| `classify_ConstructorChampion` | Depends on SPIN-inferred `wonConstructorChampionship` |

### Bug fixed during development

**Bug 1 — `infer_wonChampionship` and `infer_wonConstructorChampionship`** originally had:
```sparql
?season f1:year ?yr .  -- matched ANY resource with f1:year, including Race entities
```
This caused 1,200 triples instead of 75 (factor of ~16 = races per season), and made every World Champion also a Multi-Champion (34/34 instead of 17/34). Fixed by adding the type guard:
```sparql
?season rdf:type f1:Season ;
        f1:year ?yr .
```

**Bug 2 — `reify_wonChampionship`** originally queried `?ds f1:driver ?driver ; f1:points ?pts` without restricting to `DriverStanding` entities. Both `DriverStanding` and `Result` entities have `f1:driver` and `f1:points`, causing duplicate reification nodes (148 instead of 75). Fixed by adding:
```sparql
?ds rdf:type f1:DriverStanding ;
```

---

## 5. RDF Reification

**Where:** `reify_wonChampionship` SPIN rule  
**Pattern:** `rdf:Statement` with `rdf:subject`, `rdf:predicate`, `rdf:object`, and `f1:finalPoints`  
**Result:** 75 `rdf:Statement` nodes — one per F1 season championship — annotated with the final season points total.

```sparql
INSERT {
  _:stmt rdf:type      rdf:Statement ;
         rdf:subject   ?driver ;
         rdf:predicate f1:wonChampionship ;
         rdf:object    ?season ;
         f1:finalPoints ?pts .
}
WHERE {
  ?driver f1:wonChampionship ?season .
  ?season rdf:type f1:Season ; f1:year ?yr .
  ?ds rdf:type f1:DriverStanding ;
      f1:driver ?driver ; f1:race ?race ; f1:points ?pts .
  ?race f1:round ?round ; f1:year ?yr .
  { SELECT ?yr (MAX(?r) AS ?maxRound)
    WHERE { ?rc f1:round ?r ; f1:year ?yr . } GROUP BY ?yr }
  FILTER(?round = ?maxRound)
  FILTER NOT EXISTS {
    ?s rdf:type rdf:Statement ;
       rdf:subject ?driver ; rdf:predicate f1:wonChampionship ; rdf:object ?season
  }
}
```

**Why reification?** The triple `driver wonChampionship season` already exists as a plain triple. Reification allows attaching the final championship points *to that triple itself* — not to the driver (who has many seasons) or the season (which has one champion). This is the canonical RDF use case for reification: making statements about statements.

The `f1:finalPoints` property is declared in `formula1_ontology.ttl` with `rdfs:domain rdf:Statement`, ensuring it only appears on reification nodes.

**Sample data** (verified in GraphDB):

| Driver | Year | Final Points |
|---|---|---|
| Lewis Hamilton | 2020 | 347.0 |
| Max Verstappen | 2023 | 575.0 |
| Michael Schumacher | 2004 | 148.0 |

The reification data is exposed on the `/tools/` page via a live SPARQL query.

---

## 6. RDFa 1.1 Lite

**Standard:** RDFa 1.1 Lite using Schema.org vocabulary  
**Files:** All detail templates (`driver_detail.html`, `constructor_detail.html`, `circuit_detail.html`, `race_detail.html`, `season_detail.html`, `champions.html`)

**Attributes used:**

| Attribute | Purpose |
|---|---|
| `vocab="https://schema.org/"` | Declares the Schema.org vocabulary for the block |
| `typeof="Person"` | Driver entities are `schema:Person` |
| `typeof="SportsOrganization"` | Constructor entities |
| `typeof="SportsActivityLocation"` | Circuit entities |
| `typeof="SportsEvent"` | Race entities |
| `typeof="Event"` | Season entities |
| `typeof="ItemList"` | Champions listing page |
| `property="name"` | Entity label |
| `property="birthDate"` | Driver date of birth |
| `property="nationality"` | Driver/Constructor nationality |
| `property="latitude"`, `property="longitude"` | Circuit geo-coordinates (in `<meta>`) |
| `property="startDate"` | Race date |
| `property="sameAs"` | Link to Wikipedia (`rdfs:seeAlso`) |
| `resource="{{ request.build_absolute_uri }}"` | Canonical URI for the entity |
| `property="itemListElement"` | Champions list items |

**Validation tools used:**
- W3C pyRDFa distiller: `https://www.w3.org/2012/pyRdfa/extract?format=turtle&uri=<page_url>`
- Google Rich Results Test: `https://search.google.com/test/rich-results?url=<page_url>`
- RDFa Play: `https://rdfa.info/play/` — paste page HTML to visualise extracted triples

All three are linked from the `/tools/` Semantic Tools page.

---

## 7. Microformats 2

**Standard:** Microformats 2 (independent of any vocabulary declaration)  
**Files:** Same detail templates as RDFa

**Classes used:**

| Class | Standard | Used on |
|---|---|---|
| `h-card` | hCard | Driver, Constructor, Circuit articles |
| `h-event` | hEvent | Race, Season articles |
| `h-adr` | hAdr | Circuit address block |
| `p-name` | hCard/hEvent | Entity name |
| `p-nationality` | hCard | Driver/Constructor nationality |
| `p-country-name` | hAdr | Circuit country |
| `p-locality` | hAdr | Circuit city |
| `dt-bday` | hCard | Driver date of birth |
| `dt-start` | hEvent | Race/Season start date |
| `u-url` | hCard/hEvent | Link to Wikipedia (same as `sameAs`) |

**Why both RDFa and Microformats 2?** They serve different parsers and ecosystems. RDFa integrates with the OWL ontology namespace and is consumed by SPARQL-aware tools and Google's Knowledge Graph. Microformats 2 requires no vocabulary declaration and is parsed by IndieWeb tools, social readers, and contact importers. Showing both demonstrates mastery of both standards and their respective trade-offs.

**Parser demonstration:** The `/tools/` page includes a live Microformats 2 parser (powered by `mf2py`) that fetches any page of the site and displays the extracted JSON — demonstrating the complete round-trip: HTML emits MF2 → `mf2py` parses it back.

---

## 8. External Semantic Enrichment

All external enrichment is **loaded asynchronously** — detail pages render instantly, and enrichment data is injected into the hero section after a `fetch()` call to `/api/entity-info/`. This eliminates the 2–8 second SPARQL timeout from the page load critical path.

### 8.1 Drivers (Wikidata — `wdt:P106 wd:Q10843402`)

`get_driver_wikidata(name)` queries Wikidata for F1 drivers by label match.

| Wikidata Property | Field returned | Display |
|---|---|---|
| P19 | `birthPlace` | City of birth in hero meta chips |
| P18 | `image` | Portrait photo for hero avatar |
| P570 | `deathDate` | `†` suffix on driver name, lifespan replaces age chip |
| P2048 | `height` | Height chip in hero meta |
| P22 | `fatherName` | "Father: Graham Hill" — F1 dynasty link |
| P40 | `childNames` | "Son: Mick Schumacher" — F1 dynasty link |
| schema:description | `description` | Short tagline |

Notable use cases:
- Ayrton Senna, Roland Ratzenberger, Jochen Rindt, Jim Clark — all display `† [year]`
- Graham Hill / Damon Hill, Gilles / Jacques Villeneuve, Michael / Mick Schumacher — family links shown
- Height shown for all drivers where available

### 8.2 Constructors (Wikidata — `wdt:P31 wd:Q41298738`)

`get_constructor_wikidata(name)` queries Wikidata for F1 teams.

| Wikidata Property | Field returned | Display |
|---|---|---|
| P571 | `foundingDate` | Founding year in stats list |
| P159 | `hq` | Headquarters in stats list |
| P154 | `logo` | Official team logo replaces Wikipedia thumbnail |
| P856 | `website` | Official website link in stats list |
| P17 | `country` | Country of origin as meta chip |
| P112 | `founder` | Who founded the team in stats list |
| P576 | `dissolved` | "Dissolved YYYY" chip for defunct teams |

### 8.3 Circuits (DBpedia — direct URI approach)

`get_circuit_dbpedia(name)` constructs the DBpedia resource URI directly from the circuit name:

```python
resource_uri = "http://dbpedia.org/resource/" + circuit_name.replace(" ", "_")
# "Circuit de Monaco" → dbr:Circuit_de_Monaco
```

**Why direct URI instead of label matching?** F1 circuits in DBpedia are **not** typed as `dbo:RaceTrack` — they use generic types (`owl:Thing`, `geo:SpatialThing`). Label-matching queries with a `dbo:RaceTrack` constraint never find them. The direct URI approach is reliable because circuit names in the Ergast dataset follow the same Wikipedia/DBpedia naming conventions.

| DBpedia Property | Field returned | Display |
|---|---|---|
| dbo:abstract | `abstract` | English description in hero |
| dbp:length | `length` | Track length injected into Circuit details list |
| dbp:turns | `turns` | Number of corners injected |
| dbp:capacity | `capacity` | Spectator capacity (formatted with locale) injected |
| dbp:opened | `opened` | Year circuit opened injected |
| dbp:lapRecord | `lapRecord` | Fastest lap ever (driver, time, year) in dedicated panel |

Sample data confirmed in GraphDB:
- Circuit de Monaco: 12 turns, 37,000 capacity, opened 1929
- Silverstone: 6 turns, 164,000 capacity, opened 1948

### 8.4 Wikipedia REST API

`get_wikipedia_summary(wiki_url)` uses `/api/rest_v1/page/summary/<title>`. Returns: `image` (thumbnail), `description` (short tagline), `extract` (first paragraph, max 500 chars). Used as primary source of the text description shown in hero sections, with semantic source attribution always labelled as "Wikidata" or "DBpedia" (never "Wikipedia") since the structured facts come from those endpoints.

---

## 9. Web Application Pages

| URL | Page | Key semantic features |
|---|---|---|
| `/drivers/` | All Drivers | Server-side filter + Filter button, card scale hover, podium page-1-only, RDFa |
| `/drivers/<id>/` | Driver Detail | Async Wikidata (death date †, height, family links), constructor career deep-links, lightbox photo, h-card + RDFa |
| `/constructors/` | All Constructors | Filter + RDFa |
| `/constructors/<id>/` | Constructor Detail | Async Wikidata (logo, website, country, founder, dissolved), drivers table with links |
| `/constructors/champions/` | Constructor Champions | `f1:ConstructorChampion` SPIN-inferred, scale-hover cards |
| `/circuits/` | All Circuits | Filter + RDFa |
| `/circuits/<id>/` | Circuit Detail | Async DBpedia (turns, capacity, opened, lap record), lightbox photo, h-adr + RDFa |
| `/seasons/` | All Seasons | Card/table toggle, reactive sort |
| `/seasons/<year>/` | Season Detail | Full results, standings, deep links to races/drivers/constructors/circuits |
| `/races/` | All Races | Filter + button |
| `/races/<id>/` | Race Detail | Podium with wiki images, constructor links in results, driver links throughout |
| `/champions/` | World Champions | `f1:WorldChampion` SPIN-inferred, wiki photos, scale-hover cards, RDFa ItemList |
| `/champions/multi/` | Multi-Champions | `f1:MultichampionDriver` SPIN-inferred (COUNT ≥ 2), scale-hover cards |
| `/champions/veterans/` | Veterans | `f1:Veteran` SPIN-inferred (100+ races), table with champion badge |
| `/tools/` | Semantic Tools | RDF reification live SPARQL viewer, MF2 live parser, RDFa Play/W3C distiller links |
| `/assistant/` | F1 Assistant | LLM-powered Q&A over the knowledge graph |

### Navigation structure

The navigation uses **dropdown menus** to group related pages:

- **Drivers** dropdown → All Drivers / World Champions / Multi-Champions / Veterans
- **Constructors** dropdown → All Constructors / Constructor Champions
- Single links: Seasons, Races, Circuits, F1 Assistant

---

## 10. Key Implementation Decisions

### 10.1 Two-layer inference architecture

| Layer | Mechanism | When it runs | What it handles |
|---|---|---|---|
| OWL (Layer 1) | GraphDB built-in ruleset | At triple load time | `rdfs:domain/range`, `owl:inverseOf`, `owl:SymmetricProperty`, `rdfs:subPropertyOf` |
| SPIN (Layer 2) | `manage.py run_spin_rules` | On demand | Aggregation, arithmetic, negation-as-failure, reification |

### 10.2 RDF reification vs named graphs

Named graphs could also annotate championship data. Reification was chosen because it is the **standard RDF mechanism** for making statements about statements, uses the built-in `rdf:Statement` vocabulary, and works without quad-store semantics. It is also directly supported by SPARQL 1.1 `INSERT` with blank node subjects.

### 10.3 Asynchronous external enrichment

All Wikidata/DBpedia/Wikipedia calls are deferred to after page render. The page HTML loads in under 500ms; enrichment data is injected into the hero section after a `fetch()` call completes. This is architecturally significant: it separates the semantic knowledge graph (local, fast) from the linked data enrichment (remote, slower).

### 10.4 DBpedia resource URI construction

The circuit enrichment query uses direct resource URI construction rather than label-matching:
```python
"http://dbpedia.org/resource/" + circuit_name.replace(" ", "_")
```
This works because F1 circuits in DBpedia are not typed as `dbo:RaceTrack` (they use `owl:Thing`) — label-matching with a type constraint never returns results. Direct URI lookup is also faster and more reliable.

### 10.5 SPARQL property paths and graph traversal

The ontology's `rdfs:subPropertyOf` chain (`wonRace ⊑ competedIn`) enables alternation path queries:
```sparql
?hamilton (f1:wonRace | f1:achievedPodium) ?race .  -- equivalent to competedIn
```

The `owl:SymmetricProperty` on `wasTeammate` enables 2-hop teammate queries:
```sparql
?h f1:wasTeammate/f1:wasTeammate ?t .  -- teammates of teammates
```

### 10.6 Interesting SPARQL use cases (only possible via inference)

**World Champions who raced as teammates:**
```sparql
SELECT ?aLabel ?bLabel WHERE {
  ?a rdf:type f1:WorldChampion ; rdfs:label ?aLabel ; f1:wasTeammate ?b .
  ?b rdf:type f1:WorldChampion ; rdfs:label ?bLabel .
  FILTER(?a != ?b) FILTER(STR(?aLabel) < STR(?bLabel))
}
```
Result: Prost & Senna, Prost & Lauda, Prost & Mansell.

**Constructors that fielded the most World Champions:**
```sparql
SELECT ?ctorLabel (COUNT(DISTINCT ?d) AS ?n) WHERE {
  ?ctor f1:hadDriver ?d .  -- OWL inverseOf-inferred, not in raw data
  ?d rdf:type f1:WorldChampion .
  ?ctor rdfs:label ?ctorLabel .
} GROUP BY ?ctor ?ctorLabel ORDER BY DESC(?n)
```
Result: McLaren (15), Ferrari (15), Williams (11).

**Championship points from reified statements:**
```sparql
SELECT ?driverLabel ?yr ?pts WHERE {
  ?stmt rdf:type rdf:Statement ;
        rdf:predicate f1:wonChampionship ;
        rdf:subject ?driver ; rdf:object ?season ;
        f1:finalPoints ?pts .
  ?driver rdfs:label ?driverLabel .
  ?season f1:year ?yr .
} ORDER BY DESC(?yr)
```
Result: Only answerable via RDF reification — the final points attached to the triple.

---

## 11. Differences from TP1

| Feature | TP1 | TP2 |
|---|---|---|
| Data storage | SQLite (Django ORM) | GraphDB triple store (SPARQL) |
| Data model | Relational tables | RDF triples + OWL 2 DL ontology |
| Classification | Hard-coded SQL queries | OWL inference + SPIN rules |
| Web queries | SQL | SPARQL 1.1 |
| Entity typing | Explicit columns | `rdfs:domain` inference — no explicit `rdf:type` in facts |
| Semantic markup | None | RDFa 1.1 Lite (Schema.org) + Microformats 2 |
| External enrichment | None | Wikidata + DBpedia + Wikipedia REST API (async) |
| RDF reification | None | 75 `rdf:Statement` nodes with `f1:finalPoints` |
| Navigation | Flat links | Dropdown menus (Champions/Veterans under Drivers, etc.) |
| Detail pages | Static | Dynamic: lightbox photo, async enrichment in hero section |
| Performance | All data synchronous | External calls deferred to after page render |
| Entity sub-pages | None | Multi-Champions, Veterans, Constructor Champions |

---

## 12. Tools and Validation

| Tool | URL / Command | What it validates |
|---|---|---|
| W3C RDFa Distiller | `https://www.w3.org/2012/pyRdfa/extract?format=turtle&uri=<url>` | Extracts RDFa triples as Turtle from any page |
| Google Rich Results | `https://search.google.com/test/rich-results?url=<url>` | Schema.org structured data |
| RDFa Play | `https://rdfa.info/play/` | Paste page HTML to visualise extracted RDF graph |
| mf2py parser | `/api/parse-microformats/?url=<url>` | Parses MF2 from any site page, returns JSON |
| SPIN inference | `python manage.py run_spin_rules` | Materialises all 15 SPIN rules, reports OK/ERR per rule |
| GraphDB SPARQL | `http://localhost:7200/` | Direct SPARQL queries on the live graph |
| Protégé + HermiT | Protégé desktop | OWL 2 DL consistency check (completes in 265ms) |
| Semantic Tools page | `/tools/` | Live reification viewer, MF2 parser, RDFa distiller links |

---

## 13. Files Reference

```
data/rdf/
  formula1_ontology.ttl      — OWL 2 DL ontology (18 classes, 15+ object/data properties)
                               includes f1:finalPoints (rdfs:domain rdf:Statement)
  formula1.nt                — N-Triples facts (no explicit rdf:type for Driver/Constructor/Circuit)

scripts/
  csv_to_rdf.py              — Converts Ergast CSV → N-Triples (infer_type flag suppresses rdf:type)
  merge_integrated.py        — Merges ontology + facts into one NT file for GraphDB load
  generate_ontology_diagram.py — Generates docs/ontology_diagram.svg

championship/
  spin_rules.py              — 15 SPARQL INSERT WHERE rules + bug fix notes
  views.py                   — All Django views; api_entity_info (async enrichment endpoint)
  services/
    graphdb.py               — GraphDBClient (query + run_update)
    external_data.py         — Wikidata (drivers+constructors), DBpedia (circuits),
                               Wikipedia REST API; direct URI approach for DBpedia
  management/commands/
    run_spin_rules.py        — Django management command

templates/championship/
  base.html                  — Global nav (dropdowns), theme toggle, card scale-hover CSS,
                               dialog lightbox CSS, wiki-img-slot JS, MF2/RDFa utilities
  driver_detail.html         — h-card + RDFa Person; async: death date †, height, family,
                               description from Wikidata; photo lightbox
  constructor_detail.html    — h-card + RDFa SportsOrganization; async: logo, website,
                               country, founder, dissolved from Wikidata; lightbox
  circuit_detail.html        — h-adr + RDFa SportsActivityLocation; async: turns, capacity,
                               opened, lap record from DBpedia; lightbox
  race_detail.html           — h-event + RDFa SportsEvent; constructor links in podium + table
  season_detail.html         — h-event + RDFa Event; circuit + constructor deep links
  champions.html             — RDFa ItemList; SPIN-inferred WorldChampion; scale-hover cards
  multichampions.html        — SPIN-inferred MultichampionDriver; scale-hover cards
  veterans.html              — SPIN-inferred Veteran (100+ races); table view with champion badge
  constructor_champions.html — SPIN-inferred ConstructorChampion; scale-hover cards
  semantic_tools.html        — Live reification SPARQL viewer, mf2py parser, RDFa links

docs/
  ontology_diagram.md        — Mermaid classDiagram of the full ontology
  ontology_diagram.svg       — Auto-generated SVG rendering
  ONTOLOGY_INFERENCE.md      — Inference verification (15/15 checks with real counts) + SPARQL use cases
  tp2_documentation.md       — This file
```

---

## 14. Known Issues and Design Notes

### SPIN rule ordering matters
The `infer_wonChampionship` rule must run before `classify_WorldChampion`, which must run before `classify_MultichampionDriver`. The rules in `spin_rules.py` are ordered accordingly and executed sequentially.

### Wikidata rate limiting
Wikidata enforces a rate limit of ~1 request per minute during outage periods. Enrichment calls are cached in-process (`_cache` dict in `external_data.py`), so repeated page views of the same entity do not re-query. In production, the cache should be replaced with Redis for persistence across restarts.

### DBpedia label variations
The direct URI approach (`dbr:Circuit_de_Monaco`) works for circuits whose DBpedia URI matches the Ergast label exactly. Circuits with different naming (e.g. abbreviations) may return empty results. The fallback is the Wikipedia summary extract, which always returns a description.

### OWL vs SPIN boundary
OWL DL (even OWL 2 DL) cannot express:
- Arithmetic comparisons on data values (`positionOrder ≤ 3`)
- Aggregation (`COUNT`, `GROUP BY`, `MAX`)
- Negation-as-failure (`FILTER NOT EXISTS` over derived patterns)
- Cross-entity joins with non-local pattern matching

All of these are handled exclusively by SPIN rules. The boundary is intentional and documented in both `spin_rules.py` (per-rule comments) and `ONTOLOGY_INFERENCE.md`.
