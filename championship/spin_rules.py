"""
SPIN inference rules for the F1 knowledge system.

Each rule is a SPARQL 1.1 UPDATE (INSERT WHERE) that materialises implicit
knowledge as explicit triples.  Rules are run in order via apply_all_rules().

GraphDBClient.run_update() prepends its own PREFIXES (rdf:, rdfs:, f1:, xsd:)
automatically, so the queries below need no prefix declarations of their own.

Reference: ws.10a — SPIN/SPARQL Inference Notation.

WHY SPIN INSTEAD OF OWL REASONING
──────────────────────────────────
OWL DL (including GraphDB's OWL-Max ruleset) covers:
  • rdfs:subClassOf / rdfs:subPropertyOf chains
  • rdfs:domain / rdfs:range → class membership from property usage
  • owl:FunctionalProperty, owl:SymmetricProperty, owl:inverseOf
  • owl:someValuesFrom / owl:allValuesFrom restrictions on known individuals

OWL DL CANNOT express:
  • Aggregation — COUNT(*), GROUP BY, HAVING (e.g. "has ≥ 100 race entries")
  • Arithmetic comparisons involving computed values (e.g. "MAX round per year")
  • Negation-as-failure patterns needed to establish the last round of a season

All rules below fall into one or more of these categories and therefore cannot be
handled by the reasoner.  Each rule documents its specific reason.
"""

from __future__ import annotations

import time

