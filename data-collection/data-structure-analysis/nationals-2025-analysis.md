# nationals-2025.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | 2025 XP Gymnastics Nationals - Artistic |
| **Dates** | 2025-09-23 to 2025-09-27 (6 days) |
| **Sport** | GYMNASTICS (Artistic) |
| **Disciplines** | WAG + MAG |
| **Scope** | PUBLIC |
| **Host Organization** | XP Gymnastics |
| **Participants** | 439 (all competed) |
| **Organizations (Regions)** | 15 |
| **Units** | 17 |
| **Sessions** | 26 |
| **Performance Individuals** | 439 |
| **Performance Scores** | 3301 |
| **Performance Result Tables** | 209 (73 with advancement) |
| **Performance Teams** | 69 |
| **Performance Rules** | 17 |
| **File size** | ~14.4 MB (minified JSON, single line) |

---

## 2. Data Model Overview

This file uses the flat reference-based `performance*` model with 22 top-level keys. Entities link to each other via `eventId`, `unitId`, `sessionId`, `participantId`, and `entityId` fields.

### Top-Level Keys

```
nationals-2025.json
│
├── events:                          [ Event ] (1)
├── eventOfficials:                  [] (0)
├── eventOrganizations:              [ Organization ] (15)
├── eventParticipants:               [ Participant ] (439)
├── performanceGroups:               [] (0)
├── performanceIndividuals:          [ Individual ] (439)
├── performanceJudgingPanels:        [] (0)
├── performanceRecorders:            [] (0)
├── performanceResultTables:         [ ResultTable ] (209)
├── performanceRules:                [ RuleSet ] (17)
├── performanceScores:               [ Score ] (3301)
├── performanceSessionGroups:        [ SessionGroup ] (89)
├── performanceSessionRotations:     [ Rotation ] (452)
├── performanceTeams:                [ Team ] (69)
├── products:                        [] (0)
├── scoreboards:                     [] (0)
├── sessions:                        [ Session ] (26)
├── sessionFolders:                  [ Folder ] (2)
├── shortUrls:                       [ ShortUrl ] (28)
├── transactions:                    [] (0)
├── units:                           [ Unit ] (17)
└── unitFolders:                     [ Folder ] (2) — unitIds arrays are empty
```

---

## 3. Entity Relationship Diagram

```
events (1)
  │
  ├── sessionFolders (2)
  │     ├── Men's Artistic Gymnastics
  │     └── Women's Artistic Gymnastics
  │
  ├── unitFolders (2) — empty unitIds
  │     ├── Men's Artistic Gymnastics
  │     └── Women's Artistic Gymnastics
  │
  ├── units[] (17)
  │     ├── 9 MAG units (Levels 4-9, U16, U18, Senior Open)
  │     ├── 8 WAG units (Steps 5-10, JI, SI)
  │     ├── performanceRules[]
  │     ├── performanceResultTables[] (73 with advancement)
  │     ├── performanceIndividuals[] → eventParticipants[]
  │     └── performanceTeams[]
  │
  ├── sessions[] (26)
  │     ├── 15 Day 1 qualification sessions
  │     ├── 11 Day 2 finals sessions
  │     ├── unitIds[] → units[]
  │     ├── performanceSessionGroups[] (89)
  │     └── performanceSessionRotations[] (452)
  │
  └── eventParticipants (439)
        └── performanceIndividuals (439)
              ├── 1-to-1 mapping (all participants compete)
              ├── 0 multi-unit entries
              ├── resultTableConfigs[] → performanceResultTables[]
              └── performanceScores[] (3301)

performanceScores (3301)
  ├── entityId → performanceIndividuals[]
  ├── unitScoreId → performanceRules[].scores[].id
  └── publicOutputs{} → computed score values (4 or 5 keys)

performanceResultTables (209)
  ├── unitId → units[]
  ├── resultSets[].primaryRanking[] → rankings
  └── 73 tables with advancingIds[] → qualification→finals pipeline
```

---

## 4. Event Metadata

