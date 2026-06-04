# manawatu-wag_2025.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | Manawatu GymSports WAG Opens 2025 |
| **Dates** | 2025-05-31 to 2025-06-02 (2 days) |
| **Sport** | GYMNASTICS (Artistic) |
| **Discipline** | WAG only |
| **Scope** | PUBLIC |
| **Host Organization** | Manawatu GymSports (MGI) |
| **Participants** | 453 registered, 452 competed |
| **Organizations (Clubs)** | 15 |
| **Units** | 21 |
| **Sessions** | 14 |
| **Performance Individuals** | 595 (452 unique participants, some in 2 units) |
| **Performance Scores** | 2513 |
| **Performance Result Tables** | 203 |
| **Performance Teams** | 65 |
| **Performance Rules** | 21 |
| **File size** | ~5.2 MB (minified JSON, single line) |

---

## 2. Data Model Overview

This file uses the flat reference-based `performance*` model with 22 top-level keys. Entities link to each other via `eventId`, `unitId`, `sessionId`, `participantId`, and `entityId` fields.

### Top-Level Keys

```
manawatu-wag_2025.json
│
├── events:                          [ Event ] (1)
├── eventOfficials:                  [] (0)
├── eventOrganizations:              [ Organization ] (15)
├── eventParticipants:               [ Participant ] (453)
├── performanceGroups:               [] (0)
├── performanceIndividuals:          [ Individual ] (595)
├── performanceJudgingPanels:        [] (0)
├── performanceRecorders:            [] (0)
├── performanceResultTables:         [ ResultTable ] (203)
├── performanceRules:                [ RuleSet ] (21)
├── performanceScores:               [ Score ] (2513)
├── performanceSessionGroups:        [ SessionGroup ] (68)
├── performanceSessionRotations:     [ Rotation ] (272)
├── performanceTeams:                [ Team ] (65)
├── products:                        [] (0)
├── scoreboards:                     [] (0)
├── sessions:                        [ Session ] (14)
├── sessionFolders:                  [] (0)
├── shortUrls:                       [ ShortUrl ] (16)
├── transactions:                    [] (0)
├── units:                           [ Unit ] (21)
└── unitFolders:                     [] (0)
```

---

## 3. Entity Relationship Diagram

```
events (1)
  │
  ├── units[] (21)
  │     ├── 15 All-Around & Teams units (Day 1)
  │     ├── 6 Apparatus-only units (Day 2)
  │     ├── performanceRules[]
  │     ├── performanceResultTables[]
  │     ├── performanceIndividuals[] → eventParticipants[]
  │     └── performanceTeams[]
  │           └── memberRefs[] → performanceIndividuals[]
  │
  ├── sessions[] (14)
  │     ├── orders 0-9: Day 1 (AA units)
  │     ├── orders 10-13: Day 2 (Apparatus units)
  │     ├── unitIds[] → units[]
  │     ├── performanceSessionGroups[] (68)
  │     │     └── entityRefs[] → performanceIndividuals[]
  │     └── performanceSessionRotations[] (272)
  │           ├── allowedEventCodes (apparatus)
  │           └── orderedEntityRefs[] → performanceIndividuals[]
  │
  └── eventParticipants (453)
        └── performanceIndividuals (595)
              ├── 309 participants in 1 unit (Day 1 only)
              ├── 143 participants in 2 units (Day 1 AA + Day 2 Apparatus)
              ├── resultTableConfigs[] → performanceResultTables[]
              └── performanceScores[] (2513)

performanceScores (2513)
  ├── entityId → performanceIndividuals[]
  ├── unitScoreId → performanceRules[].scores[].id
  └── publicOutputs{} → computed score values

performanceResultTables (203)
  ├── unitId → units[]
  └── resultSets[].primaryRanking[] → rankings (no advancement)
```

---

## 4. Event Metadata

| Field | Value |
|---|---|
| `name` | Manawatu GymSports WAG Opens 2025 |
| `organizationId` | MGI (Manawatu GymSports) |
| `startDate` | 2025-05-31 |
| `endDate` | 2025-06-02 |
| `startsAt` | 2025-05-30T12:00:00Z |
| `stage` | completed |
| `isPublic` | true |
| `participantCount` | 453 |
| `timeZone` | Pacific/Auckland |
| `countryCode` | NZ |
| `currencyCode` | NZD |
| `venues` | [] (not specified) |

---

## 5. Two-Day Competition Model

This competition spans two days with distinct round types:

