"""
External semantic enrichment via Wikidata and DBpedia.

Functions return a plain dict of enrichment fields, or {} on any failure.
Results are cached in-process to avoid repeated remote calls per page load.

Reference: ws.10b — accessing Wikidata and DBpedia via SPARQLWrapper.
"""

from __future__ import annotations

import json
import urllib.request

from SPARQLWrapper import SPARQLWrapper2

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
DBPEDIA_ENDPOINT  = "https://dbpedia.org/sparql"
_TIMEOUT    = 12  # seconds
_USER_AGENT = "ws-f1-project/1.0 (academic; contact: rodrigo@example.org)"
_WIKI_PATH  = "/wiki/"

_cache: dict[str, object] = {}


# ── Wikipedia ─────────────────────────────────────────────────────────────────

def get_wikipedia_summary(wiki_url: str) -> dict:
    """Return {image, description, extract} from the Wikipedia REST summary API."""
    if not wiki_url or _WIKI_PATH not in wiki_url:
        return {}
    cache_key = f"wp:summary:{wiki_url}"
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        title   = wiki_url.rstrip("/").split(_WIKI_PATH)[-1]
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        req     = urllib.request.Request(api_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        result = {
            "image":       data.get("thumbnail", {}).get("source", ""),
            "description": data.get("description", ""),
            "extract":     data.get("extract", "")[:500],
        }
        _cache[cache_key] = result
        return result
    except Exception:
        _cache[cache_key] = {}
        return {}


def get_wikipedia_image(wiki_url: str) -> str:
    """Return a thumbnail URL from any Wikipedia article URL."""
    return get_wikipedia_summary(wiki_url).get("image", "")


# ── Wikidata — Drivers ────────────────────────────────────────────────────────

def get_driver_wikidata(driver_name: str) -> dict:
    """
    Return Wikidata enrichment for an F1 driver.

    New fields vs. original:
      deathDate  (P570)  — date of death, shown as † on detail pages
      height     (P2048) — height in cm
      fatherName (P22)   — father's name (e.g. Damon Hill → Graham Hill)
      childNames (P40)   — list of children's names (F1 dynasties)
    """
    cache_key = f"wd:driver:{driver_name}"
    if cache_key in _cache:
        return _cache[cache_key]

    sparql = SPARQLWrapper2(WIKIDATA_ENDPOINT)
    sparql.setTimeout(_TIMEOUT)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(f"""
        PREFIX wd:     <http://www.wikidata.org/entity/>
        PREFIX wdt:    <http://www.wikidata.org/prop/direct/>
        PREFIX schema: <https://schema.org/>
        SELECT ?item ?birthPlaceLabel ?description ?image
               ?deathDate ?height ?fatherLabel
               (GROUP_CONCAT(DISTINCT ?childLabel; separator="|") AS ?childNames)
        WHERE {{
          ?item wdt:P106 wd:Q10843402 ;
                rdfs:label ?label .
          OPTIONAL {{ ?item wdt:P19  ?birthPlace }}
          OPTIONAL {{ ?item wdt:P18  ?image }}
          OPTIONAL {{ ?item wdt:P570 ?deathDate }}
          OPTIONAL {{ ?item wdt:P2048 ?height }}
          OPTIONAL {{ ?item wdt:P22  ?father .
                      ?father rdfs:label ?fatherLabel .
                      FILTER(LANG(?fatherLabel) = "en") }}
          OPTIONAL {{ ?item wdt:P40  ?child .
                      ?child  rdfs:label ?childLabel .
                      FILTER(LANG(?childLabel) = "en") }}
          OPTIONAL {{
            ?item schema:description ?description .
            FILTER(LANG(?description) = "en")
          }}
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
          }}
          FILTER(LANG(?label) = "en")
          FILTER(LCASE(STR(?label)) = "{driver_name.lower()}")
        }}
        GROUP BY ?item ?birthPlaceLabel ?description ?image
                 ?deathDate ?height ?fatherLabel
        LIMIT 1
    """)
    try:
        results = sparql.query().bindings
        if not results:
            _cache[cache_key] = {}
            return {}
        r = results[0]
        death_raw = r["deathDate"].value if "deathDate" in r else ""
        height_raw = r["height"].value if "height" in r else ""
        data = {
            "birthPlace":   r["birthPlaceLabel"].value if "birthPlaceLabel" in r else "",
            "description":  r["description"].value     if "description"     in r else "",
            "image":        r["image"].value            if "image"           in r else "",
            "wikidata_uri": r["item"].value             if "item"            in r else "",
            "deathDate":    death_raw[:10]              if death_raw         else "",
            "height":       height_raw.split("^")[0]   if height_raw        else "",
            "fatherName":   r["fatherLabel"].value      if "fatherLabel"     in r else "",
            "childNames":   r["childNames"].value       if "childNames"      in r else "",
        }
        _cache[cache_key] = data
        return data
    except Exception:
        _cache[cache_key] = {}
        return {}


# ── Wikidata — Constructors ───────────────────────────────────────────────────

def get_constructor_wikidata(constructor_name: str) -> dict:
    """
    Return Wikidata enrichment for an F1 constructor.

    New fields vs. original:
      logo        (P154) — team logo image URL
      website     (P856) — official website
      country     (P17)  — country of origin
      founder     (P112) — who founded the team
      dissolved   (P576) — date when team was dissolved (if applicable)
    """
    cache_key = f"wd:constructor:{constructor_name}"
    if cache_key in _cache:
        return _cache[cache_key]

    sparql = SPARQLWrapper2(WIKIDATA_ENDPOINT)
    sparql.setTimeout(_TIMEOUT)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(f"""
        PREFIX wd:  <http://www.wikidata.org/entity/>
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        SELECT ?item ?foundingDate ?hqLabel ?logo ?website
               ?countryLabel ?founderLabel ?dissolved WHERE {{
          ?item wdt:P31 wd:Q41298738 ;
                rdfs:label ?label .
          OPTIONAL {{ ?item wdt:P571 ?foundingDate }}
          OPTIONAL {{ ?item wdt:P159 ?hq }}
          OPTIONAL {{ ?item wdt:P154 ?logo }}
          OPTIONAL {{ ?item wdt:P856 ?website }}
          OPTIONAL {{ ?item wdt:P17  ?country }}
          OPTIONAL {{ ?item wdt:P112 ?founder }}
          OPTIONAL {{ ?item wdt:P576 ?dissolved }}
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
          }}
          FILTER(LANG(?label) = "en")
          FILTER(LCASE(STR(?label)) = "{constructor_name.lower()}")
        }}
        LIMIT 1
    """)
    try:
        results = sparql.query().bindings
        if not results:
            _cache[cache_key] = {}
            return {}
        r = results[0]
        dissolved_raw = r["dissolved"].value if "dissolved" in r else ""
        data = {
            "foundingDate": r["foundingDate"].value[:10] if "foundingDate" in r else "",
            "hq":           r["hqLabel"].value           if "hqLabel"      in r else "",
            "logo":         r["logo"].value              if "logo"         in r else "",
            "website":      r["website"].value           if "website"      in r else "",
            "country":      r["countryLabel"].value      if "countryLabel" in r else "",
            "founder":      r["founderLabel"].value      if "founderLabel" in r else "",
            "dissolved":    dissolved_raw[:10]           if dissolved_raw  else "",
            "wikidata_uri": r["item"].value              if "item"         in r else "",
        }
        _cache[cache_key] = data
        return data
    except Exception:
        _cache[cache_key] = {}
        return {}


# ── DBpedia — Circuits ────────────────────────────────────────────────────────

def get_circuit_dbpedia(circuit_name: str) -> dict:
    """
    Return DBpedia enrichment for a racing circuit.

    New fields vs. original:
      turns     (dbp:turns)    — number of corners
      capacity  (dbp:capacity) — spectator capacity
      opened    (dbp:opened)   — year the circuit opened
      lapRecord (dbp:lapRecord)— fastest lap record (textual, e.g. "1:10.239 – Hamilton (2020)")
    """
    cache_key = f"dbp:circuit:{circuit_name}"
    if cache_key in _cache:
        return _cache[cache_key]

    # Construct the DBpedia resource URI directly from the circuit name
    # (e.g. "Circuit de Monaco" → <http://dbpedia.org/resource/Circuit_de_Monaco>)
    # This is more reliable than label-matching queries which often time out.
    resource_uri = "http://dbpedia.org/resource/" + circuit_name.replace(" ", "_")

    sparql = SPARQLWrapper2(DBPEDIA_ENDPOINT)
    sparql.setTimeout(_TIMEOUT)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX dbp: <http://dbpedia.org/property/>
        SELECT ?abstract ?length ?turns ?capacity ?opened ?lapRecord WHERE {{
          OPTIONAL {{ <{resource_uri}> dbo:abstract  ?abstract  FILTER(LANG(?abstract) = "en") }}
          OPTIONAL {{ <{resource_uri}> dbp:length    ?length    }}
          OPTIONAL {{ <{resource_uri}> dbp:turns     ?turns     }}
          OPTIONAL {{ <{resource_uri}> dbp:capacity  ?capacity  }}
          OPTIONAL {{ <{resource_uri}> dbp:opened    ?opened    }}
          OPTIONAL {{ <{resource_uri}> dbp:lapRecord ?lapRecord }}
          FILTER(BOUND(?turns) || BOUND(?capacity) || BOUND(?abstract) || BOUND(?length))
        }}
        LIMIT 1
    """)
    try:
        results = sparql.query().bindings
        if not results:
            _cache[cache_key] = {}
            return {}
        r       = results[0]
        lap_raw = r["lapRecord"].value if "lapRecord" in r else ""
        data = {
            "abstract":    r["abstract"].value  if "abstract" in r else "",
            "length":      r["length"].value    if "length"   in r else "",
            "turns":       r["turns"].value     if "turns"    in r else "",
            "capacity":    r["capacity"].value  if "capacity" in r else "",
            "opened":      r["opened"].value    if "opened"   in r else "",
            "lapRecord":   lap_raw[:120]        if lap_raw    else "",
            "dbpedia_uri": resource_uri,
        }
        _cache[cache_key] = data
        return data
    except Exception:
        _cache[cache_key] = {}
        return {}