| Field | Value |
|---|---|
| `name` | 2025 XP Gymnastics Nationals - Artistic |
| `organizationId` | XP Gymnastics |
| `startDate` | 2025-09-23 |
| `endDate` | 2025-09-27 |
| `startsAt` | 2025-09-22T12:00:00Z |
| `stage` | completed |
| `isPublic` | true |
| `participantCount` | 439 |
| `timeZone` | Pacific/Auckland |
| `countryCode` | NZ |
| `currencyCode` | NZD |
| `venues` | [] (not specified) |

---

## 5. Competition Structure: Folders, Units & Sessions

### 5a. Session Folders

```
sessionFolders[0]: "Men's Artistic Gymnastics"
sessionFolders[1]: "Women's Artistic Gymnastics"
```

### 5b. Units (17)

**MAG — 9 units:**

| # | Unit Name | Individuals | Teams | Level |
|---|---|---|---|---|
| 1 | Level 4 | 39 | 9 | L4 |
| 2 | Level 5 | 18 | 3 | L5 |
| 3 | Level 6 | 13 | 2 | L6 |
| 4 | Level 7 | 21 | 3 | L7 |
| 5 | Level 8 | 11 | 1 | L8 |
| 6 | Level 9 | 13 | 0 | L9 |
| 7 | U16 | 2 | 0 | Under 16 |
| 8 | U18 | 6 | 0 | Under 18 |
| 9 | Senior Open | 9 | 0 | Senior Open |

**WAG — 8 units:**

| # | Unit Name | Individuals | Teams | Level |
|---|---|---|---|---|
| 10 | STEP 5 | 72 | 13 | Step 5 |
| 11 | STEP 6 | 72 | 12 | Step 6 |
| 12 | STEP 7 | 73 | 16 | Step 7 |
| 13 | STEP 8 | 43 | 7 | Step 8 |
| 14 | STEP 9 | 21 | 2 | Step 9 |
| 15 | STEP 10 | 12 | 1 | Step 10 |
| 16 | Junior International | 2 | 0 | JI |
| 17 | Senior International | 12 | 0 | SI |

### 5c. Unit Totals

| Discipline | Units | Individuals | Teams |
|---|---|---|---|
| MAG | 9 | 146 (33.2%) | 18 |
| WAG | 8 | 293 (66.8%) | 51 |
| **Total** | **17** | **439** | **69** |

### 5d. Apparatus

**WAG:** VT, UB, BB, FX (4)
**MAG:** FX, PH, SR, VT, PB, HB (6)

---

## 6. Two-Day Qualification & Finals Format

This is a **national championship** with a qualification → finals structure, unlike the single-round competitions in the dataset.

### Day 1 — Qualification (15 sessions)

| Order | Session | Units | Individuals |
|---|---|---|---|
| 0 | Session 5: Level 4 Day 1 | Level 4 | 39 |
| 0 | Session 1: STEP 5 Day 1 | STEP 5 | 35 |
| 1 | Session 6: Level 5 Day 1 | Level 5 | 18 |
| 1 | Session 2: STEP 5 Day 1 | STEP 5 | 37 |
| 2 | Session 7: Level 6/U16/U18 Day 1 | Level 6, U16, U18 | 20 |
| 2 | Session 4: STEP 8 Day 1 | STEP 8 | 43 |
| 3 | Session 8: Level 7 Day 1 | Level 7 | 21 |
| 3 | Session 5: STEP 6 Day 1 | STEP 6 | 36 |
| 4 | Session 11: SO Day 1 | Senior Open | 9 |
| 4 | Session 6: STEP 6 Day 1 | STEP 6 | 36 |
| 5 | Session 12: Level 8/9 Day 1 | Level 8, Level 9 | 24 |
| 5 | Session 7: STEP 7 Day 1 | STEP 7 | 36 |
| 6 | Session 8: STEP 7 Day 1 | STEP 7 | 37 |
| 9 | Session 11: STEP 10/JI/SI Day 1 | STEP 10, JI, SI | 26 |
| 10 | Session 12: STEP 9 Day 1 | STEP 9 | 21 |

### Day 2 — Finals (11 sessions)