| | Day 1 (Sessions 1-10) | Day 2 (Sessions 11-14) |
|---|---|---|
| **Focus** | AA, Apps and Teams | Apparatus only |
| **Steps** | 1-10 | 5-10 |
| **Units** | 15 (all steps, split by colour for 1-5) | 6 (one per step) |
| **Sessions** | Orders 0-9 | Orders 10-13 |
| **Team scoring** | Steps 1-8 | No |
| **VT scoring** | Single or dual vault (per step rules) | Single or dual vault (per step rules) |

143 of 452 competing participants (31.6%) appear in **2 performance individuals** — one for their Day 1 AA unit and one for their Day 2 Apparatus unit.

### Typical Competitor Flow

```
Competitor (Steps 5-10)
├── Day 1:  All Around & Teams session
│           → VT, UB, BB, FX passes
│           → allAround ranking
│           → team ranking (Steps 5-8)
│
└── Day 2:  Apparatus session
            → VT, UB, BB, FX passes
            → apparatus-only rankings
            → no allAround or team ranking
```

Steps 1-4 gymnasts compete on Day 1 only.

---

## 6. Competition Structure: Units & Sessions

### 6a. Units (21)

**Day 1 — 15 All-Around & Teams units:**

| # | Unit Name | Individuals | Teams | Step | Stream |
|---|---|---|---|---|---|
| 1 | WAG STEP 1 Green AA, Apps and Teams | 49 | 6 | 1 | Green |
| 2 | WAG STEP 1 Blue AA, Apps and Teams | 35 | 4 | 1 | Blue |
| 3 | WAG STEP 2 Blue AA, Apps and Teams | 35 | 4 | 2 | Blue |
| 4 | WAG STEP 2 Green AA, Apps and Teams | 47 | 6 | 2 | Green |
| 5 | WAG STEP 3 Blue AA, Apps and Teams | 33 | 4 | 3 | Blue |
| 6 | WAG STEP 3 Green AA, Apps and Teams | 39 | 7 | 3 | Green |
| 7 | WAG STEP 4 Blue AA, Apps and Teams | 38 | 6 | 4 | Blue |
| 8 | WAG STEP 4 Green AA, Apps and Teams | 32 | 5 | 4 | Green |
| 9 | WAG STEP 5 Green All Around, Teams | 24 | 4 | 5 | Green |
| 10 | WAG STEP 5 Blue All Around, Teams | 30 | 5 | 5 | Blue |
| 11 | WAG STEP 6 All Around and Teams | 34 | 6 | 6 | — |
| 12 | WAG STEP 7 All Around and Teams | 37 | 6 | 7 | — |
| 13 | WAG STEP 8 All Around and Teams | 12 | 2 | 8 | — |
| 14 | WAG STEP 9 All Around | 4 | 0 | 9 | — |
| 15 | WAG STEP 10 All Around | 2 | 0 | 10 | — |

**Day 2 — 6 Apparatus-only units:**

| # | Unit Name | Individuals | Teams | Step |
|---|---|---|---|---|
| 16 | WAG STEP 5 Apparatus | 55 | 0 | 5 |
| 17 | WAG STEP 6 Apparatus | 34 | 0 | 6 |
| 18 | WAG STEP 7 Apparatus | 37 | 0 | 7 |
| 19 | WAG STEP 8 Apparatus | 12 | 0 | 8 |
| 20 | WAG STEP 9 Apparatus | 4 | 0 | 9 |
| 21 | WAG STEP 10 Apparatus | 2 | 0 | 10 |

### 6b. Apparatus

All WAG steps use 4 apparatus: **VT, UB, BB, FX**.

### 6c. WAG Step Progression

| Step | AA unit name | Apparatus unit | VT vaults | Streams | Teams |
|---|---|---|---|---|---|
| 1 | AA, Apps and Teams | — | 1 | Green / Blue | Yes |
| 2 | AA, Apps and Teams | — | 1 | Blue / Green | Yes |
| 3 | AA, Apps and Teams | — | 1 | Blue / Green | Yes |
| 4 | AA, Apps and Teams | — | 1 | Blue / Green | Yes |
| 5 | All Around, Teams | Apparatus | 1 | Green / Blue | Yes (AA only) |
| 6 | All Around and Teams | Apparatus | **2** | — | Yes (AA only) |
| 7 | All Around and Teams | Apparatus | **2** | — | Yes (AA only) |
| 8 | All Around and Teams | Apparatus | 1 | — | Yes (AA only) |
| 9 | All Around | Apparatus | 1 | — | No |
| 10 | All Around | Apparatus | **2** | — | No |

