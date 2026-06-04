# mgi-wag-2026.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | Manawatu WAG Opens 2026 |
| **Dates** | 2026-05-29 to 2026-06-01 (4 days) |
| **Sport** | GYMNASTICS (Artistic) |
| **Discipline** | WAG only |
| **Scope** | PUBLIC |
| **Host Organization** | Manawatu GymSports (MGI) |
| **Participants** | 445 registered, 443 competed |
| **Organizations (Clubs)** | 18 |
| **Units** | 29 |
| **Sessions** | 16 |
| **Performance Individuals** | 613 (443 unique participants, 170 in 2 units) |
| **Performance Scores** | 2607 |
| **Performance Result Tables** | 269 |
| **Performance Teams** | 65 |
| **Performance Rules** | 29 |
| **File size** | ~14.3 MB (minified JSON, single line) |

---

## 2. Data Model Overview

This file uses the flat reference-based `performance*` model with 22 top-level keys. Entities link to each other via `eventId`, `unitId`, `sessionId`, `participantId`, and `entityId` fields.

### Top-Level Keys

```
mgi-wag-2026.json
│
├── events:                          [ Event ] (1)
├── eventOfficials:                  [] (0)
├── eventOrganizations:              [ Organization ] (18)
├── eventParticipants:               [ Participant ] (445)
├── performanceGroups:               [] (0)
├── performanceIndividuals:          [ Individual ] (613)
├── performanceJudgingPanels:        [] (0)
├── performanceRecorders:            [] (0)
├── performanceResultTables:         [ ResultTable ] (269)
├── performanceRules:                [ RuleSet ] (29)
├── performanceScores:               [ Score ] (2607)
├── performanceSessionGroups:        [ SessionGroup ] (81)
├── performanceSessionRotations:     [ Rotation ] (329)
├── performanceTeams:                [ Team ] (65)
├── products:                        [] (0)
├── scoreboards:                     [] (0)
├── sessions:                        [ Session ] (16)
├── sessionFolders:                  [] (0)
├── shortUrls:                       [ ShortUrl ] (18)
├── transactions:                    [] (0)
├── units:                           [ Unit ] (29)
└── unitFolders:                     [] (0)
```

---

## 3. Entity Relationship Diagram

```
events (1)
  │
  ├── units[] (29)
  │     ├── 17 Day 1 AA units (Steps 1-10, Youth, JI, SI)
  │     ├── 12 Day 2 Apparatus units (Steps 5-10, Youth, JI, SI)
  │     ├── performanceRules[] ("Gymnastics Rules")
  │     ├── performanceResultTables[] (no advancement)
  │     ├── performanceIndividuals[] → eventParticipants[]
  │     └── performanceTeams[]
  │
  ├── sessions[] (16)
  │     ├── orders 0-10: Day 1 (AA units)
  │     ├── orders 11-15: Day 2 (Apparatus units)
  │     ├── unitIds[] → units[]
  │     ├── performanceSessionGroups[] (81)
  │     └── performanceSessionRotations[] (329)
  │
  └── eventParticipants (445)
        └── performanceIndividuals (613)
              ├── 273 participants in 1 unit (Day 1 only)
              ├── 170 participants in 2 units (Day 1 AA + Day 2 Apparatus)
              ├── 2 registered but did not compete
              ├── resultTableConfigs[] → performanceResultTables[]
              └── performanceScores[] (2607)

performanceScores (2607)
  ├── entityId → performanceIndividuals[]
  ├── unitScoreId → performanceRules[].scores[].id
  └── publicOutputs{} → computed score values

performanceResultTables (269)
  ├── unitId → units[]
  └── resultSets[].primaryRanking[] → rankings (no advancement)
```

---

## 4. Event Metadata

