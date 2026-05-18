"""
External semantic enrichment via Wikidata and DBpedia.

Functions return a plain dict of enrichment fields, or {} on any failure.
Results are cached in-process to avoid repeated remote calls per page load.

Reference: ws.10b — accessing Wikidata and DBpedia via SPARQLWrapper.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from SPARQLWrapper import SPARQLWrapper2

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
DBPEDIA_ENDPOINT  = "https://dbpedia.org/sparql"
_TIMEOUT = 10  # seconds
_USER_AGENT = "ws-f1-project/1.0 (academic; contact: rodrigo@example.org)"

_cache: dict[str, object] = {}


# ── Wikipedia image ────────────────────────────────────────────────────────────

def get_wikipedia_image(wiki_url: str) -> str:
    """Return a thumbnail URL from any Wikipedia article URL.

    Uses the Wikipedia REST summary API — no key required, no SPARQL needed.
    Example: https://en.wikipedia.org/wiki/Lewis_Hamilton
          -> https://upload.wikimedia.org/wikipedia/commons/thumb/...
    """
    if not wiki_url or "/wiki/" not in wiki_url:
        return ""
    cache_key = f"wp:img:{wiki_url}"
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        title = wiki_url.rstrip("/").split("/wiki/")[-1]
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        image = data.get("thumbnail", {}).get("source", "")
        _cache[cache_key] = image
        return image
    except Exception:
        _cache[cache_key] = ""
        return ""


# ── Wikidata ───────────────────────────────────────────────────────────────────

def get_driver_wikidata(driver_name: str) -> dict:
    """Return Wikidata enrichment for a Formula 1 driver by full name."""
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
        SELECT ?item ?birthPlaceLabel ?description ?image WHERE {{
          ?item wdt:P106 wd:Q10843402 ;
                rdfs:label ?label .
          OPTIONAL {{ ?item wdt:P19 ?birthPlace }}
          OPTIONAL {{ ?item wdt:P18 ?image }}
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
        LIMIT 1
    """)
    try:
        results = sparql.query().bindings
        if not results:
            _cache[cache_key] = {}
            return {}
        r = results[0]
        data = {
            "birthPlace":   r["birthPlaceLabel"].value if "birthPlaceLabel" in r else "",
            "description":  r["description"].value    if "description"      in r else "",
            "image":        r["image"].value           if "image"            in r else "",
            "wikidata_uri": r["item"].value            if "item"             in r else "",
        }
        _cache[cache_key] = data
        return data
    except Exception:
        _cache[cache_key] = {}
        return {}


def get_constructor_wikidata(constructor_name: str) -> dict:
    """Return Wikidata enrichment for an F1 constructor by name."""
    cache_key = f"wd:constructor:{constructor_name}"
    if cache_key in _cache:
        return _cache[cache_key]

    sparql = SPARQLWrapper2(WIKIDATA_ENDPOINT)
    sparql.setTimeout(_TIMEOUT)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(f"""
        PREFIX wd:  <http://www.wikidata.org/entity/>
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        SELECT ?item ?foundingDate ?hqLabel WHERE {{
          ?item wdt:P31 wd:Q41298738 ;
                rdfs:label ?label .
          OPTIONAL {{ ?item wdt:P571 ?foundingDate }}
          OPTIONAL {{ ?item wdt:P159 ?hq }}
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
        data = {
            "foundingDate": r["foundingDate"].value if "foundingDate" in r else "",
            "hq":           r["hqLabel"].value      if "hqLabel"      in r else "",
            "wikidata_uri": r["item"].value          if "item"         in r else "",
        }
        _cache[cache_key] = data
        return data
    except Exception:
        _cache[cache_key] = {}
        return {}


# ── DBpedia ────────────────────────────────────────────────────────────────────

def get_circuit_dbpedia(circuit_name: str) -> dict:
    """Return DBpedia enrichment for a racing circuit by name (partial match)."""
    cache_key = f"dbp:circuit:{circuit_name}"
    if cache_key in _cache:
        return _cache[cache_key]

    sparql = SPARQLWrapper2(DBPEDIA_ENDPOINT)
    sparql.setTimeout(_TIMEOUT)
    sparql.setQuery(f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX dbp: <http://dbpedia.org/property/>
        SELECT ?circuit ?abstract ?length WHERE {{
          ?circuit a dbo:RaceTrack ;
                   rdfs:label ?label ;
                   dbo:abstract ?abstract .
          OPTIONAL {{ ?circuit dbp:length ?length }}
          FILTER(LANG(?label)    = "en")
          FILTER(LANG(?abstract) = "en")
          FILTER(CONTAINS(LCASE(STR(?label)), "{circuit_name.lower()[:20]}"))
        }}
        LIMIT 1
    """)
    try:
        results = sparql.query().bindings
        if not results:
            _cache[cache_key] = {}
            return {}
        r = results[0]
        data = {
            "abstract":    r["abstract"].value  if "abstract" in r else "",
            "length":      r["length"].value     if "length"   in r else "",
            "dbpedia_uri": r["circuit"].value    if "circuit"  in r else "",
        }
        _cache[cache_key] = data
        return data
    except Exception:
        _cache[cache_key] = {}
        return {}