Steps 1-4 use colour streams (Green/Blue or Blue/Green) to split competitors within the same step. Step 5 also uses streams. Steps 6-10 have a single stream each.

Steps 9 and 10 have no team scoring (team count = 0).

### 6d. Sessions (14)

| Order | Session | Units | Individuals |
|---|---|---|---|
| 0 | WAG Session 1 STEP 1 | STEP 1 Green + STEP 1 Blue | 84 |
| 1 | WAG Session 2 STEP 2 | STEP 2 Blue + STEP 2 Green | 82 |
| 2 | WAG Session 3 STEP 3 | STEP 3 Blue + STEP 3 Green | 72 |
| 3 | WAG Session 4 STEP 4 Blue | STEP 4 Blue | 38 |
| 4 | WAG Session 5 STEP 4 Green | STEP 4 Green | 32 |
| 5 | WAG Session 6 STEP 5 Green | STEP 5 Green AA | 24 |
| 6 | WAG Session 7 STEP 5 Blue | STEP 5 Blue AA | 30 |
| 7 | WAG Session 8 STEP 6 | STEP 6 AA | 34 |
| 8 | WAG Session 9 STEP 7 | STEP 7 AA | 37 |
| 9 | WAG Session 10 STEP 8, 9, 10 | STEP 8 AA + STEP 9 AA + STEP 10 AA | 18 |
| 10 | WAG Session 11 STEP 5 | STEP 5 Apparatus | 53 |
| 11 | WAG Session 12 STEP 6 | STEP 6 Apparatus | 34 |
| 12 | WAG Session 13 STEP 8, 9, 10 | STEP 8 App + STEP 9 App + STEP 10 App | 18 |
| 13 | WAG Session 14 STEP 7 | STEP 7 Apparatus | 36 |

---

## 7. Two-Vault Apparatus (Steps 6, 7, 10)

Steps 6, 7, and 10 require gymnasts to perform **two vault passes**. This is reflected in 6 unitEventIds across their respective AA and Apparatus units:

| Unit | VT passes | Aggregation (AA) | Aggregation (Apparatus) |
|---|---|---|---|
| WAG STEP 6 All Around and Teams | 2 | AVERAGE | — |
| WAG STEP 7 All Around and Teams | 2 | AVERAGE | — |
| WAG STEP 10 All Around | 2 | 1 vault counts | — |
| WAG STEP 6 Apparatus | 2 | — | AVERAGE |
| WAG STEP 7 Apparatus | 2 | — | AVERAGE |
| WAG STEP 10 Apparatus | 2 | — | BEST |

All other WAG steps (1-5, 8-9) use a **single vault pass** across all units.

---

## 8. Performance Individuals (595)

### Entity Structure

```
performanceIndividual {
  _id:              ObjectId
  participantId:    ObjectId    → eventParticipants._id
  eventId:          ObjectId    → events._id
  unitId:           ObjectId    → units._id
  tags:             []          (unused)
  resultTableConfigs[]
    ├── resultTableId           → performanceResultTables.resultTableId
    ├── tieBreaker              numeric
    ├── hasOptedOutAdvancing    bool
    └── eventIdsOptedOut        []
}
```

### Participant-to-Individual Mapping

- **453** eventParticipants (registered)
- **452** unique participants with at least 1 performance individual
- **595** total performance individuals (some participants appear twice)
- **1** participant registered but never competed

| Participant type | Count | % |
|---|---|---|
| In 1 unit (Day 1 AA only) | 309 | 68.4% |
| In 2 units (Day 1 AA + Day 2 Apparatus) | 143 | 31.6% |
| Registered but did not compete | 1 | 0.2% |

A participant in 2 units has separate performanceIndividual entries per unit, each with its own `resultTableConfigs[]` and `performanceScore[]` entries.

---

## 9. Performance Teams (65)

### Entity Structure

```
performanceTeam {
  _id:              ObjectId
  eventId:          ObjectId
  unitId:           ObjectId
  tags:             []
  resultTableConfigs[]
    └── { resultTableId, tieBreaker, ... }
  memberRefs[]
    └── { entityId → performanceIndividual, entityType: "individual" }
}
```

### Team Counts by Unit

Teams only exist in Day 1 (AA) units. All Day 2 (Apparatus) units have 0 teams.