| Field | Value |
|---|---|
| `name` | Manawatu WAG Opens 2026 |
| `organizationId` | MGI (Manawatu GymSports) |
| `startDate` | 2026-05-29 |
| `endDate` | 2026-06-01 |
| `startsAt` | 2026-05-28T12:00:00Z |
| `stage` | completed |
| `isPublic` | true |
| `participantCount` | 445 |
| `timeZone` | Pacific/Auckland |
| `countryCode` | NZ |
| `currencyCode` | NZD |
| `venues` | [] (not specified) |

---

## 5. Two-Day Competition Model

This competition spans multiple days with two distinct round types:

| | Day 1 (Sessions 1-11) | Day 2 (Sessions 12-16) |
|---|---|---|
| **Focus** | AA, Apps and Teams | Apparatus only |
| **Steps** | 1-10, Youth, JI, SI | 5-10, Youth, JI, SI |
| **Units** | 17 AA units | 12 Apparatus units |
| **Sessions** | Orders 0-10 | Orders 11-15 |
| **Team scoring** | Steps 1-8 | No |
| **VT scoring** | Single or dual vault (per step rules) | Single or dual vault (per step rules) |

170 of 443 competing participants (38.2%) appear in **2 performance individuals** — one for Day 1 AA and one for Day 2 Apparatus.

---

## 6. Competition Structure: Units & Sessions

### 6a. Units (29)

**Day 1 — 17 AA units:**

| # | Unit Name | Individuals | Teams | Level |
|---|---|---|---|---|
| 1 | STEP 1 Green AA, Apps and Teams | 30 | 3 | 1 Green |
| 2 | STEP 1 Blue AA, Apps and Teams | 28 | 4 | 1 Blue |
| 3 | STEP 2 Blue (1st) AA, Apps and Teams | 23 | 4 | 2 Blue 1st |
| 4 | STEP 2 Green (1st) AA, Apps and Teams | 21 | 3 | 2 Green 1st |
| 5 | STEP 2 Green (2nd) AA, Apps and Teams | 20 | 3 | 2 Green 2nd |
| 6 | STEP 2 Blue (2nd) AA, Apps and Teams | 23 | 3 | 2 Blue 2nd |
| 7 | STEP 3 Blue AA, Apps and Teams | 31 | 4 | 3 Blue |
| 8 | STEP 3 Green AA, Apps and Teams | 35 | 5 | 3 Green |
| 9 | STEP 4 Blue AA, Apps and Teams | 30 | 5 | 4 Blue |
| 10 | STEP 4 Green AA, Apps and Teams | 32 | 5 | 4 Green |
| 11 | STEP 5 Green AA and Teams | 31 | 6 | 5 Green |
| 12 | STEP 5 Blue AA and Teams | 30 | 3 | 5 Blue |
| 13 | STEP 6 AA and Teams | 45 | 9 | 6 |
| 14 | STEP 7 AA and Teams | 29 | 4 | 7 |
| 15 | STEP 8 AA and Teams | 21 | 4 | 8 |
| 16 | STEP 9 AA | 4 | 0 | 9 |
| 17 | STEP 10 AA | 2 | 0 | 10 |
| 18 | Youth AA | 4 | 0 | Youth |
| 19 | Junior International AA | 1 | 0 | JI |
| 20 | Senior International AA | 3 | 0 | SI |

**Day 2 — 12 Apparatus units:**

| # | Unit Name | Individuals | Teams | Level |
|---|---|---|---|---|
| 21 | STEP 5 Day Two Apparatus | 61 | 0 | 5 |
| 22 | STEP 6 Day Two Apparatus | 45 | 0 | 6 |
| 23 | STEP 7 Day Two Apparatus | 29 | 0 | 7 |
| 24 | STEP 8 Day Two Apparatus | 21 | 0 | 8 |
| 25 | STEP 9 Day Two Apparatus | 4 | 0 | 9 |
| 26 | STEP 10 Apps Day Two | 2 | 0 | 10 |
| 27 | Youth Apps Day Two | 4 | 0 | Youth |
| 28 | Junior International Apps Day Two | 1 | 0 | JI |
| 29 | Senior International Apps Day Two | 3 | 0 | SI |

### 6b. Apparatus

