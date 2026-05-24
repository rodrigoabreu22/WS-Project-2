# F1 Knowledge System — Ontology & Inference Capabilities

> MEI Web Semantics TP2 — Rodrigo Abreu  
> Generated against live GraphDB data — 2026-05-24

---

## 1. Inference Verification

All 15 inference checks pass against the live knowledge graph.

| Status | Count | What is being inferred | Mechanism |
|--------|------:|------------------------|-----------|
| ✅ | 861 | `f1:Driver` entities | OWL `rdfs:domain` of `f1:driverRef` |
| ✅ | 212 | `f1:Constructor` entities | OWL `rdfs:domain` of `f1:constructorRef` |
| ✅ | 77 | `f1:Circuit` entities | OWL `rdfs:domain` of `f1:circuitRef` |
| ✅ | 34 | `f1:WorldChampion` drivers | SPIN rule — position 1 at final round |
| ✅ | 17 | `f1:MultichampionDriver` | SPIN rule — COUNT(championships) ≥ 2 |
| ✅ | 86 | `f1:Veteran` drivers | SPIN rule — COUNT(results) ≥ 100 |
| ✅ | 17 | `f1:ConstructorChampion` | SPIN rule — constructor standings, final round (F1 started in 1950, constructors' championship in 1958) |
| ✅ | 24 | `f1:ActiveCircuit` | SPIN rule — MAX(year) in dataset |
| ✅ | 45 | `f1:HistoricCircuit` | SPIN rule — no race in last 10 years of dataset |
| ✅ | 3,397 | `f1:PodiumResult` results | SPIN rule — positionOrder ≤ 3 |
| ✅ | 1,128 | `f1:wonRace` triples | SPIN rule — positionOrder = 1 |
| ✅ | 10,012 | `f1:wasTeammate` triples | SPIN rule — same race, same constructor |
| ✅ | 75 | `f1:wonChampionship` triples | SPIN rule — driver standings, final round per season |
| ✅ | 2,150 | `f1:hadDriver` triples | OWL `owl:inverseOf f1:drovFor` |
| ✅ | 1,125 | `f1:heldAt` triples | SPIN rule — materialised from `f1:circuit` |

### Key point: base class inference without explicit `rdf:type`

The facts file (`formula1.nt`) does **not** contain a single `rdf:type f1:Driver` triple.  
Instead, `csv_to_rdf.py` emits the `f1:driverRef` data property, and GraphDB's OWL-Max
ruleset applies the `rdfs:domain` axiom at load time:

```
f1:driverRef rdfs:domain f1:Driver .
```

So `<driver/1> f1:driverRef "hamilton"` automatically yields `<driver/1> rdf:type f1:Driver`
— the ontology does the classification work, not the raw data.

You can verify this distinction with two SPARQL queries in `/sparql/`:

```sparql
-- Should return 0 (no explicit type in facts)
SELECT (COUNT(*) AS ?explicit) WHERE {
  ?d f1:driverRef ?ref .
  FILTER NOT EXISTS { ?d rdf:type f1:Driver }
}

-- Should return 861 (inferred by rdfs:domain)
SELECT (COUNT(*) AS ?inferred) WHERE { ?d rdf:type f1:Driver }
```

---

## 2. Two-Layer Inference Architecture

The system uses two complementary mechanisms:

### Layer 1 — OWL reasoning (GraphDB built-in, always on)

Handled by GraphDB's **OWL-Max with RDFS** ruleset. Runs at triple load time.

| Axiom type | Example | What it infers |
|---|---|---|
| `rdfs:domain` | `driverRef domain Driver` | entity with `driverRef` → `rdf:type Driver` |
| `rdfs:range` | `wonRace range Race` | object of `wonRace` → `rdf:type Race` |
| `rdfs:subClassOf` | `WorldChampion ⊑ Driver` | `WorldChampion` individuals are also `Driver` |
| `owl:inverseOf` | `hadDriver inverseOf drovFor` | `x drovFor y → y hadDriver x` |
| `owl:SymmetricProperty` | `wasTeammate symmetric` | `x wasTeammate y → y wasTeammate x` |
| `rdfs:subPropertyOf` | `wonRace ⊑ competedIn` | `wonRace` triples also appear as `competedIn` |

### Layer 2 — SPIN rules (on-demand, via `python manage.py run_spin_rules`)

Custom SPARQL INSERT WHERE rules for patterns OWL DL **cannot** express:

| Rule | Why OWL cannot express it |
|---|---|
| `classify_WorldChampion` | Requires `GROUP BY + MAX` to find final round of season |
| `classify_Veteran` | Requires `COUNT(results) ≥ 100` — arithmetic aggregation |
| `classify_ActiveCircuit` | Requires `MAX(year)` across dataset — global aggregate |
| `classify_HistoricCircuit` | Requires `MAX(year) - 10` threshold + negation-as-failure |
| `classify_MultichampionDriver` | Requires `COUNT(championships) ≥ 2` |
| `classify_ConstructorChampion` | Depends on `wonConstructorChampionship` — a SPIN-derived property not in raw data |
| `infer_wasTeammate` | Cross-entity join: same race, same constructor, different driver |

---

## 3. Interesting Use Cases

These queries only work because of the inferred knowledge — none of them can be answered from the raw CSV data directly.

### 3.1 — Which World Champions raced as teammates?

Combines `f1:wasTeammate` (SPIN-inferred) with `rdf:type f1:WorldChampion` (SPIN-inferred):

```sparql
SELECT ?a ?aLabel ?b ?bLabel WHERE {
  ?a rdf:type f1:WorldChampion ; rdfs:label ?aLabel ; f1:wasTeammate ?b .
  ?b rdf:type f1:WorldChampion ; rdfs:label ?bLabel .
  FILTER(?a != ?b)
  FILTER(STR(?aLabel) < STR(?bLabel))
} ORDER BY ?aLabel
```

Real result: Alain Prost and Ayrton Senna, Prost and Niki Lauda, Prost and Nigel Mansell — the legendary McLaren era rivalries confirmed by graph traversal.

---

### 3.2 — Which constructors fielded the most World Champions?

Combines `f1:hadDriver` (OWL `owl:inverseOf`-inferred) with `rdf:type f1:WorldChampion`:

```sparql
SELECT ?ctorLabel (COUNT(DISTINCT ?d) AS ?champions) WHERE {
  ?ctor f1:hadDriver ?d .
  ?d rdf:type f1:WorldChampion .
  ?ctor rdfs:label ?ctorLabel .
} GROUP BY ?ctor ?ctorLabel
ORDER BY DESC(?champions) LIMIT 8
```

Real result: McLaren (15), Ferrari (15), Williams (11), Team Lotus (10).  
This is only answerable because `hadDriver` is OWL-inferred from `drovFor` — it is not a property in the raw data.

---

### 3.3 — World Champions who won races at Historic Circuits

Joins `f1:wonRace` (SPIN) + `f1:heldAt` (SPIN) + `rdf:type f1:HistoricCircuit` (SPIN):

```sparql
SELECT DISTINCT ?dLabel ?cLabel WHERE {
  ?d rdf:type f1:WorldChampion ; rdfs:label ?dLabel .
  ?d f1:wonRace ?race .
  ?race f1:heldAt ?circuit .
  ?circuit rdf:type f1:HistoricCircuit ; rdfs:label ?cLabel .
} ORDER BY ?dLabel
```

Real result: Alain Prost won at Kyalami, Magny-Cours, Estoril — circuits no longer on the F1 calendar. Purely synthesised knowledge: neither "wonRace" nor "HistoricCircuit" exist in raw data.

---

### 3.4 — Veteran World Champions (class intersection)

OWL class intersection of two SPIN-inferred classes:

```sparql
SELECT ?dLabel WHERE {
  ?d rdf:type f1:WorldChampion ;
     rdf:type f1:Veteran ;       -- 100+ race entries
     rdfs:label ?dLabel .
} ORDER BY ?dLabel
```

Real result: champions who also proved longevity across 100+ races — two independently SPIN-inferred classes combined in a single pattern. No raw data table has this concept.

---

### 3.5 — Constructor Champions active at current circuits

Chains `f1:ConstructorChampion` (SPIN) + race wins + `f1:ActiveCircuit` (SPIN):

```sparql
SELECT ?cLabel (COUNT(DISTINCT ?race) AS ?wins) WHERE {
  ?c rdf:type f1:ConstructorChampion ; rdfs:label ?cLabel .
  ?driver f1:drovFor ?c ; f1:wonRace ?race .
  ?race f1:heldAt ?circuit .
  ?circuit rdf:type f1:ActiveCircuit .
} GROUP BY ?c ?cLabel ORDER BY DESC(?wins)
```

Real result: McLaren (315), Ferrari (289), Mercedes (194), Red Bull (131) — race wins at circuits still on the 2024 calendar, filtered to championship-winning teams only.

---

### 3.6 — Find all teammates of a specific champion

Property path + `wasTeammate` (SPIN symmetric):

```sparql
SELECT DISTINCT ?tLabel WHERE {
  ?hamilton rdfs:label "Lewis Hamilton" .
  ?hamilton f1:wasTeammate ?t .
  ?t rdfs:label ?tLabel .
} ORDER BY ?tLabel
```

Returns every driver who shared a garage with Hamilton — derived entirely from race result joins.

---

### 3.7 — Circuits that went from Active to Historic (temporal gap)

Only possible because both `f1:ActiveCircuit` and `f1:HistoricCircuit` are SPIN-inferred:

```sparql
SELECT ?cLabel WHERE {
  ?c rdf:type f1:HistoricCircuit ; rdfs:label ?cLabel .
  FILTER NOT EXISTS { ?c rdf:type f1:ActiveCircuit }
} ORDER BY ?cLabel
```

---

## 4. Full Potential of This RDF + Ontology Stack

### 4.1 — Federated SPARQL (live Wikidata enrichment)

SPARQL 1.1 allows querying external endpoints in the same query. Since the website already stores `rdfs:seeAlso` with Wikipedia URLs, you can federate with Wikidata:

```sparql
SELECT ?dLabel ?birth ?nationality WHERE {
  ?d rdf:type f1:WorldChampion ; rdfs:label ?dLabel .
  SERVICE <https://query.wikidata.org/sparql> {
    ?item wdt:P31 wd:Q5 ; rdfs:label ?dLabel@en .
    OPTIONAL { ?item wdt:P569 ?birth }
    OPTIONAL { ?item wdt:P27/rdfs:label ?nationality FILTER(LANG(?nationality)="en") }
  }
}
```

This returns champions enriched with Wikidata birthdate and citizenship — zero extra data loading required.

---

### 4.2 — SPARQL Property Paths (graph traversal)

OWL `rdfs:subPropertyOf` turns `wonRace ⊑ competedIn`, enabling path queries:

```sparql
-- All circuits a champion competed at (via competedIn or wonRace)
SELECT DISTINCT ?cLabel WHERE {
  ?hamilton rdfs:label "Lewis Hamilton" .
  ?hamilton (f1:wonRace|f1:achievedPodium) ?race .
  ?race f1:heldAt ?circuit ; rdfs:label ?cLabel .
}
```

Arbitrary-length paths are possible too:
```sparql
-- Teammates of teammates of Hamilton (2 hops)
SELECT DISTINCT ?tLabel WHERE {
  ?h rdfs:label "Lewis Hamilton" .
  ?h f1:wasTeammate/f1:wasTeammate ?t .
  ?t rdfs:label ?tLabel .
  FILTER(?t != ?h)
}
```

---

### 4.3 — OWL DL Queries via Protégé / HermiT

With individual data loaded, HermiT can answer class queries that combine multiple axioms:

- *"Which individuals are both `f1:Veteran` and `f1:ConstructorChampion`?"* — class intersection
- *"Find all instances of `f1:Driver` that have no `f1:wonRace` triple"* — non-monotonic query
- *"Classify all individuals as `f1:WorldChampion` using `owl:equivalentClass`"* — bidirectional inference

The `owl:equivalentClass` axioms on `Driver/Constructor/Circuit` give HermiT **necessary and sufficient** conditions — HermiT can classify an anonymous individual with a `driverRef` property as a `Driver` without an explicit `rdf:type` assertion.

---

### 4.4 — RDFa + Microformats in Pages (Linked Data on the Web)

Every detail page in the website embeds two layers of structured data:

**RDFa 1.1 Lite** (machine-readable, Schema.org):
```html
<article vocab="https://schema.org/" typeof="Person" resource="http://...">
  <span property="name">Lewis Hamilton</span>
  <link property="sameAs" href="https://en.wikipedia.org/wiki/Lewis_Hamilton" />
</article>
```
→ Google's Knowledge Graph, search engine rich results, and semantic crawlers can extract this.

**Microformats 2** (h-card, h-event):
```html
<article class="h-card">
  <span class="p-name">Lewis Hamilton</span>
  <span class="p-country-name">British</span>
</article>
```
→ Parsed by social readers, contact importers, IndieWeb tools without any vocabulary declaration.

**Why both?** They serve different parsers and different use cases. RDFa integrates with the OWL ontology namespace. Microformats 2 requires no vocabulary and is simpler for human-readable tools. Showing both demonstrates knowledge of both standards.

---

### 4.5 — Knowledge Graph as a Recommendation Engine

Because `f1:wasTeammate` is symmetric and derived, you can build recommendations:

```sparql
-- Drivers "like" Hamilton: shared constructors, won at similar circuits
SELECT ?other ?otherLabel (COUNT(?shared) AS ?overlap) WHERE {
  ?h rdfs:label "Lewis Hamilton" ; f1:wonRace ?race .
  ?race f1:heldAt ?circuit .
  ?other f1:wonRace ?race2 .
  ?race2 f1:heldAt ?circuit .
  ?other rdfs:label ?otherLabel .
  FILTER(?other != ?h)
} GROUP BY ?other ?otherLabel
ORDER BY DESC(?overlap) LIMIT 5
```

No ML required — pure graph traversal over inferred properties.

---

### 4.6 — Semantic Web Stack in This Project

```
Raw CSV data
    │
    ▼ csv_to_rdf.py (no rdf:type for base classes)
N-Triples facts file
    │
    ├─► GraphDB (OWL-Max RDFS ruleset)
    │       rdfs:domain/range inference → rdf:type for Driver/Constructor/Circuit
    │       owl:inverseOf → hadDriver
    │       owl:SymmetricProperty → wasTeammate symmetric
    │       rdfs:subPropertyOf → wonRace ⊆ competedIn
    │
    ├─► SPIN rules (run_spin_rules management command)
    │       14 SPARQL INSERT WHERE rules
    │       WorldChampion, Veteran, HistoricCircuit, etc.
    │       Aggregation + arithmetic + negation-as-failure
    │
    ├─► Django web app (SPARQL queries over inferred graph)
    │       /drivers/, /constructors/, /circuits/, /champions/, /sparql/
    │
    ├─► RDFa 1.1 Lite on HTML pages (schema.org embedding)
    │
    ├─► Microformats 2 on HTML pages (h-card, h-event)
    │
    └─► Wikidata/DBpedia federation (SPARQLWrapper live enrichment)
```

---

## 5. Limitations and Known Issues

### OWL vs SPIN boundary
The table below documents every classification and why it falls on one side of the boundary:

| Class | Mechanism | OWL limitation |
|---|---|---|
| `Driver` | OWL `rdfs:domain` | ✅ expressible |
| `Constructor` | OWL `rdfs:domain` | ✅ expressible |
| `Circuit` | OWL `rdfs:domain` | ✅ expressible |
| `WorldChampion` | SPIN | Requires `GROUP BY + MAX` (final round detection) |
| `MultichampionDriver` | SPIN | Requires `COUNT(championships) ≥ 2` |
| `Veteran` | SPIN | Requires `COUNT(results) ≥ 100` |
| `ActiveCircuit` | SPIN | Requires `MAX(year)` across dataset |
| `HistoricCircuit` | SPIN | Requires `MAX(year) - 10` + negation-as-failure |
| `ConstructorChampion` | SPIN | Depends on `wonConstructorChampionship` — itself SPIN-derived |
| `PodiumResult` | SPIN | Requires `positionOrder ≤ 3` (arithmetic inequality) |

### Why OWL cannot handle aggregation
OWL DL is based on Description Logic, a decidable fragment of first-order logic. It has:
- **No** universal quantification over computed aggregates (`COUNT`, `SUM`, `MAX`)
- **No** arithmetic comparisons on data values (`positionOrder ≤ 3`)
- **No** negation-as-failure (`FILTER NOT EXISTS` over derived patterns)

SPIN (SPARQL Inference Notation) fills exactly this gap: each rule is a standard SPARQL 1.1
`INSERT WHERE` query that runs imperatively and materialises its conclusions as explicit triples.