| Unit | Teams |
|---|---|
| WAG STEP 3 Green AA | 7 |
| WAG STEP 1 Green AA | 6 |
| WAG STEP 2 Green AA | 6 |
| WAG STEP 4 Blue AA | 6 |
| WAG STEP 6 AA | 6 |
| WAG STEP 7 AA | 6 |
| WAG STEP 4 Green AA | 5 |
| WAG STEP 5 Blue AA | 5 |
| WAG STEP 1 Blue AA | 4 |
| WAG STEP 2 Blue AA | 4 |
| WAG STEP 3 Blue AA | 4 |
| WAG STEP 5 Green AA | 4 |
| WAG STEP 8 AA | 2 |

---

## 10. Result Tables (203)

### 10a. Structure

```
performanceResultTable {
  _id:                    ObjectId
  eventId:                ObjectId
  unitId:                 ObjectId
  resultTableId:          string (opaque)
  primaryResultSetId:     string → references resultSets[].id
  resultSets[]
    ├── id
    ├── primaryRanking[]
    │   └── { entityId, value (score), rank, sourceItems[], isEqual }
    └── secondaryRanking[] (optional)
  isPublic:               bool
  — NO advancingIds / qualifierIds / reserveIds —
}
```

### 10b. Result Table Types by Set Count

| Result Sets | Meaning | Tables |
|---|---|---|
| **1 set** | Single ranking (individual apparatus) | 152 |
| **5 sets** | 4 apparatus + 1 allAround | 51 |

No 7-set tables (MAG format) exist — this is WAG only.

### 10c. Result Tables per Unit

| Unit | Tables | With Advancement |
|---|---|---|
| Each AA unit (Steps 1-8) | 11 | 0 |
| Each Apparatus unit (Steps 5-8) | 10 | 0 |
| STEP 9 All Around | 5 | 0 |
| STEP 10 All Around | 5 | 0 |
| STEP 9 Apparatus | 5 | 0 |
| STEP 10 Apparatus | 5 | 0 |

**No advancement** — 0 of 203 result tables have advancing/qualifier/reserve IDs. AA units have 11 tables (4 apparatus + 1 AA + 6 individual apparatus rankings), Apparatus units have 10 (no team result), and Steps 9-10 have 5 each (small fields).

---

## 11. Scoring System — Node-Tree Architecture

### 11a. Performance Rules (21)

Each unit has one rule set. All 21 use `"WAG FIG 2022/2024"`.

### 11b. Score Node-Tree Inputs

Each rule has a `nodeTree` with 5 input fields (IDs unique to this export):

| Input ID (example) | Input Name | Type |
|---|---|---|
| `2TTSimpF8uBnD50u9ArO7` | Did Not Start | Boolean |
| `zlhJPAQtgZdUoJDtp803f` | Zero | Boolean |
| `gOLgi56lhgtlvYJ39J-4a` | Difficulty | Float |
| `Q5e9tuIzin9Rp914oJRTe` | Execution Deductions | Table (Float) |
| `epiDN3Rx6qzaQonEbZm41` | Neutral Deductions | Float |

### 11c. Performance Scores (2513)

```
performanceScore {
  _id:            ObjectId
  eventId:        ObjectId
  unitId:         ObjectId
  entityId:       ObjectId    → performanceIndividuals._id
  entityType:     "individual"
  unitScoreId:    string      → performanceRules[].scores[].id
  unitEventId:    string      → identifies apparatus
  unitPassId:     string      → identifies pass
  inputs:         {}          (empty in export)
  outputs:        {}          (empty in export)
  publicOutputs:  {}          ← computed score values
}
```

### 11d. Interpreting a Score

The `publicOutputs` dictionary contains 4 keys consistently mapped to score components:

```
publicOutputs example:
{
  "Ut2MuKcIkOof-N8vvxB20": 13.65,    ← finalScore
  "hiTYs4vDIFQoWP4_Qhx1a": 5,        ← difficultyScore
  "Ts4mwfg9jxOnMT3mVP9tK": 8.65,     ← executionScore
  "3EyRPFP0S5geB7wv08KBj": 0         ← neutral deductions
}
```

Score values found: numeric (NORMAL scores) and `"dns"` (Did Not Start).

The opaque output IDs are unique to this export and must be cross-referenced against the node-tree definition in the relevant `performanceRules` entry to map to field names.

### 11e. Multi-Pass Scores

6 unitEventIds have 2 passes each (all VT, in Steps 6, 7, 10). Scores for these events have `unitPassId` values that differentiate the first and second vault attempts. The specific aggregation method (AVERAGE vs BEST vs 1-counts) is applied at the result table level rather than at the individual score level.

