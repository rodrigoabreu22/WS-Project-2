# Codex Execution Prompt

You are Codex working in `/home/hugod/WS-Project-2`.

Use `improvements.md` as the source backlog, but execute conservatively. The project is already running, so do not restructure the app or replace GraphDB/Django/RDF/SPARQL. Make focused changes that are easy to demo and easy to explain in the report.

## Objective

Polish the F1 Knowledge System for Web Semantics evaluation by improving:

1. setup/documentation consistency;
2. admin data-quality and inference visibility;
3. homepage professionalism;
4. a small set of strong, explainable inference use cases;
5. final documentation/report alignment.

## Execution Order

### 1. Fix Setup And Documentation Consistency

First, inspect the current repo state:

```bash
git status --short
rg -n "GRAPHDB_REPOSITORY|ws-formula1|WS-Formula1|owl-max|Django 4|Django 6|formula1_facts|formula1.nt" README.md .env.example scripts ws_project report docs
```

Then fix obvious mismatches:

- Standardize GraphDB repo naming across docs/scripts. Prefer the currently working setup unless there is a strong reason to change it.
- Keep `scripts/create_graphdb_repo.sh` using GraphDB's Turtle multipart config flow.
- Confirm `scripts/merge_integrated.py` defaults to `data/rdf/formula1.nt`.
- Treat `report/report_tp2.tex` as the current report. Do not spend time polishing old `report/report.tex` unless it is still referenced as final.
- Update `docs/implemented.md` if it still claims implemented features are missing.

Acceptance:

- README setup commands match actual scripts.
- `.env.example`, setup script, load script and docs agree on the intended GraphDB repo name.
- `venv/bin/python manage.py check` passes.

### 2. Fix Admin Data Quality

Inspect:

- `championship/admin_views.py`
- `templates/admin/data_quality.html`

Fix misleading checks:

- Replace `drivers_without_constructors` if it checks `?driver f1:constructor ?constructor`. Historical constructor links are inferred through `f1:drovFor`.
- Use clearer checks such as:
  - drivers without race entries;
  - drivers without inferred constructor history;
  - races without results;
  - results without status;
  - qualifying rows without matching race/driver/constructor;
  - circuits never used by a race;
  - missing inference dependency, e.g. zero `f1:wonRace` triples.

Improve the UI:

- Add summary counts at the top.
- Separate errors from warnings if practical.
- Add a note for checks that depend on SPIN rules having been run.

Keep this scoped. Do not build an elaborate validation framework.

### 3. Improve Homepage

Inspect:

- `championship/views.py`
- `templates/championship/home.html`
- `templates/base.html`

Redesign the homepage as a professional knowledge-graph dashboard.

Required content:

- Title: "Formula 1 Knowledge Graph" or close equivalent.
- Explain that it covers 1950-2024 results, standings, circuits and inferred achievements.
- Live GraphDB status.
- Raw counts: seasons, races, drivers, constructors, circuits.
- Inferred counts where cheap enough:
  - World champions;
  - constructor champions;
  - historic circuits;
  - podium results.
- Clear links to:
  - champions;
  - drivers;
  - circuits;
  - semantic tools;
  - admin operations or SPARQL tools.

Design constraints:

- Keep the F1 identity but reduce slogan-heavy copy.
- Avoid text overlap on mobile.
- Do not add a marketing-only landing page; make the first screen useful.
- Use existing assets only if they make the page better.
- GraphDB-down state must render cleanly.

### 4. Add Strong Inference Use Cases

Implement only the first three unless time is clearly available:

1. `f1:startedFromP1`
2. `f1:setFastestLap`
3. `f1:achievedHatTrick`

Important:

- Do not use `qualifying.csv` as the main pole source. It only covers 494 of 1125 races.
- Use `results.grid = 1` for full-dataset `startedFromP1`.
- If adding qualifying-based logic later, call it `qualifiedOnPole` and document its limited 1994-2024 coverage.

Likely files:

- `data/rdf/formula1_ontology.ttl`
- `championship/spin_rules.py`
- `championship/views.py`
- `templates/championship/driver_detail.html`
- `templates/championship/race_detail.html`
- maybe `championship/urls.py` and a new insights template if needed.

Rules:

- Add ontology terms before using them in SPIN rules.
- Keep rules idempotent with `FILTER NOT EXISTS`.
- Prefer materialised properties over hard-coded Django-only derivations.
- Use explicit count queries to validate the inferred facts.

Definitions:

- `startedFromP1`: driver has a race result for a race with `f1:grid 1`.
- `setFastestLap`: driver has a race result where `f1:rank 1`.
- `achievedHatTrick`: driver won the race, started from P1, and set fastest lap in the same race.

Expose results visibly:

- Add driver detail stats/section for P1 starts, P1-to-win conversions, fastest laps and hat tricks.
- Add race detail badges or summary rows where these facts apply.
- Optionally add a homepage insight card for top hat-trick drivers.

### 5. Improve Admin Inference Visibility

Make inference operationally visible.

Options:

- Dashboard section showing last run status using Django messages/session if persistence is not worth it.
- More complete implementation with a small Django model if useful.

Show:

- rule name;
- description;
- OK/fail;
- elapsed time;
- explicit current count for relevant inferred triples where feasible.

Do not depend on GraphDB returning inserted triple counts. Use separate count queries.

### 6. Optional Safe Delete Preview

Only do this if the previous steps are stable.

Scope:

- Driver;
- Constructor;
- Circuit.

Before delete, show:

- number of direct triples about the entity;
- number of incoming references;
- a warning if deletion would orphan or hide related records.

Do not implement cascading deletes unless explicitly requested.

### 7. Update Docs And Report Notes

Update:

- `README.md`
- `ONTOLOGY_INFERENCE.md`
- `docs/tp2_documentation.md`
- `report/report_tp2.tex` if needed

Document:

- new ontology terms;
- new SPIN rules;
- counts observed after running the rules;
- why OWL cannot express these rules alone;
- admin improvements;
- homepage/dashboard changes.

Keep report edits factual and concise.

## Verification

Run at minimum:

```bash
venv/bin/python manage.py check
venv/bin/python manage.py test
bash -n scripts/create_graphdb_repo.sh scripts/setup.sh scripts/load_rdf_to_graphdb.sh
venv/bin/python scripts/merge_integrated.py --help
```

If GraphDB is up and data is loaded, also run:

```bash
venv/bin/python manage.py run_spin_rules
```

Manual browser checks:

- `/`
- `/champions/`
- `/constructors/champions/`
- `/champions/veterans/`
- `/drivers/<known-driver-id>/`
- `/races/<known-race-id>/`
- `/tools/`
- `/sparql/`
- `/admin-panel/`
- `/admin-panel/data-quality/`
- `/admin-panel/imports/race-results/`

## Guardrails

- Do not replace GraphDB with relational tables for domain data.
- Do not silently revert user changes.
- Do not expand scope into unrelated visual redesigns.
- Do not add many weak inference rules; three strong rules are better.
- Keep generated `.nt` files gitignored.
- Keep changes explainable for a professor during a demo.
- After each implementation block, summarize what changed and what still needs verification.