| Order | Session | Units | Individuals |
|---|---|---|---|
| 6 | Session 13: Level 5/6 Day 2 | Level 5, Level 6 | 31 |
| 7 | Session 14: Level 4 Day 2 | Level 4 | 24 |
| 7 | Session 9: STEP 5 Day 2 | STEP 5 | 32 |
| 8 | Session 15: Level 7 Day 2 | Level 7 | 21 |
| 8 | Session 10: STEP 8 Day 2 | STEP 8 | 43 |
| 9 | Session 17: Level 8/9 Day 2 | Level 8, Level 9 | 24 |
| 10 | Session 19: U16/U18/SO Day 2 | U16, U18, Senior Open | 16 |
| 11 | Session 13: STEP 6 Day 2 | STEP 6 | 32 |
| 12 | Session 14: STEP 7 Day 2 | STEP 7 | 73 |
| 13 | Session 17: STEP 9/10 Day 2 | STEP 9, STEP 10 | 33 |
| 14 | Session 19: STEP JI/SI Day 2 | JI, SI | 14 |

---

## 7. Advancement Pipeline

**73 of 209** result tables have `advancingIds[]`, `qualifierIds[]`, and `reserveIds[]` — linking qualification round rankings to finals.

### Advancement Tables by Unit

| Unit | Advancement Tables | Notes |
|---|---|---|
| STEP 7 | 8 | All-around + per-apparatus advancement |
| STEP 8 | 8 | All-around + per-apparatus advancement |
| Level 7 | 6 | All-around + per-apparatus advancement |
| Level 8 | 6 | All-around + per-apparatus advancement |
| Level 9 | 6 | All-around + per-apparatus advancement |
| U16 | 6 | All-around + per-apparatus advancement |
| U18 | 6 | All-around + per-apparatus advancement |
| Senior Open | 6 | All-around + per-apparatus advancement |
| STEP 9 | 4 | Partial apparatus advancement |
| STEP 10 | 4 | Partial apparatus advancement |
| Junior International | 4 | Partial apparatus advancement |
| Senior International | 4 | Partial apparatus advancement |
| Level 4 | 1 | Single all-around qualification |
| Level 5 | 1 | Single all-around qualification |
| Level 6 | 1 | Single all-around qualification |
| STEP 5 | 1 | Single all-around qualification |
| STEP 6 | 1 | Single all-around qualification |

Lower levels (L4-6, STEP 5-6) have only 1 advancement table each — likely feeding all-around qualifiers to Day 2. Higher levels have 4-8 advancement tables, indicating per-apparatus qualification to finals.

---

## 8. Multi-Vault Apparatus

**56 multi-pass events** across 12 of 17 units — the most extensive two/multi-vault rules in the dataset.

| Unit | Multi-pass VT events | Max VT passes | Notes |
|---|---|---|---|
| Level 4 | 6 | 2 | |
| Level 5, Level 6 | — | — | (Part of L4-6 combined sessions) |
| Level 7, Level 8, Level 9 | — | — | (Single passes for most apparatus) |
| U16 | 6 | 2 | |
| U18 | 6 | **4** | Up to 4 vault passes |
| Senior Open | 6 | **4** | Up to 4 vault passes |
| STEP 5 | 4 | 2 | |
| STEP 6 | 4 | **4** | Up to 4 vault passes |
| STEP 7 | 4 | **4** | Up to 4 vault passes |
| STEP 8 | 4 | 2 | |
| STEP 9 | 4 | 2 | |
| STEP 10 | 4 | **4** | Up to 4 vault passes |
| Junior International | 4 | **4** | Up to 4 vault passes |
| Senior International | 4 | **4** | Up to 4 vault passes |

The highest number of multi-pass events is found in mid-level WAG (STEP 5-9 with 4 each) and high-level MAG (U16, U18, SO with 6 each). The maximum number of passes for a single VT event is **4**, found in U18, Senior Open, STEP 6, STEP 7, STEP 10, JI, and SI.

---

## 9. Performance Individuals (439)

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

- **439** eventParticipants (registered)
- **439** performanceIndividuals (all competed)
- **0** participants not in individuals
- **0** multi-unit participants (everyone in exactly 1 unit)

Unlike the Manawatu competition where gymnasts appeared in 2 units (AA Day 1 + Apparatus Day 2), the Nationals handles progression within a single unit through the qualification/advancement pipeline.

---

