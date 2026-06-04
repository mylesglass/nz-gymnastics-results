# hvg-elementary_2025.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | Hutt Valley Elementary Competition |
| **Date** | 2025-05-24 (single day) |
| **Sport** | GYMNASTICS (Artistic) |
| **Disciplines** | WAG + MAG |
| **Scope** | PUBLIC |
| **Host Organization** | Hutt Valley Gymnastics (HVG) |
| **Participants** | 287 registered, 283 competed |
| **Organizations (Clubs)** | 9 |
| **Units** | 9 |
| **Sessions** | 8 |
| **Performance Individuals** | 283 |
| **Performance Scores** | 1230 |
| **Performance Result Tables** | 89 |
| **Performance Teams** | 44 |
| **Performance Rules** | 9 |
| **File size** | ~2.6 MB (minified JSON, single line) |

---

## 2. Data Model Overview

This file uses the same flat reference-based `performance*` model as `csg-classic_2025.json`. Entities link to each other via `eventId`, `unitId`, `sessionId`, `participantId`, and `entityId` fields. The model has 22 top-level keys.

### Top-Level Keys

```
hvg-elementary_2025.json
│
├── events:                          [ Event ] (1)
├── eventOfficials:                  [] (0)
├── eventOrganizations:              [ Organization ] (9)
├── eventParticipants:               [ Participant ] (287)  ← registered athletes
├── performanceGroups:               [] (0)
├── performanceIndividuals:          [ Individual ] (283)   ← athletes who competed
├── performanceJudgingPanels:        [] (0)
├── performanceRecorders:            [] (0)
├── performanceResultTables:         [ ResultTable ] (89)   ← pre-computed rankings
├── performanceRules:                [ RuleSet ] (9)        ← scoring node trees
├── performanceScores:               [ Score ] (1230)       ← individual pass scores
├── performanceSessionGroups:        [ SessionGroup ] (32)  ← competitor groupings
├── performanceSessionRotations:     [ Rotation ] (144)     ← apparatus stations
├── performanceTeams:                [ Team ] (44)          ← team entries
├── products:                        [] (0)
├── scoreboards:                     [] (0)
├── sessions:                        [ Session ] (8)        ← competition time slots
├── sessionFolders:                  [] (0)                 ← none in this file
├── shortUrls:                       [ ShortUrl ] (9)
├── transactions:                    [] (0)
├── units:                           [ Unit ] (9)           ← division/level groupings
└── unitFolders:                     [] (0)
```

---

## 3. Entity Relationship Diagram

```
events (1)
  │
  ├── units[] (9)
  │     ├── performanceRules[]
  │     ├── performanceResultTables[]
  │     ├── performanceIndividuals[] → eventParticipants[]
  │     └── performanceTeams[]
  │           └── memberRefs[] → performanceIndividuals[]
  │
  ├── sessions[] (8)
  │     ├── unitIds[] → units[]
  │     ├── performanceSessionGroups[] (32)
  │     │     └── entityRefs[] → performanceIndividuals[]
  │     └── performanceSessionRotations[] (144)
  │           ├── allowedEventCodes (apparatus)
  │           └── orderedEntityRefs[] → performanceIndividuals[]
  │
  └── eventParticipants (287)
        └── performanceIndividuals (283)
              ├── resultTableConfigs[] → performanceResultTables[]
              └── performanceScores[] (1230)

performanceScores (1230)
  ├── entityId → performanceIndividuals[]
  ├── unitScoreId → performanceRules[].scores[].id
  └── publicOutputs{} → computed score values

performanceResultTables (89)
  ├── unitId → units[]
  └── resultSets[].primaryRanking[] → rankings (no advancement)
```

---

## 4. Event Metadata

| Field | Value |
|---|---|
| `name` | Hutt Valley Elementary Competition |
| `organizationId` | HVG (Hutt Valley Gymnastics) |
| `startDate` | 2025-05-24 |
| `endDate` | 2025-05-24 |
| `startsAt` | 2025-05-23T12:00:00Z |
| `stage` | completed |
| `isPublic` | true |
| `participantCount` | 287 |
| `timeZone` | Pacific/Auckland |
| `countryCode` | NZ |
| `currencyCode` | NZD |
| `venues` | [] (not specified) |

