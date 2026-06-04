# hve-2026.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | HVG Elementary Competition 2026 |
| **Date** | 2026-05-23 (single day) |
| **Sport** | GYMNASTICS (Artistic) |
| **Disciplines** | WAG + MAG |
| **Scope** | PUBLIC |
| **Host Organization** | Hutt Valley Gymnastics (HVG) |
| **Participants** | 271 (all competed) |
| **Organizations (Clubs)** | 9 |
| **Units** | 11 |
| **Sessions** | 10 |
| **Performance Individuals** | 271 |
| **Performance Scores** | 1146 |
| **Performance Result Tables** | 112 |
| **Performance Teams** | 41 |
| **Performance Rules** | 11 |
| **File size** | ~6.9 MB (minified JSON, single line) |

---

## 2. Data Model Overview

This file uses the flat reference-based `performance*` model with 22 top-level keys. Entities link to each other via `eventId`, `unitId`, `sessionId`, `participantId`, and `entityId` fields.

### Top-Level Keys

```
hve-2026.json
│
├── events:                          [ Event ] (1)
├── eventOfficials:                  [] (0)
├── eventOrganizations:              [ Organization ] (9)
├── eventParticipants:               [ Participant ] (271)
├── performanceGroups:               [] (0)
├── performanceIndividuals:          [ Individual ] (271)
├── performanceJudgingPanels:        [] (0)
├── performanceRecorders:            [] (0)
├── performanceResultTables:         [ ResultTable ] (112)
├── performanceRules:                [ RuleSet ] (11)
├── performanceScores:               [ Score ] (1146)
├── performanceSessionGroups:        [ SessionGroup ] (37)
├── performanceSessionRotations:     [ Rotation ] (158)
├── performanceTeams:                [ Team ] (41)
├── products:                        [] (0)
├── scoreboards:                     [] (0)
├── sessions:                        [ Session ] (10)
├── sessionFolders:                  [] (0)
├── shortUrls:                       [ ShortUrl ] (11)
├── transactions:                    [] (0)
├── units:                           [ Unit ] (11)
└── unitFolders:                     [] (0)
```

---

## 3. Entity Relationship Diagram

```
events (1)
  │
  ├── units[] (11)
  │     ├── 3 MAG units (Levels 1-3)
  │     ├── 8 WAG units (Steps 1-4, two streams each)
  │     ├── performanceRules[]
  │     ├── performanceResultTables[] (no advancement)
  │     ├── performanceIndividuals[] → eventParticipants[]
  │     └── performanceTeams[]
  │
  ├── sessions[] (10)
  │     ├── 2 MAG sessions → orders 0-1
  │     ├── 8 WAG sessions → orders 2-9 (one per stream per step)
  │     ├── unitIds[] → units[]
  │     ├── performanceSessionGroups[] (37)
  │     └── performanceSessionRotations[] (158)
  │
  └── eventParticipants (271)
        └── performanceIndividuals (271)
              ├── 1-to-1 mapping (all compete)
              ├── 0 multi-unit entries
              ├── resultTableConfigs[] → performanceResultTables[]
              └── performanceScores[] (1146)

performanceScores (1146)
  ├── entityId → performanceIndividuals[]
  ├── unitScoreId → performanceRules[].scores[].id
  └── publicOutputs{} → computed score values (4 keys)

performanceResultTables (112)
  ├── unitId → units[]
  └── resultSets[].primaryRanking[] → rankings (no advancement)
```

---

## 4. Event Metadata

| Field | Value |
|---|---|
| `name` | HVG Elementary Competition 2026 |
| `organizationId` | HVG (Hutt Valley Gymnastics) |
| `startDate` | 2026-05-23 |
| `endDate` | 2026-05-23 |
| `startsAt` | 2026-05-22T12:00:00Z |
| `stage` | completed |
| `isPublic` | true |
| `participantCount` | 271 |
| `timeZone` | Pacific/Auckland |
| `countryCode` | NZ |
| `currencyCode` | NZD |
| `venues` | [] (not specified) |

---

## 5. Competition Structure: Units & Sessions

### 5a. Units (11)

**MAG — 3 units (all single-stream):**

| # | Unit Name | Individuals | Teams | Level |
|---|---|---|---|---|
| 1 | MAG Level 1 | 12 | 2 | 1 |
| 2 | MAG Level 2 | 7 | 2 | 2 |
| 3 | MAG Level 3 | 12 | 2 | 3 |

**WAG — 8 units (Steps 1-4, each with Green/Yellow streams):**

| # | Unit Name | Individuals | Teams | Step | Stream |
|---|---|---|---|---|---|
| 4 | WAG Step 1 Green | 31 | 4 | 1 | Green |
| 5 | WAG Step 1 Yellow | 29 | 3 | 1 | Yellow |
| 6 | WAG Step 2 Green | 36 | 4 | 2 | Green |
| 7 | WAG Step 2 Yellow | 35 | 6 | 2 | Yellow |
| 8 | WAG Step 3 Green | 30 | 4 | 3 | Green |
| 9 | WAG Step 3 Yellow | 32 | 5 | 3 | Yellow |
| 10 | WAG Step 4 Green | 24 | 5 | 4 | Green |
| 11 | WAG Step 4 Yellow | 23 | 4 | 4 | Yellow |