---

## 12. Organizations (15 Clubs)

Regional clubs from the lower North Island:

| Code | Name | Participants |
|---|---|---|
| HUT | Hutt Valley Gymnastics | 67 |
| MGI | Manawatu GymSports | 60 |
| OMN | OMNI Gymnastic Centre | 48 |
| TWI | Twisters Tawa Gymnastics Club | 46 |
| WAI | Gymnastics Waitara | 44 |
| WBG | Whanganui Boys and Girls Gym Club | 34 |
| RIM | Rimutaka Gymsports | 33 |
| LVN | Levin Gymnastics Club | 22 |
| HAS | Hastings Gymnastics | 21 |
| GGC | Gisborne Gymnastics Club | 20 |
| KAP | Kapiti Gymnastics Club | 19 |
| HCG | Harbour City Gymnastics | 16 |
| CAP | Capital Gymnastics | 9 |
| ONS | Onslow Gymnastics | 9 |
| CEN | Central Gym Club | 5 |

---

## 13. Data Flow

```
Event (2 days — May 31 - June 2)
  │
  ├── 21 units: 15 AA (Day 1) + 6 Apparatus (Day 2)
  │
  ├── 14 sessions: 10 Day 1 + 4 Day 2
  │     └── performanceSessionGroups (68) + Rotations (272)
  │
  ├── 453 eventParticipants
  │     └── 595 performanceIndividuals (452 unique)
  │           ├── 309 in 1 unit (Day 1 AA only)
  │           ├── 143 in 2 units (Day 1 AA + Day 2 App)
  │           ├── unit assignment
  │           ├── resultTableConfigs → result tables
  │           └── memberRefs in teams
  │
  ├── 2513 performanceScores
  │     ├── per individual per apparatus pass
  │     ├── 6 multi-pass VT events (Steps 6, 7, 10)
  │     ├── scored via WAG FIG 2022/2024 rules
  │     └── outputs: finalScore, difficulty, execution, deductions
  │
  └── 203 performanceResultTables
        ├── 152 single-set tables (apparatus rankings)
        ├── 51 five-set tables (4 apparatus + AA)
        └── 0 advancement tables (no finals)
```

---

## 14. Notable Observations

- **WAG-only competition**: No MAG — the entire file covers only Women's Artistic Gymnastics from Steps 1-10.
- **Two-day format with distinct round types**: Day 1 (sessions 1-10) covers all-around and team competition. Day 2 (sessions 11-14) covers apparatus-only competition. 31.6% of gymnasts compete on both days.
- **143 participants in 2 units**: Each gymnast has two separate `performanceIndividual` entries (one per unit), with different `resultTableConfigs` and `performanceScore` entries. The Day 1 AA individual has 6 resultTableConfigs (4 apparatus + 1 AA + 1 team) while the Day 2 Apparatus individual has 5 (4 apparatus + 1 all-apparatus).
- **No advancement or finals**: 0 of 203 result tables have advancing/qualifier/reserve IDs. All units use a single-round format with no progression pipeline.
- **Two-vault steps**: Steps 6, 7, and 10 require two vault passes across both their AA and Apparatus units. Steps 6 and 7 average both vaults. Step 10 uses BEST aggregation for Apparatus and counts 1 vault for AA.
- **Colour-coded streams**: Steps 1-5 use Blue/Green colour streams to split competitors within the same step level into separate units. Steps 6-10 use a single stream each.
- **Steps 9 and 10 have no team scoring**: Their AA units show `teamCount: 0` and no team result tables.
- **Steps 9 and 10 have tiny fields**: Only 4 and 2 individuals respectively across both AA and Apparatus units.
- **Apparatus units have no teams**: All 6 Day 2 Apparatus units show `teamCount: 0`.
- **No session folders**: The `sessionFolders` array is empty — the WAG-only context makes discipline folders unnecessary.
- **1 participant (0.2%)** registered but never appeared in a performance individual — they did not compete.
- **Score output IDs**: The 4-key output structure (finalScore, difficulty, execution, deductions) is consistent across all scores. The specific opaque IDs are unique to this export (e.g. `Ut2MuKcIkOof-N8vvxB20`).
- **Code of points**: All 21 units use WAG FIG 2022/2024.
- **Same event, different format**: This file represents the same competition found in the old-format `manawatu-wag-25.json` under `data-collection/JSON 2025/quar/`, but exported in the newer flat reference-based schema.