---

## 5. Competition Structure: Units & Sessions

### 5a. Units (9) — Competition Divisions

| # | Unit Name | Discipline | Levels | Individuals | Teams |
|---|---|---|---|---|---|
| 1 | WAG Step 1 Green | WAG | Step 1 (Green stream) | 35 | 6 |
| 2 | WAG Step 1 Yellow | WAG | Step 1 (Yellow stream) | 37 | 5 |
| 3 | WAG Step 2 Green | WAG | Step 2 (Green stream) | 39 | 6 |
| 4 | WAG Step 2 Yellow | WAG | Step 2 (Yellow stream) | 42 | 6 |
| 5 | WAG Step 3 | WAG | Step 3 | 41 | 7 |
| 6 | WAG Step 4 | WAG | Step 4 | 40 | 6 |
| 7 | MAG Level 1 | MAG | Level 1 | 13 | 3 |
| 8 | MAG Level 2 | MAG | Level 2 | 25 | 5 |
| 9 | MAG Level 3 | MAG | Level 3 | 11 | 0 |

This is an **elementary-level competition** — WAG caps at Step 4 (no Step 5+ or JI/SI), MAG caps at Level 3 (no Level 4+ or U16/U18/SO).

### 5b. WAG Apparatus

All WAG steps use 4 apparatus: **VT, UB, BB, FX** — single vault pass (no two-vault steps at this level).

### 5c. MAG Apparatus

All MAG levels use 6 apparatus: **FX, PH, SR, VT, PB, HB** — single pass per apparatus.

### 5d. WAG Streams

Steps 1 and 2 are split into two parallel streams (Green and Yellow), giving separate competitions for different age/ability groups within the same step. Steps 3 and 4 have a single stream each.

---

## 6. Session Map — Single Day (8 Sessions)

| Order | Session Name | Units | Individuals |
|---|---|---|---|
| 0 | MAG Session 3 | MAG Level 1 + Level 3 | 24 |
| 1 | MAG Session 4 | MAG Level 2 | 25 |
| 2 | WAG Session 1 Green | WAG Step 1 Green | 35 |
| 3 | WAG Session 1 Yellow | WAG Step 1 Yellow | 37 |
| 4 | WAG Session 2 Green | WAG Step 2 Green | 39 |
| 5 | WAG Session 2 Yellow | WAG Step 2 Yellow | 42 |
| 6 | WAG Session 3 | WAG Step 3 | 41 |
| 7 | WAG Session 4 | WAG Step 4 | 40 |

MAG sessions run first (orders 0-1), followed by WAG sessions (orders 2-7). Some sessions bundle multiple units (MAG Session 3 combines Level 1 and Level 3).

---

## 7. WAG vs MAG Comparison

| Aspect | WAG | MAG |
|---|---|---|
| Levels | Step 1-4 (Green/Yellow streams for 1-2) | Level 1-3 |
| Apparatus | VT, UB, BB, FX (4) | FX, PH, SR, VT, PB, HB (6) |
| Two-vault steps | None | N/A |
| Divisions | Under / Over (within each level) | None (single division) |
| Largest unit | Step 2 Yellow (42 indiv) | Level 2 (25 indiv) |
| Smallest unit | Step 1 Green (35 indiv) | Level 3 (11 indiv) |
| Team scoring | Yes (all 6 units have teams) | Level 1-2 have teams; Level 3 has 0 |
| Total individuals | 234 | 49 |
| Total teams | 36 | 8 |

### Apparatus by Discipline

```
WAG: VT (Vault) → UB (Uneven Bars) → BB (Balance Beam) → FX (Floor Exercise)
MAG: FX (Floor Exercise) → PH (Pommell Horse) → SR (Still Rings) → VT (Vault) → PB (Parallel Bars) → HB (Horizontal Bar)
```

### Competitive Level Progression