### 5b. Discipline Totals

| Discipline | Units | Individuals | Teams |
|---|---|---|---|
| MAG | 3 | 31 (11.4%) | 6 |
| WAG | 8 | 240 (88.6%) | 35 |
| **Total** | **11** | **271** | **41** |

### 5c. Apparatus

**WAG:** VT, UB, BB, FX (4) — all single vault
**MAG:** FX, PH, SR, VT, PB, HB (6) — all single pass

### 5d. Sessions (10)

| Order | Session | Units | Individuals |
|---|---|---|---|
| 0 | MAG Session 1 | MAG Level 1 | 12 |
| 1 | MAG Session 2 | MAG Level 2 + Level 3 | 19 |
| 2 | WAG Session 1 Green | WAG Step 1 Green | 31 |
| 3 | WAG Session 1 Yellow | WAG Step 1 Yellow | 29 |
| 4 | WAG Session 2 Green | WAG Step 2 Green | 36 |
| 5 | WAG Session 2 Yellow | WAG Step 2 Yellow | 35 |
| 6 | WAG Session 3 Green | WAG Step 3 Green | 30 |
| 7 | WAG Session 3 Yellow | WAG Step 3 Yellow | 32 |
| 8 | WAG Session 4 Green | WAG Step 4 Green | 24 |
| 9 | WAG Session 4 Yellow | WAG Step 4 Yellow | 23 |

MAG sessions run first (orders 0-1), followed by WAG sessions (orders 2-9) — one session per stream per step. MAG Session 2 bundles Level 2 and Level 3 together.

---

## 6. Changes from the 2025 Edition

This file is the 2026 edition of the same competition found in `hvg-elementary_2025.json`. Notable differences:

| Aspect | 2025 (`hvg-elementary_2025.json`) | 2026 (`hve-2026.json`) |
|---|---|---|
| **Date** | 2025-05-24 | 2026-05-23 |
| **Participants** | 287 (283 competed) | 271 (all competed) |
| **Units** | 9 | 11 |
| **Steps 3-4 format** | Single stream each | Split into Green + Yellow streams |
| **MAG Level 3 teams** | 0 teams | 2 teams |
| **MAG units** | 3 (L1, L2, L3) | 3 (L1, L2, L3) — same |
| **Rule names** | "WAG FIG 2022/2024" / "MAG FIG 2022/2024" | "Gymnastics Rules" (generic) |
| **Sessions** | 8 | 10 |
| **Total scores** | 1230 | 1146 |
| **Result tables** | 89 | 112 |
| **Teams** | 44 | 41 |
| **DNS participants** | 4 (1.4%) | 0 |

The 2026 edition adds colour streams for Steps 3 and 4 (matching the existing pattern for Steps 1-2), bringing the unit count from 9 to 11. MAG Level 3 gains teams (2 teams vs 0 in 2025).

---

## 7. WAG vs MAG Comparison

| Aspect | WAG | MAG |
|---|---|---|
| Levels | Step 1-4 | Level 1-3 |
| Streams | Green + Yellow (all steps) | Single stream (all levels) |
| Apparatus | VT, UB, BB, FX (4) | FX, PH, SR, VT, PB, HB (6) |
| Two-vault | None | N/A |
| Largest unit | Step 2 Green (36 indiv) | Level 1 and 3 (12 each) |
| Smallest unit | Step 4 Yellow (23 indiv) | Level 2 (7 indiv) |
| Team scoring | Yes (all units) | Yes (all units) |
| Total individuals | 240 | 31 |
| Total teams | 35 | 6 |

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

## 8. Performance Individuals (271)

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

- **271** eventParticipants (registered)
- **271** performanceIndividuals (all competed)
- **0** participants not in individuals
- **0** multi-unit participants

1-to-1 mapping with full attendance.

---

## 9. Performance Teams (41)

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
| WAG Step 2 Yellow | 6 |
| WAG Step 3 Yellow | 5 |
| WAG Step 4 Green | 5 |
| WAG Step 1 Green | 4 |
| WAG Step 2 Green | 4 |
| WAG Step 3 Green | 4 |
| WAG Step 4 Yellow | 4 |
| WAG Step 1 Yellow | 3 |
| MAG Level 1 | 2 |
| MAG Level 2 | 2 |
| MAG Level 3 | 2 |

Every unit has at least 1 team — unlike the 2025 edition where MAG Level 3 had 0 teams.

---

## 10. Result Tables (112)

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
| **1 set** | Single ranking (individual apparatus) | 82 |
| **5 sets** | 4 apparatus + 1 allAround (WAG) | 24 |
| **7 sets** | 6 apparatus + 1 allAround (MAG) | 6 |

### 10c. Result Tables per Unit

| Unit | Tables | With Advancement |
|---|---|---|
| Each WAG unit (8 units) | 11 | 0 |
| Each MAG unit (3 units) | 8 | 0 |

**No advancement** — 0 of 112 result tables have advancing/qualifier/reserve IDs.