## 10. Performance Teams (69)

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
| STEP 7 | 16 |
| STEP 5 | 13 |
| STEP 6 | 12 |
| Level 4 | 9 |
| STEP 8 | 7 |
| Level 5 | 3 |
| Level 7 | 3 |
| Level 6 | 2 |
| STEP 9 | 2 |
| Level 8 | 1 |
| STEP 10 | 1 |

Level 9, U16, U18, Senior Open, Junior International, and Senior International have **0 teams** — highest levels compete individually only.

---

## 11. Result Tables (209)

### 11a. Structure

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
    ├── secondaryRanking[] (optional)
    └── tertiaryRanking[] (optional)
  advancingIds[]          (73 tables)
  qualifierIds[]          (73 tables)
  reserveIds[]            (73 tables)
  isPublic:               bool
  ...
}
```

### 11b. Result Table Types by Set Count

| Result Sets | Meaning | Tables |
|---|---|---|
| **1 set** | Single ranking (individual apparatus or qualifier list) | 170 |
| **5 sets** | 4 apparatus + 1 allAround (WAG) | 22 |
| **7 sets** | 6 apparatus + 1 allAround (MAG) | 17 |

### 11c. Result Tables per Unit

| Unit | Tables | With Advancement |
|---|---|---|
| STEP 7 | 19 | 8 |
| STEP 8 | 19 | 8 |
| Level 7 | 14 | 6 |
| Level 8 | 14 | 6 |
| STEP 6 | 14 | 1 |
| Level 9 | 13 | 6 |
| U16 | 13 | 6 |
| U18 | 13 | 6 |
| Senior Open | 13 | 6 |
| STEP 5 | 12 | 1 |
| STEP 9 | 10 | 4 |
| STEP 10 | 10 | 4 |
| Level 4 | 9 | 1 |
| Level 5 | 9 | 1 |
| Level 6 | 9 | 1 |
| Junior International | 9 | 4 |
| Senior International | 9 | 4 |

---

## 12. Scoring System — Node-Tree Architecture

### 12a. Performance Rules (17)

Each unit has one rule set:

| Units | Rule Name |
|---|---|
| MAG Level 4-9, U16, U18, Senior Open | MAG FIG 2022/2024 |
| WAG STEP 5-10, JI, SI | WAG FIG 2022/2024 |

### 12b. Score Node-Tree Inputs

Each rule has a `nodeTree` with 5 input fields (IDs unique to this export):

| Input ID (example) | Input Name | Type |
|---|---|---|
| `yzF0ms2R1pdm6lz_1hHr_` | Did Not Start | Boolean |
| `YeY7OICoLwToELh6ZVtlS` | Zero | Boolean |
| `UGpGIcJOKVEVkY5pUDyht` | Difficulty | Float |
| `4Wn2agItJeq1qmFyBEiXm` | Execution Deductions | Table (Float) |
| `2mOfDz-toKR_cz5KtBVuS` | Neutral Deductions | Float |

### 12c. Performance Scores (3301)

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

### 12d. Interpreting a Score

Scores in this file have either **4 or 5 output keys**:

```
4-key output (most scores):
{
  "4ybUr-8pTLNCp5KbyA0pS": 13.8,      ← finalScore
  "VOEIW3GWdPyq0EQ_OlzG_": 5,         ← difficultyScore
  "v592ml7cFAauSW7jGFPn-": 8.8,       ← executionScore
  "otElxQVRDn1FJCSCzaYiX": 0          ← neutral deductions
}

