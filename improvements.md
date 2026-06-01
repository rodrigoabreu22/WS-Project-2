# Improvements Prompt

You are Codex working in `/home/hugod/WS-Project-2`.

Goal: improve the F1 Knowledge System for Web Semantics evaluation without changing the core architecture. Keep the project Django + GraphDB + RDF/SPARQL based. Prefer small, demonstrable improvements that make the semantic layer, UI and admin use cases stronger.

## Current Context

- Public app already has RDF-backed pages for drivers, constructors, circuits, races, seasons, champions, multi-champions, veterans, constructor champions, semantic tools and an LLM assistant.
- Graph data is generated from Kaggle/Ergast-style CSV files into `data/rdf/formula1.nt`, then merged with `data/rdf/formula1_ontology.ttl` into `data/rdf/formula1_integrated.nt`.
- GraphDB runs OWL-Max/RDFS inference. Custom SPIN-like SPARQL UPDATE rules are in `championship/spin_rules.py`.
- Existing inferred concepts include:
  - `f1:WorldChampion`
  - `f1:MultichampionDriver`
  - `f1:Veteran`
  - `f1:ConstructorChampion`
  - `f1:ActiveCircuit`
  - `f1:HistoricCircuit`
  - `f1:PodiumResult`
  - `f1:wonRace`
  - `f1:achievedPodium`
  - `f1:drovFor`
  - `f1:hadDriver`
  - `f1:wasTeammate`
  - `f1:wonChampionship`
  - `f1:wonConstructorChampionship`
  - `f1:heldAt`
- Existing semantic extras include RDF reification, RDFa, Microformats 2, Wikidata, DBpedia and SPARQLWrapper usage.
- The TP1 statement requires Kaggle dataset, RDF, GraphDB, SPARQL query/update, Django, UI and easy setup. The current repo mostly satisfies this and goes beyond it, but some use cases and polish can still be improved.

## Priority 0 - Quick Correctness Fixes

Do these before bigger UI work.

1. Check stale documentation and naming mismatches.
   - `requirements.txt` uses Django 6.0.3 and `report/report_tp2.tex` says Django 6. Treat `report/report_tp2.tex` as the current report and either update or ignore the older `report/report.tex` references to Django 4.x.
   - README architecture says Ergast CSV, while the assignment says Kaggle. Use wording like "Kaggle Formula 1 dataset, derived from Ergast schema" if accurate.
   - Confirm `scripts/merge_integrated.py` defaults to `data/rdf/formula1.nt`; it should not point to `formula1_facts.nt`.
   - Standardize the GraphDB repository name across `.env.example`, README, setup scripts and report. Current scripts default to `ws-formula1-owlmax`, while local `.env` may use `WS-Formula1`; pick one name and make all docs/scripts match it.
   - Update `docs/implemented.md`, because it still describes an old baseline and says several features are not implemented.

2. Check admin data-quality queries.
   - `drivers_without_constructors` currently checks `?driver f1:constructor ?constructor`, but normal historical driver-team links are inferred as `f1:drovFor`.
   - Replace or rename this check. Better options:
     - "Drivers without race entries": no `f1:Result` points to them.
     - "Drivers without inferred constructor history": no `f1:drovFor` after inference.
   - Add a note in the UI when a check depends on SPIN rules having been run.

3. Make inference runs more visible.
   - Admin currently redirects after "Run Inference" with only a message.
   - Store/display per-rule results: rule name, OK/fail, elapsed time.
   - Surface "last inference run" timestamp and failures on the admin dashboard.
   - Candidate files: `championship/admin_views.py`, `templates/admin/dashboard.html`, maybe `championship/models.py` if persistence is needed.
   - For "triples affected", do not rely on GraphDB returning inserted counts. Define explicit count queries per rule, e.g. count existing `f1:wonRace`, `f1:PodiumResult`, `f1:WorldChampion`, etc.

Acceptance:

- `python manage.py check` passes.
- Admin dashboard still loads.
- The README setup path is consistent with real scripts and generated files.

## Priority 1 - Add 2 or 3 Strong Inference Use Cases

Do not add many weak rules. Add a small number that can be shown clearly in the UI and report.

### Candidate A - Started From P1 / Converted P1

Semantic value: combines qualifying data and race result data.

Important data caveat:

- `qualifying.csv` only covers 494 of 1125 races, mostly 1994-2024.
- `results.grid = 1` covers the full race-result dataset and is safer for historical analysis.
- Use `startedFromP1` as the main full-dataset inference. If an explicit qualifying-based concept is added later, call it `qualifiedOnPole` and document the limited coverage.

Possible model:

- New object property: `f1:startedFromP1` from Driver to Race.
- New object property: `f1:convertedP1ToWin` from Driver to Race.
- Optional class: `f1:P1Winner`.

SPIN rules:

- Infer `?driver f1:startedFromP1 ?race` where a race result has `f1:grid 1`.
- Infer `?driver f1:convertedP1ToWin ?race` where same driver started from P1 and has `f1:wonRace ?race`.