```
WAG:  Step 1 < Step 2 < Step 3 < Step 4
MAG:  Level 1 < Level 2 < Level 3
```

---

## 8. Performance Individuals (283)

### Entity Structure

```
performanceIndividual {
  _id:              ObjectId
  participantId:    ObjectId    → eventParticipants._id
  eventId:          ObjectId    → events._id
  unitId:           ObjectId    → units._id
  tags:             []          (unused in this file)
  resultTableConfigs[]
    ├── resultTableId           → performanceResultTables.resultTableId
    ├── tieBreaker              numeric
    ├── hasOptedOutAdvancing    bool
    └── eventIdsOptedOut        []
}
```

### Participant-to-Individual Mapping

- **287** eventParticipants (registered)
- **283** performanceIndividuals (competed)
- **4** participants (1.4%) registered but have no performance individual record

Each participant maps to exactly **1** performance individual within a single unit.

---

## 9. Performance Teams (44)

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

| Unit | Teams |
|---|---|
| WAG Step 3 | 7 |
| WAG Step 1 Green | 6 |
| WAG Step 2 Green | 6 |
| WAG Step 2 Yellow | 6 |
| WAG Step 4 | 6 |
| WAG Step 1 Yellow | 5 |
| MAG Level 2 | 5 |
| MAG Level 1 | 3 |
| MAG Level 3 | 0 |

---

## 10. Result Tables (89)

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
    ├── secondaryRanking[] (optional apparatus sub-rankings)
    └── tertiaryRanking[] (optional)
  isPublic:               bool
  — NO advancingIds / qualifierIds / reserveIds —
}
```

### 10b. Result Table Types by Set Count

| Result Sets | Meaning | Tables | Units |
|---|---|---|---|
| **1 set** | Single ranking (individual apparatus) | 66 | All units |
| **5 sets** | 4 apparatus + 1 allAround (WAG) | 18 | WAG Steps 1-4 |
| **7 sets** | 6 apparatus + 1 allAround (MAG) | 5 | MAG Levels 1-2 |

### 10c. Result Tables per Unit

| Unit | Tables | With Advancement |
|---|---|---|
| WAG Step 1 Green | 11 | 0 |
| WAG Step 1 Yellow | 11 | 0 |
| WAG Step 2 Green | 11 | 0 |
| WAG Step 2 Yellow | 11 | 0 |
| WAG Step 3 | 11 | 0 |
| WAG Step 4 | 11 | 0 |
| MAG Level 1 | 8 | 0 |
| MAG Level 2 | 8 | 0 |
| MAG Level 3 | 7 | 0 |

**No advancement** — 0 of 89 result tables have advancing/qualifier/reserve IDs. This is a single-round elementary competition with no finals pipeline.

---

## 11. Scoring System — Node-Tree Architecture

### 11a. Performance Rules (9)

Each unit has one rule set. All use `"FIG 2022/2024"`:

| Units | Rule Name |
|---|---|
| All 6 WAG units | WAG FIG 2022/2024 |
| All 3 MAG units | MAG FIG 2022/2024 |

### 11b. Score Node-Tree Inputs

Each rule contains a `nodeTree` with an `interface` defining scoring inputs by opaque IDs:

| Input ID (example) | Input Name | Type |
|---|---|---|
| `le0rUqc1ceGjtXMrGXiMj` | Did Not Start | Boolean |
| `_MODOUq-o1V1wLzL2Aj3O` | Zero | Boolean |
| `JG0d3BMAIMsrXdBz8DHhS` | Difficulty | Float |
| `-cnPQ_JmDootoDhzJT_yS` | Execution Deductions | Table (Float) |
| `tzx_PSRegq5RnsovMjaba` | Neutral Deductions | Float |

**Note:** The specific opaque ID strings differ from those in `csg-classic_2025.json`. Each export generates its own unique IDs, but the input structure (5 fields: DNS, Zero, Difficulty, Execution Deductions, Neutral Deductions) is identical.

### 11c. Performance Scores (1230)

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

The `publicOutputs` dictionary contains computed values keyed by node-tree output IDs. From the data, the keys consistently map to these fields:

```
publicOutputs example:
{
  "v0aGeEnA6SXmt13iSBAym": 13.8,     ← finalScore
  "jeRPs0cKQ2YNbfDgaZtjM": 5,        ← difficultyScore
  "y5_hmc2PRHunl4HQdfeix": 8.8,      ← executionScore
  "LdArky7UJhYPNHPIKR4Cm": 0         ← neutral deductions
}
```

These output IDs are unique to this export and differ from the input IDs found in `performanceRules`. The output IDs must be cross-referenced against the rule set's node tree outputs (not exported in detail) to map to field names.

---

## 12. Organizations (9 Clubs)

Local clubs from the lower North Island:

| Code | Name | Participants |
|---|---|---|
| HVG | Hutt Valley Gymnastics | 64 |
| MAN | Manawatu Gymnastics | 38 |
| KAP | Kapiti Gymnastics | 35 |
| TWI | Twisters Gymnastics | 34 |
| RIM | Rimutaka Gymnastics | 31 |
| LEV | Levin Gymnastics | 28 |
| ONS | Onslow Gymnastics | 23 |
| HCG | Harbour City Gymnastics | 20 |
| CAP | Capital Gymnastics | 14 |

---

## 13. Data Flow

```
Event (single day — May 24, 2025)
  │
  ├── 9 units: WAG Steps 1-4 (6 units) + MAG Levels 1-3 (3 units)
  │
  ├── 8 sessions: 2 MAG + 6 WAG
  │     └── performanceSessionGroups (32) + Rotations (144)
  │
  ├── 287 eventParticipants
  │     └── 283 performanceIndividuals
  │           ├── unit assignment
  │           ├── resultTableConfigs → result tables
  │           └── memberRefs in teams
  │
  ├── 1230 performanceScores
  │     ├── per individual per apparatus pass
  │     ├── scored via performanceRules (WAG/MAG FIG 2022/2024)
  │     └── outputs: finalScore, difficulty, execution, deductions
  │
  └── 89 performanceResultTables
        ├── 66 single-set tables (apparatus rankings)
        ├── 18 five-set tables (WAG: 4 apparatus + AA)
        ├── 5 seven-set tables (MAG: 6 apparatus + AA)
        └── 0 advancement tables (no finals)
