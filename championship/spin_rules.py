"""
SPIN inference rules for the F1 knowledge system.

Each rule is a SPARQL 1.1 UPDATE (INSERT WHERE) that materialises implicit
knowledge as explicit triples.  Rules are run in order via apply_all_rules().

GraphDBClient.run_update() prepends its own PREFIXES (rdf:, rdfs:, f1:, xsd:)
automatically, so the queries below need no prefix declarations of their own.

Reference: ws.10a — SPIN/SPARQL Inference Notation.
"""

from __future__ import annotations

import time

# Rules are ordered: derived facts before derived classifications.
SPIN_RULES: list[dict] = [
    {
        "name": "infer_wonRace",
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
  ?season f1:year ?yr .
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