All units use 4 WAG apparatus: **VT, UB, BB, FX**.

### 6c. WAG Step Progression

| Level | AA unit(s) | Apparatus unit | VT vaults | Streams | Teams |
|---|---|---|---|---|---|
| Step 1 | Green, Blue | — | 1 | Green / Blue | Yes |
| Step 2 | Blue 1st, Green 1st, Green 2nd, Blue 2nd | — | 1 | Blue+G (×2) | Yes |
| Step 3 | Blue, Green | — | 1 | Blue / Green | Yes |
| Step 4 | Blue, Green | — | 1 | Blue / Green | Yes |
| Step 5 | Green, Blue | Day Two Apparatus | 1 | Green / Blue | Yes (AA) |
| Step 6 | AA and Teams | Day Two Apparatus | **2** | — | Yes (AA) |
| Step 7 | AA and Teams | Day Two Apparatus | **2** | — | Yes (AA) |
| Step 8 | AA and Teams | Day Two Apparatus | 1 | — | Yes (AA) |
| Step 9 | AA | Day Two Apparatus | 1 | — | No |
| Step 10 | AA | Apps Day Two | 1 | — | No |
| Youth | AA | Apps Day Two | **2** | — | No |
| JI | AA | Apps Day Two | **2** | — | No |
| SI | AA | Apps Day Two | **2** | — | No |

### 6d. Sessions (16)

| Order | Session | Units | Individuals |
|---|---|---|---|
| 0 | Session 1 - STEP 2 | STEP 2 Blue 1st + Green 1st | 44 |
| 1 | Session 2 - STEP 2 | STEP 2 Blue 2nd + Green 2nd | 43 |
| 2 | Session 3 - STEP 1 | STEP 1 Green + Blue | 58 |
| 3 | Session 4 - STEP 3 | STEP 3 Blue + Green | 66 |
| 4 | Session 5 - STEP 4 | STEP 4 Blue + Green | 62 |
| 5 | Session 6 - STEP 8 and 9 | STEP 8 AA + STEP 9 AA | 25 |
| 6 | Session 7 - STEP 10, Youth, JI, SI | STEP 10 AA + Youth AA + JI AA + SI AA | 10 |
| 7 | Session 8 - STEP 5 Green | STEP 5 Green AA | 31 |
| 8 | Session 9 - STEP 5 Blue | STEP 5 Blue AA | 30 |
| 9 | Session 10 - STEP 7 | STEP 7 AA | 29 |
| 10 | Session 11 - STEP 6 | STEP 6 AA | 45 |
| 11 | Session 12 - STEP 8 and 9 | STEP 8 App + STEP 9 App | 25 |
| 12 | Session 13 - STEP 5 | STEP 5 App | 61 |
| 13 | Session 14 - STEP 7 | STEP 7 App | 29 |
| 14 | Session 15 - STEP 10, Youth, JI, SI | JI App + SI App + STEP 10 App + Youth App | 10 |
| 15 | Session 16 - STEP 6 | STEP 6 App | 45 |

---

## 7. Two-Vault Apparatus (8 events)

Steps 6, 7, Youth, Junior International, and Senior International require **two vault passes**. This is reflected in 8 unitEventIds:

| Unit | VT passes |
|---|---|
| STEP 6 AA and Teams | 2 |
| STEP 6 Day Two Apparatus | 2 |
| STEP 7 AA and Teams | 2 |
| STEP 7 Day Two Apparatus | 2 |
| Youth Apps Day Two | 2 |
| Junior International Apps Day Two | 2 |
| Senior International Apps Day Two | 2 |
| STEP 10 Apps Day Two | 2 |

All other levels use a **single vault pass**. The maximum number of passes is 2 — no 4-pass events (unlike the Nationals file).

---

## 8. Performance Individuals (613)

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

- **445** eventParticipants (registered)
- **443** unique participants with at least 1 performance individual
- **613** total performance individuals
- **2** participants registered but never competed

