# Ontology Overview — High-Level

Shows the 7 top-level abstract classes, the 13 concrete asserted classes, and the 7 SPIN-inferred subclasses. Disjointness axioms and key object properties are omitted for clarity; see the focused diagrams for those.

```mermaid
classDiagram
    direction TB

    class Entity["f1:Entity (abstract)"]
    class Person["f1:Person (abstract)"]
    class Team["f1:Team (abstract)"]
    class Venue["f1:Venue (abstract)"]
    class Event["f1:Event (abstract)"]
    class PerformanceRecord["f1:PerformanceRecord (abstract)"]
    class Standing["f1:Standing (abstract)"]

    class Driver["f1:Driver"]
    class Constructor["f1:Constructor"]
    class Circuit["f1:Circuit"]
    class Season["f1:Season"]
    class Race["f1:Race"]
    class Result["f1:Result"]
    class QualifyingResult["f1:QualifyingResult"]
    class LapTime["f1:LapTime"]
    class PitStop["f1:PitStop"]
    class ConstructorResult["f1:ConstructorResult"]
    class DriverStanding["f1:DriverStanding"]
    class ConstructorStanding["f1:ConstructorStanding"]
    class Status["f1:Status"]

    %% SPIN-inferred subclasses (purple border in Protégé)
    class WorldChampion["f1:WorldChampion 🏆 SPIN"]
    class MultichampionDriver["f1:MultichampionDriver ⭐ SPIN"]
    class Veteran["f1:Veteran 🏟 SPIN"]
    class ActiveCircuit["f1:ActiveCircuit ✅ SPIN"]
    class HistoricCircuit["f1:HistoricCircuit 📜 SPIN"]
    class ConstructorChampion["f1:ConstructorChampion 🏎 SPIN"]
    class PodiumResult["f1:PodiumResult 🥉 SPIN"]

    Entity <|-- Person
    Entity <|-- Team
    Entity <|-- Venue

    Person  <|-- Driver
    Team    <|-- Constructor
    Venue   <|-- Circuit

    Event   <|-- Season
    Event   <|-- Race

    PerformanceRecord <|-- Result
    PerformanceRecord <|-- QualifyingResult
    PerformanceRecord <|-- LapTime
    PerformanceRecord <|-- PitStop
    PerformanceRecord <|-- ConstructorResult

    Standing <|-- DriverStanding
    Standing <|-- ConstructorStanding

    Driver      <|-- WorldChampion
    WorldChampion <|-- MultichampionDriver
    Driver      <|-- Veteran
    Circuit     <|-- ActiveCircuit
    Circuit     <|-- HistoricCircuit
    Constructor <|-- ConstructorChampion
    Result      <|-- PodiumResult
```

**Legend:** Classes labelled `SPIN` are not asserted in the facts file. They are materialised at runtime by SPIN rules in `championship/spin_rules.py`. Classes in the first two tiers are asserted or OWL-Max-inferred at GraphDB import time.