```

---

## 14. Notable Observations

- **Elementary-level competition only**: All levels are introductory. WAG caps at Step 4 (no multi-vault steps, no international levels). MAG caps at Level 3 (no advanced levels, no U16/U18/SO).
- **No qualification or finals**: 0 of 89 result tables have advancement IDs. Every unit has a single round of competition with no progression pipeline.
- **No session folders**: Unlike `csg-classic_2025.json`, the `sessionFolders` array is empty — discipline grouping is implicit in session/unit names rather than explicit folders.
- **MAG Level 3 has no teams**: 11 individuals compete individually only, with no team scoring.
- **WAG stream system**: Steps 1 and 2 are split into Green and Yellow streams — distinct parallel competitions within the same step level. Steps 3 and 4 have a single stream each.
- **MAG sessions first**: MAG sessions run first (orders 0-1) followed by WAG (orders 2-7) on the same day.
- **MAG Session 3 bundles two levels**: Level 1 and Level 3 share a single session (24 individuals), while Level 2 has its own session (25 individuals).
- **All single vault**: No two-vault steps exist at this elementary level — every apparatus has exactly 1 pass.
- **4 participants (1.4%)** registered but never appeared in a performance individual — they did not compete.
- **Score output IDs differ from csg-classic**: The opaque keys in `publicOutputs` are unique to this export (e.g. `v0aGeEnA6SXmt13iSBAym` vs csg's `JnPzDdSPnQabVqIxX570A`), but the output structure (finalScore, difficultyScore, executionScore, deductions) is identical.
- **Code of points**: All units use FIG 2022/2024 — the same rule set applies to both WAG and MAG at elementary levels.
- **Same event, different format**: This file represents the same competition found in the old-format `hv-elem-25.json` under `data-collection/JSON 2025/quar/`, but exported in the newer flat reference-based schema.