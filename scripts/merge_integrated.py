#!/usr/bin/env python3
"""
Merge facts + ontology into a single N-Triples file for Protégé / HermiT.

Streams the (large) facts file line-by-line — never loads it into RAM.
Only the small ontology file is parsed with rdflib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rdflib import Graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge RDF facts and ontology into one NT file.")
    parser.add_argument("--facts",    type=Path, default=Path("data/rdf/formula1.nt"))
    parser.add_argument("--ontology", type=Path, default=Path("data/rdf/formula1_ontology.ttl"))
    parser.add_argument("--output",   type=Path, default=Path("data/rdf/formula1_integrated.nt"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.facts.exists():
        print(f"Error: facts file not found at {args.facts}")
        return 1
    if not args.ontology.exists():
        print(f"Error: ontology file not found at {args.ontology}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Stream facts directly — one NT line at a time, no RAM accumulation.
    print(f"Streaming {args.facts} → {args.output} ...")
    fact_lines = 0
    with args.facts.open(encoding="utf-8") as fin, \
         args.output.open("w", encoding="utf-8") as fout:
        for line in fin:
            fout.write(line)
            fact_lines += 1
    print(f"  {fact_lines:,} fact triples written.")

    # Parse only the small ontology file (tens of triples — safe to load).
    print(f"Parsing ontology {args.ontology} ...")
    g = Graph()
    g.parse(str(args.ontology), format="turtle")
    print(f"  {len(g)} ontology triples.")

    # Append ontology triples as NT lines.
    with args.output.open("a", encoding="utf-8") as fout:
        for s, p, o in g:
            fout.write(f"{s.n3()} {p.n3()} {o.n3()} .\n")

    total = fact_lines + len(g)
    print(f"Done. {total:,} triples total → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
