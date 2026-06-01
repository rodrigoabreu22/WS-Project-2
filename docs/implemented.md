# Implemented System Summary

This file summarizes the current implemented state of the F1 Knowledge System.

## Core architecture

- Django 6 application with server-rendered templates and vanilla JavaScript.
- GraphDB is the source of truth for domain data; SQLite is used only for Django authentication/session/admin metadata.
- RDF facts are generated from the Kaggle/Ergast Formula 1 CSV schema.
- GraphDB repository uses the `owl-max-optimized` ruleset so `rdfs:domain`, `owl:inverseOf`, `owl:SymmetricProperty`, and subclass inference are materialised at load time.
- Default repository name across scripts and docs is `ws-formula1-owlmax`.

## Data pipeline

- Raw CSV files live in `data/raw/`.
- `scripts/csv_to_rdf.py` converts the dataset to N-Triples at `data/rdf/formula1.nt`.
- `scripts/merge_integrated.py` merges generated facts with `data/rdf/formula1_ontology.ttl` into `data/rdf/formula1_integrated.nt`.
- `scripts/create_graphdb_repo.sh` creates the GraphDB repository through the supported Turtle multipart REST API.
- `scripts/load_rdf_to_graphdb.sh` uses GraphDB server-side import for reliable inference during ingestion.
- `scripts/setup.sh` automates environment setup, RDF generation, repository creation, import, inference, and Django setup.

## Semantic layer

- Hand-authored OWL/RDFS ontology in `data/rdf/formula1_ontology.ttl`.
- Base Driver/Constructor/Circuit types are inferred from unique reference properties rather than asserted in the facts file.
- SPIN-style SPARQL UPDATE rules in `championship/spin_rules.py` materialise derived facts and classifications.
- Existing inferred concepts include world champions, multi-champions, veterans, constructor champions, active/historic circuits, podium results, race wins, teammate links, championship wins, constructor championship wins, and reified championship statements.
- RDF reification annotates championship-winning triples with final points.

## Public UI

- Home dashboard backed by live GraphDB counts.
- List/detail pages for drivers, constructors, circuits, races, and seasons.
- Inference-driven pages for champions, multi-champions, veterans, and constructor champions.
- Semantic tools page with reification viewer, Microformats parsing, and RDFa validation links.
- SPARQL explorer for SELECT queries.
- LLM assistant that translates natural-language questions to safe read-only SPARQL queries.
- Detail pages include RDFa 1.1 Lite, Microformats 2, and asynchronous Wikidata/DBpedia enrichment.

## Admin UI

- Staff-only admin panel.
- CRUD for drivers, constructors, circuits, races, and seasons through SPARQL UPDATE.
- Race-results CSV import with dry-run preview, validation, confirmation, and rollback.
- Data-quality checks over the RDF graph.
- Admin action to run SPIN inference rules.

## Verification

Recommended checks:

```bash
venv/bin/python manage.py check
venv/bin/python manage.py test
bash -n scripts/create_graphdb_repo.sh scripts/setup.sh scripts/load_rdf_to_graphdb.sh
venv/bin/python scripts/merge_integrated.py --help
```

With GraphDB running and the integrated RDF loaded:

```bash
venv/bin/python manage.py run_spin_rules
```