5-key output (some scores, often DNS or special cases):
{
  "_esbj05OhvMszMurAcnJK": "dns",     ← Did Not Start
  "EpoR7O_SsaZlM7oOPzEeT": 0,         ← Zero
  "XPFMR8TABbM_ZLp5JXeTb": 10,        ← Difficulty
  "fuADY6wjNQMV70uQVN0Zq": 0,         ← (deductions)
  "h2_mtVT7u65DtdmFzSAyz": "dns"      ← (additional field)
}
```

Score type values found: numeric (NORMAL), `"dns"` (Did Not Start), `0` (zero/not-applicable). The opaque output IDs are unique to this export and must be cross-referenced against the node-tree definition in the relevant `performanceRules`.

---

## 13. Organizations — 15 Regions

National-level competition organized by geographic region rather than club:

| Code | Name | Participants |
|---|---|---|
| CAN | Canterbury | 70 |
| WEL | Wellington | 66 |
| AUC | Auckland | 56 |
| WAI | Waikato | 35 |
| GMA | Gymsport Manukau | 36 |
| BOP | Bay of Plenty | 34 |
| HAR | Harbour | 31 |
| WAN | Wanganui / Manawatu | 25 |
| HBP | Hawkes Bay / Poverty Bay | 20 |
| OTA | Otago | 16 |
| TOP | Top of the South | 14 |
| SOU | Southland | 13 |
| NOR | Northland | 9 |
| TAR | Taranaki | 8 |
| AOR | Aorangi | 6 |

---

## 14. Data Flow

```
Event (6 days — Sep 23-27)
  │
  ├── sessionFolders: Men's / Women's Artistic Gymnastics
  │
  ├── 17 units: 9 MAG + 8 WAG
  │
  ├── 26 sessions
  │     ├── 15 Day 1 qualification rounds
  │     ├── 11 Day 2 finals rounds
  │     └── performanceSessionGroups (89) + Rotations (452)
  │
  ├── 439 eventParticipants → 439 performanceIndividuals (1:1)
  │     ├── each in exactly 1 unit
  │     ├── resultTableConfigs → result tables
  │     └── memberRefs in teams
  │
  ├── 3301 performanceScores
  │     ├── per individual per apparatus pass
  │     ├── 56 multi-pass VT events (up to 4 passes)
  │     ├── scored via FIG 2022/2024 rules
  │     └── outputs: finalScore, difficulty, execution, deductions
  │
  └── 209 performanceResultTables
        ├── 170 single-set tables (apparatus rankings)
        ├── 22 five-set tables (WAG: 4 apparatus + AA)
        ├── 17 seven-set tables (MAG: 6 apparatus + AA)
        └── 73 tables with advancement → finals pipeline
```

---

## 15. Notable Observations

- **National championship format**: This is the only file in the dataset with a qualification-to-finals pipeline (73 of 209 result tables have advancement IDs). Lower levels (L4-6, STEP 5-6) have 1 advancement table each; higher levels have 4-8.
- **Largest file**: At ~14.4 MB and 3301 scores, this is the biggest competition in the dataset — nearly double the next largest.
- **Both WAG and MAG in one file**: Unlike the discipline-specific files, this includes both with session folders (Men's / Women's Artistic Gymnastics).
- **56 multi-pass VT events**: The most extensive two-vault rules across the dataset. Up to **4 passes** for some apparatus at the highest levels (U18, Senior Open, Senior International, Junior International, STEP 6, STEP 7, STEP 10).
- **1:1 participant-to-individual mapping**: Every registered participant has exactly 1 performance individual. Unlike the Manawatu competition (where gymnasts appeared in 2 units), the Nationals handles Day 1→Day 2 progression through the qualification pipeline within a single unit.
- **All participants competed**: 0 registered-but-DNS participants — 100% attendance.
- **Regional organizations**: The 15 organizations are geographic regions (Canterbury, Wellington, Auckland, etc.) rather than individual clubs, reflecting the national-team selection format.
- **Top-heavy WAG**: 293 WAG individuals (66.8%) vs 146 MAG (33.2%) — WAG has more participants but only 8 units vs MAG's 9.
- **Highest levels have no teams**: Level 9, U16, U18, Senior Open, Junior International, and Senior International all have `teamCount: 0` — these are individual-only competitions.
- **Largest units by participation**: STEP 7 (73), STEP 5 (72), STEP 6 (72), followed by Level 4 (39).
- **Smallest units**: U16 (2 individuals), Junior International (2), U18 (6) — national-level categories have very limited participation.
- **Result tables per unit vary by level**: Advanced levels have more tables (19 for STEP 7-8) vs basic (9 for Level 4-6), reflecting per-apparatus qualification sets.
- **Score outputs can be 4 or 5 keys**: Most scores have 4 output keys (final, difficulty, execution, deductions). Some have a 5th key, likely an additional field for DNS/zero or bonus/penalty values.
- **Code of points**: All 17 units use FIG 2022/2024 (MAG or WAG variant).
- **Unit folders exist but are empty**: Both unit folder entries have empty `unitIds[]` arrays — the folder structure is defined but not populated with references.