| Participant type | Count | % |
|---|---|---|
| In 1 unit (Day 1 AA only) | 273 | 61.5% |
| In 2 units (Day 1 AA + Day 2 Apparatus) | 170 | 38.2% |
| Registered but did not compete | 2 | 0.5% |

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

| Unit | Teams |
|---|---|
| STEP 6 AA | 9 |
| STEP 5 Green AA | 6 |
| STEP 3 Green AA | 5 |
| STEP 4 Blue AA | 5 |
| STEP 4 Green AA | 5 |
| STEP 1 Blue AA | 4 |
| STEP 2 Blue 1st AA | 4 |
| STEP 3 Blue AA | 4 |
| STEP 7 AA | 4 |
| STEP 8 AA | 4 |
| STEP 1 Green AA | 3 |
| STEP 2 Green 1st AA | 3 |
| STEP 2 Green 2nd AA | 3 |
| STEP 2 Blue 2nd AA | 3 |
| STEP 5 Blue AA | 3 |

Teams only exist in Day 1 (AA) units. All Day 2 (Apparatus) units have 0 teams.

---

## 10. Result Tables (269)

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
| **1 set** | Single ranking (individual apparatus) | 192 |
| **5 sets** | 4 apparatus + 1 allAround | 77 |

No 7-set tables — this is WAG only.

### 10c. Result Tables per Unit

| Unit | Tables | With Advancement |
|---|---|---|
| Each AA unit (Steps 1-8) | 11 | 0 |
| STEP 5 Day Two Apparatus | 11 | 0 |
| STEP 8 Day Two Apparatus | 11 | 0 |
| STEP 7 Day Two Apparatus | 11 | 0 |
| STEP 6 Day Two Apparatus | 11 | 0 |
| STEP 9 AA, STEP 9 App | 6 | 0 |
| STEP 10 AA, STEP 10 App | 6 | 0 |
| Youth AA, Youth App | 6 | 0 |
| JI AA, JI App | 6 | 0 |
| SI AA, SI App | 6 | 0 |

**No advancement** — 0 of 269 result tables have advancing/qualifier/reserve IDs.

---

## 11. Scoring System — Node-Tree Architecture

### 11a. Performance Rules (29)

Each unit has one rule set. All 29 use `"Gymnastics Rules"` — a generic rule name rather than a specific FIG code reference.

### 11b. Score Node-Tree Inputs

Each rule has a `nodeTree` with 5 input fields (IDs unique to this export):

| Input ID (example) | Input Name | Type |
|---|---|---|
| (opaque) | Did Not Start | Boolean |
| (opaque) | Zero | Boolean |
| (opaque) | Difficulty | Float |
| (opaque) | Execution Deductions | Table (Float) |
| (opaque) | Neutral Deductions | Float |

### 11c. Performance Scores (2607)

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

The `publicOutputs` dictionary contains 4 or, rarely, 5 keys:

```
4-key output (2598 of 2607 scores):
{
  (opaque): finalScore,
  (opaque): difficultyScore,
  (opaque): executionScore,
  (opaque): neutral deductions
}

5-key output (9 of 2607 scores):
{
  (opaque): "dns",
  (opaque): 0,
  (opaque): difficulty,
  (opaque): deductions,
  (opaque): additional value
}
```

Score type values found: numeric (NORMAL), `"dns"` (Did Not Start). The 5-key variant appears for DNS or special-case scores.

---

## 12. Organizations — 18 Clubs

| Code | Name | Participants |
|---|---|---|
| MGI | Manawatu GymSports | 66 |
| HUT | Hutt Valley Gymnastics | 59 |
| RIM | Rimutaka Gymsports | 53 |
| GWC | Gymnastics Waitara | 41 |
| TWI | Twisters Tawa Gymnastics Club | 39 |
| NHG | NHG Gymnastics | 34 |
| WBG | Whanganui Boys and Girls Gym Club | 29 |
| MTT | Mt Tauhara Gymnastics Club | 26 |
| CAP | Capital Gymnastics | 17 |
| KAP | Kapiti Gymnastics | 15 |
| GIS | Gisborne Gymnastics Club | 12 |
| ONS | Onslow Gymnastics | 12 |
| LVN | Levin Gymnastics Club | 11 |
| OMN | OMNI Gymnastic Centre | 11 |
| HAS | Hastings Gymnastics | 7 |
| HCG | Harbour City Gymnastics | 7 |
| CEN | Central Gym Club | 6 |
| CMG | Counties Manukau Gymnastics | 0 |