---

## 11. Scoring System — Node-Tree Architecture

### 11a. Performance Rules (11)

Each unit has one rule set. All 11 use `"Gymnastics Rules"` — a generic name rather than a specific FIG code reference:

| Units | Rule Name |
|---|---|
| All 11 units | Gymnastics Rules |

### 11b. Score Node-Tree Inputs

Each rule has a `nodeTree` with 5 input fields (IDs unique to this export):

| Input ID (example) | Input Name | Type |
|---|---|---|
| `qFWSxzmc_gDoLBn5f8KDw` | Did Not Start | Boolean |
| `9Cmla0sXwunnn6xK_R8Hp` | Zero | Boolean |
| `m2CBIcIE2gYwlN_kymaW8` | Difficulty | Float |
| `aykBnXrYKO0jVkD-RIpRz` | Execution Deductions | Table (Float) |
| `bkYiH-B0LoFT6eRrYVOrh` | Neutral Deductions | Float |

The structure is identical to other files but the rule name is generic rather than FIG-specific.

### 11c. Performance Scores (1146)

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
  "AL0UXdqvms4PN3vcGCnBW": 10.066,   ← finalScore
  "JmlSsaETyneC_N87we-WB": 2,        ← difficultyScore
  "_vapglA3t7xNP4lJy7Z1_": 8.066,    ← executionScore
  "Tk7Yps7JW_j-00IhaQbZJ": 0         ← neutral deductions
}
```

Score type values found: numeric only (NORMAL scores). No DNS or ZERO scores observed in the sampled data.

---

## 12. Organizations — 9 Clubs

Same club set as the 2025 Hutt Valley Elementary, with slightly varied counts:

| Code | Name | Participants |
|---|---|---|
| HVG | Hutt Valley Gymnastics | 69 |
| MAN | Manawatu Gymnastics | 42 |
| RIM | Rimutaka Gymnastics | 32 |
| CAP | Capital Gymnastics | 30 |
| ONS | Onslow Gymnastics | 26 |
| TWI | Twisters Gymnastics | 25 |
| KAP | Kapiti Gymnastics | 24 |
| HAR | Harbour City Gymnastics | 14 |
| LEV | Levin Gymnastics | 9 |

---

## 13. Data Flow

```
Event (single day — May 23, 2026)
  │
  ├── 11 units: 8 WAG (Steps 1-4, two streams) + 3 MAG (Levels 1-3)
  │
  ├── 10 sessions: 2 MAG + 8 WAG (one per stream per step)
  │     └── performanceSessionGroups (37) + Rotations (158)
  │
  ├── 271 eventParticipants → 271 performanceIndividuals (1:1)
  │     ├── unit assignment
  │     ├── resultTableConfigs → result tables
  │     └── memberRefs in teams
  │
  ├── 1146 performanceScores
  │     ├── per individual per apparatus pass
  │     ├── no multi-pass events (all single vault)
  │     ├── scored via "Gymnastics Rules"
  │     └── outputs: finalScore, difficulty, execution, deductions
  │
  └── 112 performanceResultTables
        ├── 82 single-set tables (apparatus rankings)
        ├── 24 five-set tables (WAG: 4 apparatus + AA)
        ├── 6 seven-set tables (MAG: 6 apparatus + AA)
        └── 0 advancement tables (no finals)
```

---

## 14. Notable Observations

- **2026 edition of the Hutt Valley Elementary**: This is the same competition as `hvg-elementary_2025.json` but updated for the 2026 season with some structural changes.
- **Steps 3 and 4 now have colour streams**: The 2025 edition used single-stream units for Steps 3 and 4. The 2026 edition splits them into Green and Yellow streams, matching the existing pattern for Steps 1-2. This increases the unit count from 9 to 11.
- **MAG Level 3 now has teams**: The 2025 edition had 0 teams for Level 3; the 2026 edition has 2 teams.
- **Generic rule names**: All 11 rule sets use `"Gymnastics Rules"` rather than the FIG-specific naming (`"WAG FIG 2022/2024"` / `"MAG FIG 2022/2024"`) used in the 2025 edition. The input structure (5 fields: DNS, Zero, Difficulty, Execution Deductions, Neutral Deductions) is identical.
- **No multi-pass events**: All apparatus uses a single pass — this is an elementary-level competition with no two-vault requirements.
- **No advancement pipeline**: 0 of 112 result tables have advancing/qualifier/reserve IDs.
- **No session folders**: The `sessionFolders` array is empty — discipline grouping is implicit in session/unit names.
- **All participants competed**: 0 registered-but-DNS participants — 100% attendance.
- **No multi-unit participants**: 1-to-1 mapping across all 271 participants.
- **MAG has fewer participants**: 31 MAG individuals (11.4%) vs 240 WAG (88.6%). MAG Level 2 is the smallest unit with only 7 individuals.
- **Score output consistency**: All scores have 4 output keys (finalScore, difficultyScore, executionScore, deductions) with no 5-key variants or DNS values observed in samples.
- **Largest unit**: WAG Step 2 Green (36 individuals). Smallest: MAG Level 2 (7 individuals).