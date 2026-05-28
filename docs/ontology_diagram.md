# F1 Knowledge Ontology — RDF/RDFS Diagram

> Rendered with Mermaid `classDiagram`. Requires Mermaid v9+.

```mermaid
classDiagram
direction TB

%% ══ Abstract root classes ═══════════════════════════════════════════════
class Entity {
    +nationality : string
    +name : string
    +url : anyURI
}
class Person
class Team
class Venue
class Event {
    +year : gYear
}
class PerformanceRecord {
    +milliseconds : integer
}
class Standing {
    +points : decimal
    +position : integer
    +wins : integer
}

%% ══ Concrete OWL-asserted classes ═══════════════════════════════════════
class Driver {
    <<rdfs:domain driverRef>>
    +driverRef : string
    +forename : string
    +surname : string
    +dob : date
    +driverId : integer
}

class Constructor {
    <<rdfs:domain constructorRef>>
    +constructorRef : string
    +constructorId : integer
}

class Circuit {
    <<rdfs:domain circuitRef>>
    +circuitRef : string
    +location : string
    +country : string
    +lat : decimal
    +lng : decimal
}

class Race {
    +raceId : integer
    +round : integer
    +date : date
}

class Season

class Result {
    +resultId : integer
    +positionOrder : integer
    +grid : integer
    +laps : integer
    +points : decimal
}

class QualifyingResult {
    +qualifyId : integer
}

class LapTime
class PitStop
class ConstructorResult

class DriverStanding {
    +driverStandingsId : integer
}

class ConstructorStanding {
    +constructorStandingsId : integer
}

class Status {
    +statusLabel : string
}

%% ══ SPIN-inferred subclasses (not in raw data) ═══════════════════════════
class WorldChampion {
    <<SPIN — GROUP BY MAX round>>
}
class MultichampionDriver {
    <<SPIN — COUNT championships ≥ 2>>
}
class Veteran {
    <<SPIN — COUNT results ≥ 100>>
}
class ConstructorChampion {
    <<SPIN — constructor standings>>
}
class ActiveCircuit {
    <<SPIN — MAX year = dataset max>>
}
class HistoricCircuit {
    <<SPIN — MAX year + 10 threshold>>
}
class PodiumResult {
    <<SPIN — positionOrder ≤ 3>>
}

%% ══ Abstract class hierarchy ════════════════════════════════════════════
Entity <|-- Person
Entity <|-- Team
Entity <|-- Venue

Person <|-- Driver
Team <|-- Constructor
Venue <|-- Circuit

Event <|-- Race
Event <|-- Season

PerformanceRecord <|-- Result
PerformanceRecord <|-- QualifyingResult
PerformanceRecord <|-- LapTime
PerformanceRecord <|-- PitStop
PerformanceRecord <|-- ConstructorResult

Standing <|-- DriverStanding
Standing <|-- ConstructorStanding

%% ══ SPIN-inferred subclasses ════════════════════════════════════════════
Driver <|-- WorldChampion : SPIN
Driver <|-- Veteran : SPIN
WorldChampion <|-- MultichampionDriver : SPIN
Constructor <|-- ConstructorChampion : SPIN
Circuit <|-- ActiveCircuit : SPIN
Circuit <|-- HistoricCircuit : SPIN
Result <|-- PodiumResult : SPIN

%% ══ Object properties ═══════════════════════════════════════════════════
Driver --> Race : wonRace ⊑ competedIn
Driver --> Race : achievedPodium ⊑ competedIn
Driver --> Race : competedIn
Driver --> Season : wonChampionship
Driver --> Constructor : drovFor
Constructor --> Driver : hadDriver [inverseOf drovFor]
Driver --> Driver : wasTeammate [Symmetric]
Race --> Circuit : heldAt [Functional]
Race --> Circuit : circuit [Functional]
Race --> Season : season [Functional]
Constructor --> Season : wonConstructorChampionship
Result --> Status : status [Functional]
DriverStanding --> Driver : driver
DriverStanding --> Race : race
ConstructorStanding --> Constructor : constructor
ConstructorStanding --> Race : race
```

## Inference summary

| Mechanism | What it infers |
|---|---|
| `rdfs:domain` of `driverRef` | entity with `driverRef` → `rdf:type Driver` |
| `rdfs:domain` of `constructorRef` | entity → `rdf:type Constructor` |
| `rdfs:domain` of `circuitRef` | entity → `rdf:type Circuit` |
| `owl:equivalentClass` + `someValuesFrom` | bidirectional classification (HermiT) |
| `owl:inverseOf` | `drovFor` triple → `hadDriver` triple materialised |
| `owl:SymmetricProperty` | `wasTeammate` triple → inverse also materialised |
| `rdfs:subPropertyOf` | `wonRace`/`achievedPodium` triples also appear as `competedIn` |
| SPIN rules (14 total) | WorldChampion, Veteran, HistoricCircuit, PodiumResult, etc. |

## Disjointness axioms (`owl:disjointWith`)

- `Driver ⊥ Constructor`
- `Driver ⊥ Circuit`
- `Circuit ⊥ Constructor`
- `Race ⊥ Season`
- `Race ⊥ Driver`
- `Result ⊥ QualifyingResult`
- `Result ⊥ LapTime`