---

## 13. Data Flow

```
Event (4 days — May 29 - June 1, 2026)
  │
  ├── 29 units: 17 AA (Day 1) + 12 Apparatus (Day 2)
  │
  ├── 16 sessions: 11 Day 1 + 5 Day 2
  │     └── performanceSessionGroups (81) + Rotations (329)
  │
  ├── 445 eventParticipants
  │     └── 613 performanceIndividuals (443 unique)
  │           ├── 273 in 1 unit (Day 1 AA only)
  │           ├── 170 in 2 units (Day 1 AA + Day 2 App)
  │           ├── 2 registered but did not compete
  │           ├── resultTableConfigs → result tables
  │           └── memberRefs in teams
  │
  ├── 2607 performanceScores
  │     ├── per individual per apparatus pass
  │     ├── 8 multi-pass VT events (max 2 passes)
  │     ├── scored via "Gymnastics Rules"
  │     └── outputs: finalScore, difficulty, execution, deductions
  │
  └── 269 performanceResultTables
        ├── 192 single-set tables (apparatus rankings)
        ├── 77 five-set tables (4 apparatus + AA)
        └── 0 advancement tables (no finals)
```

---

## 14. Notable Observations

- **38.2% multi-unit participation**: The highest percentage in the dataset. 170 of 443 competing participants (38.2%) appear in 2 performance individuals — one for Day 1 AA and one for Day 2 Apparatus.
- **Step 2 is split into 4 units**: Unlike any other file, Step 2 has 4 separate units (Blue 1st, Green 1st, Green 2nd, Blue 2nd) across 2 sessions. This is driven by high Step 2 participation requiring multiple groups.
- **Youth level introduced**: The "Youth" category appears between Step 10 and Junior International — a level not present in the 2025 Manawatu edition.
- **Generic rules**: All 29 rule sets use `"Gymnastics Rules"` rather than the FIG-specific naming used in earlier files — consistent with the 2026 HVE file.
- **8 multi-pass VT events**: Steps 6, 7, Youth, JI, SI (and their Apparatus equivalents) require 2 vault passes. No 4-pass events exist (unlike the Nationals file).
- **No advancement pipeline**: 0 of 269 result tables have advancing/qualifier/reserve IDs.
- **No session folders**: The `sessionFolders` array is empty.
- **18 organizations**: Up from 15 in 2025. New clubs include NHG Gymnastics (34), Gymnastics Waitara (41), Mt Tauhara (26), and Counties Manukau (0). Counties Manukau registered 0 participants.
- **4-day competition**: May 29 to June 1 — longer than the 2025 edition (May 31 - June 2) despite similar participant counts.
- **Score outputs**: 2598 of 2607 scores use 4-key output; 9 use 5-key output (likely DNS entries). The 5-key variant matches the pattern seen in the Nationals file for DNS scorers.
- **Step 9 and above have no teams**: STEP 9 AA, STEP 10 AA, Youth AA, JI AA, SI AA and all their Apparatus equivalents show `teamCount: 0`.
- **Highest levels have tiny fields**: Youth has 4 individuals, STEP 10 has 2, JI has 1, SI has 3 — across both AA and Apparatus units.
- **Largest unit by individuals**: STEP 6 AA with 45 (and STEP 6 App with 45). STEP 5 Day Two Apparatus has 61 — the largest single unit, combining both green and blue streams for the Apparatus round.
- **Smallest unit**: Junior International AA with 1 individual.