UI use case:

- Add a small "P1 conversions" section on driver detail.
- Add a public page or table showing best P1-to-win conversion counts.

Why it helps:

- Demonstrates derived race-context inference across result rows.
- Stronger than simple count queries because the semantic relation is materialised.

### Candidate B - Fastest Lap Winners

Semantic value: derives a race-level performance achievement from result rank.

Possible model:

- New object property: `f1:setFastestLap` from Driver to Race.
- Optional class: `f1:FastestLapResult`.

SPIN rule:

- Infer fastest lap where `f1:rank 1` in `Result`.

UI use case:

- Add fastest-lap count to driver detail and race detail.
- Add badge on race result rows when the row is fastest lap.

Why it helps:

- Easy to verify with existing `results.csv` columns.
- Complements wins/podiums with another F1-specific achievement.

### Candidate C - Hat Trick / Dominant Result

Semantic value: combines multiple inferred relations.

Possible model:

- New object property: `f1:achievedHatTrick` from Driver to Race.
- Optional class: `f1:HatTrickResult`.

Definition:

- Driver won the race.
- Driver started from P1.
- Driver set fastest lap.

SPIN rule:

- Use inferred `f1:wonRace`, `f1:startedFromP1` and `f1:setFastestLap` to infer `f1:achievedHatTrick`.

UI use case:

- Driver detail "Signature achievements" block.
- New insights card on homepage: top hat-trick drivers.

Why it helps:

- Very good demo of layered inference: raw data -> simple inferred facts -> composite inferred fact.

### Candidate D - Comeback Win

Semantic value: interprets race result context.

Possible model:

- New object property: `f1:wonFromOutsideTopFive` from Driver to Race.
- Optional class: `f1:ComebackWinResult`.

Definition:

- Driver won race and `grid > 5`.

UI use case:

- Race detail badge for comeback wins.
- Public "Great comeback wins" mini page.

Why it helps:

- Uses arithmetic filter and race context, clearly not OWL-expressible.

Recommended choice:

Implement A, B and C first. They form a clean story:

1. Started from P1 from race result grid data.
2. Fastest lap from results.
3. Hat trick from P1 start + win + fastest lap.

Files likely touched:

- `data/rdf/formula1_ontology.ttl`
- `championship/spin_rules.py`
- `championship/views.py`
- `championship/urls.py`
- `templates/championship/driver_detail.html`
- `templates/championship/race_detail.html`
- optionally a new `templates/championship/insights.html`
- `README.md`
- `ONTOLOGY_INFERENCE.md`

Acceptance:

- `python manage.py run_spin_rules` runs all old and new rules idempotently.
- New inferred triples have counts in `ONTOLOGY_INFERENCE.md`.
- At least one public page visibly uses the new inferred facts.
- The report can explain why OWL alone cannot infer these facts.

## Priority 2 - Make Homepage More Professional

Current homepage works but feels more like a project landing page than a polished data product. Improve it as an executive dashboard for the knowledge graph.

Design direction:

- Keep F1 visual identity but reduce slogan-heavy copy.
- Use real project value as first signal: "Formula 1 Knowledge Graph".
- Make the first viewport show:
  - live graph stats;
  - GraphDB status;
  - quick links to important use cases;
  - one inferred insight, not only raw counts.
- Use existing visual assets from `static/drivers`, `static/constructors`, `static/circuits` or add a restrained image strip. Avoid a generic marketing hero.

Proposed structure:

1. Hero band
   - Title: "Formula 1 Knowledge Graph"
   - Subtitle: "1950-2024 results, standings, circuits and inferred achievements in GraphDB."
   - Primary CTA: "Explore Champions"
   - Secondary CTA: "Open SPARQL Tools"
   - Status chip: GraphDB connected/unavailable.

2. Insight bar
   - Seasons, races, drivers, constructors, circuits.
   - Add inferred counts if cheap enough:
     - World champions
     - Constructor champions
     - Historic circuits
     - Podium results

3. Use-case blocks
   - "Inferred Champions"
   - "Driver Careers"
   - "Circuit History"
   - "Admin Knowledge Operations"
   - "Semantic Tools"

4. Semantic proof section
   - Short, visual explanation:
     - CSV -> RDF -> OWL/RDFS -> SPIN -> UI
   - Link to `/tools/` and `/sparql/`.

Files likely touched:

- `championship/views.py` for extra homepage aggregate queries.
- `templates/championship/home.html`.
- possibly `static/` if adding a new homepage asset.

Acceptance:

- Homepage looks credible on desktop and mobile.
- No overlapping text.
- GraphDB-down state still renders cleanly.
- It demonstrates inferred knowledge, not just raw dataset navigation.

## Priority 3 - Admin Use Cases Worth Showing

The admin panel already has CRUD, import, rollback, data quality and inference trigger. Improve it by making semantic operations explicit.

### Admin Use Case 1 - Inference Control Center

Add an admin page or dashboard section that shows:

- list of SPIN rules;
- description of each rule;
- last run status;
- elapsed time;
- inferred triple count per rule where feasible, computed with explicit count queries;
- button to run all rules;
- optional button to run one selected rule.

Acceptance:

- A professor can see exactly how inference is operationalized.
- Failures are visible and actionable.

### Admin Use Case 2 - Safe Delete / Impact Preview

Before deleting a driver, constructor or circuit, show dependent triples:

- number of direct triples about the entity;
- number of incoming links from results/standings/races;
- warning if deletion will orphan data.

Implementation:

- Add preview query before delete confirmation.
- For now, avoid cascading deletes unless intentionally implemented.
- Keep Season/Race delete impact preview as future work; those entities touch too many related tables for a quick safe implementation.

Acceptance:

- Admin demonstrates SPARQL analysis before SPARQL UPDATE.
- This is a better "management system" use case than blind delete.

### Admin Use Case 3 - Data Quality Summary Dashboard

Improve `/admin-panel/data-quality/`:

- show counts at top for each check;
- separate errors vs warnings;
- fix or rename misleading checks;
- add checks for:
  - races without results;
  - results without status;
  - qualifying rows without matching race/driver/constructor;
  - circuits never used by a race;
  - inferred rule dependency missing, e.g. no `f1:wonRace` triples after load.

Acceptance:

- Data quality page is useful even during demo.
- Empty checks are compact and reassuring.

### Admin Use Case 4 - Import Aftercare

After race results import:

- show exactly which derived facts should be regenerated;
- provide "Run inference now" CTA;
- show latest batch metadata and rollback link.

Acceptance:

- Import flow demonstrates write operations plus inference lifecycle.

## Priority 4 - Check Assignment / Theory Coverage

Audit against the statement and class topics. Mark each item as "done", "needs polish", or "missing".

### Statement Coverage

- Kaggle dataset with multiple entities and relations: done.
- Conversion to RDF: done.
- RDF file for GraphDB import: done, but keep generated `.nt` out of git if too large; document how to regenerate.
- Python/Django app: done.
- GraphDB triplestore: done.
- SPARQL SELECT and UPDATE: done.
- UI for display and management: done, admin can be strengthened.
- Easy setup with `requirements.txt`: mostly done; verify README commands.
- No Docker requirement: OK.
- Report structure in required order: verify final report has:
  1. Introduction
  2. Data, sources and transformation
  3. Operations over data with SPARQL
  4. Application functionalities
  5. Conclusions
  6. Configuration

### Theory Topics To Demonstrate

- RDF/N-Triples: done.
- RDFS/OWL vocabulary and inference: done.
- Domain/range inference: done.
- `owl:inverseOf`, `owl:SymmetricProperty`, `rdfs:subPropertyOf`: done.
- SPARQL SELECT with aggregation/filter/order: done.
- SPARQL UPDATE: done.
- SPIN / rule-based inference: done; can be made more visible.
- RDF reification: done; verify `/tools/` clearly shows it.
- RDFa: done on detail pages; verify validators/links.
- Microformats 2: done; verify parser still works.
- Linked Data / external endpoints: done via Wikidata/DBpedia.
- SPARQLWrapper: done.
- Federated SPARQL or external enrichment: done; make sure report includes screenshots/examples.

Likely missing or weak:

- Tests for rule counts or query contracts.
- Admin semantic operations are present but not strongly explained in UI.
- Homepage does not yet communicate semantic value as professionally as the rest of the app.
- Documentation has stale baseline files and version inconsistencies.

## Suggested Execution Order

1. Documentation, GraphDB repository naming and quick correctness fixes.
2. Fix/rename misleading admin data-quality checks.
3. Redesign homepage so it presents the semantic value clearly.
4. Add `startedFromP1`, `setFastestLap`, and `achievedHatTrick` inference rules and ontology terms.
5. Expose the new inferred facts in one or two public pages.
6. Improve admin inference visibility with per-rule status and explicit count queries.
7. Add safe-delete impact preview for Driver/Constructor/Circuit only if time remains.
8. Update README, report notes and `ONTOLOGY_INFERENCE.md`.
9. Run verification.

## Verification Commands

Use these after changes:

```bash
venv/bin/python manage.py check
venv/bin/python manage.py test
venv/bin/python manage.py run_spin_rules
venv/bin/python scripts/merge_integrated.py --help
```

If GraphDB is running and loaded, also check these manually:

- `/`
- `/champions/`
- `/constructors/champions/`
- `/champions/veterans/`
- `/tools/`
- `/sparql/`
- `/admin-panel/`
- `/admin-panel/data-quality/`
- `/admin-panel/imports/race-results/`

## Guardrails

- Do not replace GraphDB with relational database logic.
- Do not hard-code derived facts in Django if they should be inferred in SPARQL.
- Keep inference rules idempotent with `FILTER NOT EXISTS`.
- Add ontology terms before using them in SPIN rules.
- Keep UI changes scoped and responsive.
- Update the report/docs whenever adding a semantic feature, because the evaluation depends heavily on explanation.