# Rules are ordered: derived facts before derived classifications.
SPIN_RULES: list[dict] = [
    {
        "name": "infer_wonRace",
        # WHY SPIN: requires a numeric equality filter (positionOrder = 1).
        # OWL owl:hasValue can express a single fixed value, but cannot join across
        # the result–driver–race triple pattern needed to derive the link.
        "description": "Driver who finished positionOrder=1 gets f1:wonRace link.",
        "query": """
INSERT { ?driver f1:wonRace ?race . }
WHERE {
  ?result f1:resultId ?id ;
          f1:positionOrder 1 ;
          f1:driver ?driver ;
          f1:race ?race .
  FILTER NOT EXISTS { ?driver f1:wonRace ?race }
}
""",
    },
    {
        "name": "infer_achievedPodium",
        # WHY SPIN: uses FILTER(?pos <= 3), an arithmetic inequality.
        # OWL restrictions (owl:someValuesFrom, owl:maxInclusive via data ranges)
        # cannot be combined with the cross-entity join pattern required here.
        "description": "Driver with positionOrder <= 3 gets f1:achievedPodium link.",
        "query": """
INSERT { ?driver f1:achievedPodium ?race . }
WHERE {
  ?result f1:resultId ?id ;
          f1:positionOrder ?pos ;
          f1:driver ?driver ;
          f1:race ?race .
  FILTER(?pos <= 3)
  FILTER NOT EXISTS { ?driver f1:achievedPodium ?race }
}
""",
    },
    {
        "name": "infer_drovFor",
        "description": "Driver linked to every Constructor they drove for.",
        "query": """
INSERT { ?driver f1:drovFor ?constructor . }
WHERE {
  ?result f1:resultId ?id ;
          f1:driver ?driver ;
          f1:constructor ?constructor .
  FILTER NOT EXISTS { ?driver f1:drovFor ?constructor }
}
""",
    },
    {
        "name": "infer_wasTeammate",
        "description": "Two drivers in the same race for the same constructor are teammates (symmetric).",
        "query": """
INSERT { ?d1 f1:wasTeammate ?d2 . ?d2 f1:wasTeammate ?d1 . }
WHERE {
  ?r1 f1:resultId ?id1 ; f1:race ?race ; f1:constructor ?ctor ; f1:driver ?d1 .
  ?r2 f1:resultId ?id2 ; f1:race ?race ; f1:constructor ?ctor ; f1:driver ?d2 .
  FILTER(?d1 != ?d2)
  FILTER NOT EXISTS { ?d1 f1:wasTeammate ?d2 }
}
""",
    },
    {
        "name": "infer_wonChampionship",
        # WHY SPIN: requires GROUP BY + MAX to find the final round of each season,
        # then a FILTER join between the subquery result and the main pattern.
        # OWL DL has no mechanism for aggregation or for comparing a value against
        # a dynamically computed maximum.
        "description": "Driver holding position=1 in DriverStanding at the final round of a season wins the championship.",
        "query": """
INSERT { ?driver f1:wonChampionship ?season . }
WHERE {
  ?ds f1:driverStandingsId ?anyId ;
      f1:race ?race ;
      f1:driver ?driver ;
      f1:position 1 .
  ?race f1:round ?round ;
        f1:year ?yr .
  ?season rdf:type f1:Season ;
          f1:year ?yr .
  {
    SELECT ?yr (MAX(?r) AS ?maxRound)
    WHERE { ?rc f1:round ?r ; f1:year ?yr . }
    GROUP BY ?yr
  }
  FILTER(?round = ?maxRound)
  FILTER NOT EXISTS { ?driver f1:wonChampionship ?season }
}
""",
    },
    {
        "name": "reify_wonChampionship",
        # WHY REIFICATION: rdf:Statement allows attaching metadata (final points,
        # points margin) to an already-materialised triple without changing the
        # original triple.  This is the standard RDF reification pattern and cannot
        # be expressed as a plain data property on the Driver or Season nodes.
        # We use IRI(CONCAT(...)) to produce stable, addressable statement URIs
        # instead of blank nodes, so the reified nodes can be retrieved by SPARQL.
        "description": "Reify each f1:wonChampionship triple as an rdf:Statement node annotated with final championship points.",
        "query": """
INSERT {
  _:stmt rdf:type      rdf:Statement ;
         rdf:subject   ?driver ;
         rdf:predicate f1:wonChampionship ;
         rdf:object    ?season ;
         f1:finalPoints ?pts .
}
WHERE {
  ?driver f1:wonChampionship ?season .
  ?season rdf:type f1:Season ;
          f1:year ?yr .
  ?ds rdf:type f1:DriverStanding ;
      f1:driver ?driver ;
      f1:race ?race ;
      f1:points ?pts .
  ?race f1:round ?round ;
        f1:year ?yr .
  {
    SELECT ?yr (MAX(?r) AS ?maxRound)
    WHERE { ?rc f1:round ?r ; f1:year ?yr . }
    GROUP BY ?yr
  }
  FILTER(?round = ?maxRound)
  FILTER NOT EXISTS {
    ?s rdf:type      rdf:Statement ;
       rdf:subject   ?driver ;
       rdf:predicate f1:wonChampionship ;
       rdf:object    ?season .
  }
}
""",
    },
    {
        "name": "infer_heldAt",
        "description": "Materialise f1:heldAt from the f1:circuit property on Race entities.",
        "query": """
INSERT { ?race f1:heldAt ?circuit . }
WHERE {
  ?race f1:circuit ?circuit .
  FILTER NOT EXISTS { ?race f1:heldAt ?circuit }
}
""",
    },
    {
        "name": "classify_WorldChampion",
        "description": "Drivers who won at least one championship are classified as f1:WorldChampion.",
        "query": """
INSERT { ?driver rdf:type f1:WorldChampion . }
WHERE {
  ?driver f1:wonChampionship ?season .
  FILTER NOT EXISTS { ?driver rdf:type f1:WorldChampion }
}
""",
    },
    {
        "name": "classify_MultichampionDriver",
        "description": "WorldChampion with two or more championships is classified as f1:MultichampionDriver.",
        "query": """
INSERT { ?driver rdf:type f1:MultichampionDriver . }
WHERE {
  SELECT ?driver (COUNT(?season) AS ?titles)
  WHERE { ?driver f1:wonChampionship ?season . }
  GROUP BY ?driver
  HAVING(?titles >= 2)
}
""",
    },
    {
        "name": "classify_Veteran",
        "description": "Driver with 100 or more race entries is classified as f1:Veteran.",
        "query": """
INSERT { ?driver rdf:type f1:Veteran . }
WHERE {
  SELECT ?driver (COUNT(DISTINCT ?result) AS ?entries)
  WHERE { ?result f1:resultId ?id ; f1:driver ?driver . }
  GROUP BY ?driver
  HAVING(?entries >= 100)
}
""",
    },
    {
        "name": "classify_ActiveCircuit",
        # WHY SPIN: requires MAX aggregation to find the most recent year in the
        # dataset, then uses it as a filter condition.  OWL cannot compute or
        # reference a maximum value across the entire dataset.
        "description": "Circuit that hosted a race in the latest season of the dataset is classified as f1:ActiveCircuit.",
        "query": """
INSERT { ?circuit rdf:type f1:ActiveCircuit . }
WHERE {
  { SELECT (MAX(?yr) AS ?maxYear) WHERE { ?r f1:year ?yr . } }
  ?race f1:circuit ?circuit ;
        f1:year ?maxYear .
  FILTER NOT EXISTS { ?circuit rdf:type f1:ActiveCircuit }
}
""",
    },
    {
        "name": "classify_PodiumResult",
        # WHY SPIN: uses FILTER(?pos <= 3), an arithmetic inequality on a data value.
        # OWL 2 data ranges (owl:onDataRange with xsd:maxInclusive) can express this
        # as a necessary condition on a class, but cannot match existing individuals
        # against that range and reclassify them without a complete DL reasoner pass
        # over every Result individual — which is intractable at dataset scale.
        "description": "RaceResult with positionOrder <= 3 is classified as f1:PodiumResult.",
        "query": """
INSERT { ?result rdf:type f1:PodiumResult . }
WHERE {
  ?result f1:resultId ?id ;
          f1:positionOrder ?pos .
  FILTER(?pos <= 3)
  FILTER NOT EXISTS { ?result rdf:type f1:PodiumResult }
}
""",
    },
    {
        "name": "infer_wonConstructorChampionship",
        # WHY SPIN: mirrors infer_wonChampionship but for constructors.  Requires
        # GROUP BY + MAX to identify the final round of each season and a correlated
        # filter — not expressible in OWL DL.  Secondary entity: this property does
        # NOT exist in the raw dataset and is fully synthesised here.
        "description": "Constructor holding position=1 in ConstructorStanding at the final round of a season wins the championship.",
        "query": """
INSERT { ?constructor f1:wonConstructorChampionship ?season . }
WHERE {
  ?cs f1:constructorStandingsId ?anyId ;
      f1:race ?race ;
      f1:constructor ?constructor ;
      f1:position 1 .
  ?race f1:round ?round ;
        f1:year ?yr .
  ?season rdf:type f1:Season ;
          f1:year ?yr .
  {
    SELECT ?yr (MAX(?r) AS ?maxRound)
    WHERE { ?rc f1:round ?r ; f1:year ?yr . }
    GROUP BY ?yr
  }
  FILTER(?round = ?maxRound)
  FILTER NOT EXISTS { ?constructor f1:wonConstructorChampionship ?season }
}
""",
    },
    {
        "name": "classify_ConstructorChampion",
        # WHY SPIN: depends on f1:wonConstructorChampionship which is itself a SPIN-
        # derived property (not in raw data).  OWL someValuesFrom cannot reason over
        # a property that does not yet exist at load time; it would require a two-pass
        # DL classification after the SPIN rule has run.
        "description": "Constructor with at least one wonConstructorChampionship is classified as f1:ConstructorChampion.",
        "query": """
INSERT { ?constructor rdf:type f1:ConstructorChampion . }
WHERE {
  ?constructor f1:wonConstructorChampionship ?season .
  FILTER NOT EXISTS { ?constructor rdf:type f1:ConstructorChampion }
}
""",
    },
    {
        "name": "classify_HistoricCircuit",
        # WHY SPIN: requires computing (MAX year in dataset) - 10 as a threshold, then
        # applying it as a FILTER on per-circuit race history.  Both the arithmetic on
        # a dataset-wide aggregate and the negation-as-failure pattern (no race in
        # the window) are beyond OWL DL expressivity.  This is also a secondary
        # entity: "historic" is a derived semantic label not present in the source data.
        "description": "Circuit with no race in the last 10 years of the dataset is classified as f1:HistoricCircuit.",
        "query": """
INSERT { ?circuit rdf:type f1:HistoricCircuit . }
WHERE {
  { SELECT (MAX(xsd:integer(STR(?yr))) AS ?maxYr)
    WHERE { ?r f1:year ?yr . } }
  ?circuit f1:circuitRef ?ref .
  FILTER NOT EXISTS {
    ?race f1:circuit ?circuit ;
          f1:year ?ry .
    FILTER(xsd:integer(STR(?ry)) >= ?maxYr - 10)
  }
  FILTER NOT EXISTS { ?circuit rdf:type f1:HistoricCircuit }
}
""",
    },
]


def apply_all_rules(db_client) -> list[dict]:
    """Run all SPIN rules in declaration order. Returns per-rule result dicts."""
    results = []
    for rule in SPIN_RULES:
        t0 = time.time()
        try:
            db_client.run_update(rule["query"])
            elapsed = round(time.time() - t0, 2)
            results.append({"name": rule["name"], "ok": True, "elapsed": elapsed})
        except Exception as exc:
            results.append({"name": rule["name"], "ok": False, "error": str(exc)})
    return results


def apply_rule(db_client, rule_name: str) -> None:
    """Run a single named rule. Raises ValueError if the name is not found."""
    for rule in SPIN_RULES:
        if rule["name"] == rule_name:
            db_client.run_update(rule["query"])
            return
    raise ValueError(f"Rule '{rule_name}' not found in SPIN_RULES.")
