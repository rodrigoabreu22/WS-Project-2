# External Knowledge Integration

Shows how the F1 knowledge graph is enriched at render time from three external sources. All calls are asynchronous (client-side JS fetch after page load) with in-process caching on the Django server.

```mermaid
graph TD
    subgraph KG["F1 Knowledge Graph (GraphDB)"]
        DR["f1:Driver\n861 entities\nrdfs:seeAlso → Wikipedia URL"]
        CT["f1:Constructor\n212 entities\nrdfs:seeAlso → Wikipedia URL"]
        CI["f1:Circuit\n77 entities\nrdfs:seeAlso → Wikipedia URL\nrdfs:label → circuit name"]
        RC["f1:Race\n1,125 entities\nrdfs:seeAlso → Wikipedia URL"]
        SE["f1:Season\n75 entities\nrdfs:seeAlso → Wikipedia URL"]
    end

    subgraph WD["Wikidata SPARQL endpoint\nhttps://query.wikidata.org/sparql"]
        WD_D["Drivers\nFilter: wdt:P106 = Q10843402\n─────────────────────\nP19 birthPlace\nP570 deathDate (†)\nP2048 height\nP22 father name\nP40 children names\nschema:description"]
        WD_C["Constructors\nFilter: wdt:P31 = Q41298738\n─────────────────────\nP571 founding date\nP159 headquarters\nP154 logo image\nP856 official website\nP17 country\nP112 founder\nP576 dissolved date"]
    end

    subgraph DBP["DBpedia SPARQL endpoint\nhttps://dbpedia.org/sparql"]
        DBP_CI["Circuits — direct URI:\ndbr:{Circuit_Name_With_Underscores}\n─────────────────────\ndbo:abstract (text)\ndbp:length (km)\ndbp:turns (corners)\ndbp:capacity (spectators)\ndbp:opened (year)\ndbp:lapRecord (text)\ndbp:surface (asphalt/etc)\ndbo:thumbnail (image)"]
    end

    subgraph WP["Wikipedia REST API\nhttps://en.wikipedia.org/api/rest_v1/page/summary"]
        WP_ALL["Called per entity via rdfs:seeAlso URL\n─────────────────────\nthumbnail.source (portrait/photo)\ndescription (short tagline)\nextract (up to 500 chars)"]
    end

    subgraph DJ["Django backend\nservices/external_data.py"]
        API["GET /api/entity-info/\n?type=driver|constructor|circuit\n&name=...&wiki=..."]
        IMG["GET /api/wiki-image/\n?url=..."]
    end

    %% Knowledge graph → external queries
    DR -->|"rdfs:seeAlso URL\n+ driver name"| WD_D
    CT -->|"rdfs:seeAlso URL\n+ constructor name"| WD_C
    CI -->|"circuit name\n→ dbr:Name_With_Underscores\n(not rdfs:label triple)"| DBP_CI

    %% All entities → Wikipedia
    DR -->|rdfs:seeAlso| WP_ALL
    CT -->|rdfs:seeAlso| WP_ALL
    CI -->|rdfs:seeAlso| WP_ALL
    RC -->|rdfs:seeAlso| WP_ALL
    SE -->|rdfs:seeAlso| WP_ALL

    %% Django APIs
    WD_D --> API
    WD_C --> API
    DBP_CI --> API
    WP_ALL --> API
    WP_ALL --> IMG
```

## What is Currently Enriched

| Entity | Wikipedia | Wikidata | DBpedia |
|--------|-----------|----------|---------|
| Driver | ✅ photo + extract | ✅ birthPlace, death†, height, family | — |
| Constructor | ✅ photo + extract | ✅ logo, founder, website, country, dissolved | — |
| Circuit | ✅ photo + extract | — | ✅ turns, capacity, opened, surface, lap record |
| Race | ✅ extract (planned) | — | — |
| Season | ✅ extract (planned) | — | — |

## Key Design Decisions

| Decision | Reason |
|---|---|
| Async JS fetch (not server-side render) | Keeps TTFB fast; external APIs add 2–12s latency |
| In-process `_cache` dict | Prevents duplicate calls for the same entity within a request |
| Direct DBpedia URI construction | F1 circuits not typed as `dbo:RaceTrack` — label queries return 0 results |
| Wikipedia REST `/page/summary` | Returns structured JSON (thumbnail URL, tagline, extract) in one request |
| 12s timeout per SPARQL query | Prevents page hang if Wikidata/DBpedia is slow or rate-limited |
