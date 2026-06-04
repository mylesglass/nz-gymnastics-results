# csg-classic_2025.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | CSG CLASSIC 2025 \| Brought to you by Extreme Carpet Cleaning |
| **Dates** | 2025-07-03 to 2025-07-06 (4 days) |
| **Sport** | GYMNASTICS (Artistic) |
| **Disciplines** | WAG + MAG |
| **Scope** | PUBLIC |
| **Host Organization** | Christchurch School of Gymnastics (CSG) |
| **Participants** | 611 registered, 585 competed |
| **Organizations (Clubs)** | 29 (including 1 from Australia) |
| **Session Folders** | 2 (WAG, MAG) |
| **Units** | 13 |
| **Sessions** | 28 |
| **Performance Individuals** | 585 |
| **Performance Scores** | 3641 |
| **Performance Result Tables** | 282 |
| **Performance Teams** | 108 |
| **Performance Rules** | 13 |
| **File size** | ~7.3 MB (minified JSON, single line) |

---

## 2. Data Model Overview

This file uses a **flat, reference-based** model built around a `performance*` namespace of 22 top-level arrays. Entities link to each other via `eventId`, `unitId`, `sessionId`, `participantId`, and `entityId` reference fields rather than nested hierarchical structures.

### Top-Level Keys

```
csg-classic_2025.json
│
├── events:                          [ Event ] (1)
├── eventOfficials:                  [] (0)
├── eventOrganizations:              [ Organization ] (29)
├── eventParticipants:               [ Participant ] (611)  ← registered athletes
├── performanceGroups:               [] (0)
├── performanceIndividuals:          [ Individual ] (585)   ← athletes who competed
├── performanceJudgingPanels:        [] (0)
├── performanceRecorders:            [] (0)
├── performanceResultTables:         [ ResultTable ] (282)  ← pre-computed rankings
├── performanceRules:                [ RuleSet ] (13)       ← scoring node trees
├── performanceScores:               [ Score ] (3641)       ← individual pass scores
├── performanceSessionGroups:        [ SessionGroup ] (97)  ← competitor groupings
├── performanceSessionRotations:     [ Rotation ] (477)     ← apparatus stations
├── performanceTeams:                [ Team ] (108)         ← team entries
├── products:                        [] (0)
├── scoreboards:                     [] (0)
├── sessions:                        [ Session ] (28)       ← competition time slots
├── sessionFolders:                  [ Folder ] (2)         ← WAG / MAG grouping
├── shortUrls:                       [ ShortUrl ] (43)
├── transactions:                    [] (0)
├── units:                           [ Unit ] (13)          ← division/level groupings
└── unitFolders:                     [] (0)
```

---

## 3. Entity Relationship Diagram

```
sessionFolders (WAG / MAG)
  │
  ├── sessions[] (28)
  │     ├── unitIds[] → units[]
  │     ├── performanceSessionGroups[] (97)
  │     │     └── entityRefs[] → performanceIndividuals[]
  │     └── performanceSessionRotations[] (477)
  │           ├── allowedEventCodes (apparatus)
  │           └── orderedEntityRefs[] → performanceIndividuals[]
  │
  └── units[] (13)
        ├── name (e.g. "WAG STEP 5", "MAG DIV C")
        ├── performanceRules[] (score node trees)
        ├── performanceResultTables[] (pre-computed rankings)
        ├── performanceIndividuals[] → eventParticipants[]
        └── performanceTeams[]
              └── memberRefs[] → performanceIndividuals[]

eventParticipants (611)
  └── performanceIndividuals (585)
        ├── unitId, participantId
        ├── resultTableConfigs[] → performanceResultTables[]
        └── performanceScores[] ← via entityId (3641)

performanceScores (3641)
  ├── entityId → performanceIndividuals[]
  ├── unitScoreId → performanceRules[].scores[].id
  └── publicOutputs{} → mapped via rules to field names

performanceResultTables (282)
  ├── unitId → units[]
  ├── resultSets[].primaryRanking[] → rankings
  └── advancingIds[] → qualification pipeline to finals
```

---

## 4. Event Metadata

| Field | Value |
|---|---|
| `name` | CSG CLASSIC 2025 \| Brought to you by Extreme Carpet Cleaning |
| `organizationId` | CSG (Christchurch School of Gymnastics) |
| `startDate` | 2025-07-03 |
| `endDate` | 2025-07-06 |
| `startsAt` | 2025-07-02T12:00:00Z |
| `stage` | completed |
| `isPublic` | true |
| `participantCount` | 609 |
| `timeZone` | Pacific/Auckland |
| `countryCode` | NZ |
| `currencyCode` | NZD |
| `logo` | public Scoreholder CDN |
| `venues` | [] (not specified) |

---

## 5. Competition Structure: Session Folders, Units & Sessions

### 5a. Session Folders

```
sessionFolders[0]: "WAG"
sessionFolders[1]: "MAG"
```

### 5b. Units (13) — Competition Divisions

Each unit bundles multiple levels into a single competition division:

| # | Unit Name | Discipline | Levels | Individuals | Teams |
|---|---|---|---|---|---|
| 1 | WAG STEP 2 | WAG | Step 2 | 48 | 9 |
| 2 | WAG STEP 3 | WAG | Step 3 | 37 | 6 |
| 3 | WAG STEP 4 | WAG | Step 4 | 38 | 7 |
| 4 | WAG STEP 5 | WAG | Step 5 | 91 | 19 |
| 5 | WAG STEP 6 | WAG | Step 6 | 67 | 13 |
| 6 | WAG STEP 7 | WAG | Step 7 | 74 | 15 |
| 7 | WAG STEP 8 | WAG | Step 8 | 29 | 5 |
| 8 | WAG STEP 9 | WAG | Step 9 | 18 | 2 |
| 9 | WAG DIVISION A | WAG | Step 10, JI, SI | 32 | 6 |
| 10 | MAG DIVISION D | MAG | Level 2, 3 | 25 | 5 |
| 11 | MAG DIVISION C | MAG | Level 4, 5, 6 | 71 | 13 |
| 12 | MAG DIVISION B | MAG | Level 7, 8, 9 | 40 | 7 |
| 13 | MAG DIVISION A | MAG | Under 16, 18, Senior Open | 15 | 1 |

### 5c. WAG Units Detail

| Unit | VT passCount | Apparatus |
|---|---|---|
| Step 2 | 1 | VT, UB, BB, FX |
| Step 3 | 1 | VT, UB, BB, FX |
| Step 4 | 1 | VT, UB, BB, FX |
| Step 5 | 1 | VT, UB, BB, FX |
| Step 6 | 2 | VT, UB, BB, FX |
| Step 7 | 2 | VT, UB, BB, FX |
| Step 8 | 1 | VT, UB, BB, FX |
| Step 9 | 1 | VT, UB, BB, FX |
| Step 10 / JI / SI | 2 | VT, UB, BB, FX |

### 5d. MAG Units Detail

All MAG divisions use 6 apparatus: FX, PH, SR, VT, PB, HB

---

## 6. Session Map — 28 Sessions Across 4 Days

### WAG Sessions

| Order | Session Name | Unit(s) | Individuals |
|---|---|---|---|
| 0 | WAG SESSION 1 \| STEP 3 | Step 3 | 37 |
| 1 | WAG SESSION 2 \| STEP 2 | Step 2 | 48 |
| 2 | WAG SESSION 3 \| STEP 7 ROUND 1 | Step 7 | 32 |
| 3 | WAG SESSION 4 \| STEP 7 ROUND 2 | Step 7 | 42 |
| 4 | WAG SESSION 5 \| STEP 9 | Step 9 | 18 |
| 5 | WAG SESSION 6 \| JI, SI | Division A (JI/SI) | 19 |
| 6 | WAG SESSION 6 \| STEP 10 | Division A (Step 10) | 12 |
| 7 | WAG SESSION 7 \| STEP 6 ROUND 1 | Step 6 | 37 |
| 8 | WAG SESSION 7 \| STEP 5 ROUND 1 | Step 5 | 44 |
| 9 | WAG SESSION 8 \| STEP 5 ROUND 2 | Step 5 | 47 |
| 10 | WAG SESSION 8 \| STEP 6 ROUND 2 | Step 6 | 31 |
| 11 | WAG SESSION 9 \| STEP 8 | Step 8 | 29 |
| 12 | WAG VIP SESSION 10 \| STEP 9, 10, JI, SI | Step 9 + Division A | 47 |
| 13 | WAG Session 11 \| STEP 7 & 5 | Step 7 + Step 5 | 163 |
| 14 | WAG Session 12 \| STEP 6 & 8 | Step 6 + Step 8 | 96 |
| 15 | WAG Session 13 \| STEP 4 | Step 4 | 38 |

### MAG Sessions

| Order | Session Name | Unit(s) | Individuals |
|---|---|---|---|
| 0 | MAG SESSION 3 \| Level 5 | Division C (L4-6) | 22 |
| 1 | MAG SESSION 4 \| Level 8, 9 | Division B (L7-9) | 23 |
| 2 | MAG SESSION 5 \| Level 6 | Division C (L4-6) | 14 |
| 3 | MAG SESSION 5 \| Level 7 | Division B (L7-9) | 17 |
| 4 | MAG SESSION 6 \| UNDER 16, 18, SO | Division A | 15 |
| 5 | MAG SESSION 7 \| Level 4 | Division C (L4-6) | 35 |
| 6 | MAG session 8 \| Level 8 & 9 finals | Division B (L7-9) | 23 |
| 7 | MAG SESSION 9 \| Level 6 & 7 finals | Div B + Div C | 31 |
| 8 | MAG VIP SESSION 10 \| UNDER 16, 18, SO | Division A | 15 |
| 9 | MAG SESSION 11 \| Level 4 & 5 App Finals | Division C (L4-6) | 57 |
| 10 | MAG SESSION 12 \| Level 3 | Division D (L2-3) | 12 |
| 11 | MAG SESSION 13 \| Level 2 | Division D (L2-3) | 13 |

---

## 7. Round Structure — Qualification & Finals

### 7a. WAG Round 1 / Round 2

Steps 5, 6, and 7 each have two separate round sessions. These rounds contain **largely distinct groups** of competitors:

| Step | Round 1 | Round 2 | Overlap |
|---|---|---|---|
| Step 5 | 44 indiv | 47 indiv | Minimal |
| Step 6 | 37 indiv | 31 indiv | 1 indiv |
| Step 7 | 32 indiv | 42 indiv | Minimal |

### 7b. MAG Finals

Three finals sessions exist for MAG:

| Final | Unit | Individuals |
|---|---|---|
| Level 8 & 9 finals | Division B (L7-9) | 23 |
| Level 6 & 7 finals | Div B + Div C | 31 |
| Level 4 & 5 App Finals | Division C (L4-6) | 57 |

### 7c. Qualification Pipeline

- **101 of 282** result tables have `advancingIds[]`, `qualifierIds[]`, and `reserveIds[]`
- These link qualification round rankings to finals sessions
- Each table defines `maxQualifierCount`, `maxReserveCount`, and tie-break rules
- `maxQualifierCountPerOrganization` limits qualifiers per club

---

## 8. WAG vs MAG — Full Comparison

| Aspect | WAG | MAG |
|---|---|---|
| Levels | Step 2 → Step 10, JI, SI | Level 2 → Level 9, U16, U18, SO |
| International tiers | JI (Junior International), SI (Senior International) | Under 16, Under 18, Senior Open |
| Apparatus | VT, UB, BB, FX (4) | FX, PH, SR, VT, PB, HB (6) |
| Two-vault steps | Step 6, Step 7, Step 10/JI/SI | N/A |
| Round structure | Qualification (R1/R2 for Steps 5-7) + no separate finals | Qualification + Apparatus Finals (L4-9) |
| Largest unit | Step 5 (91 individuals, 19 teams) | Div C L4-6 (71 individuals, 13 teams) |
| Lowest step | Step 2 (48 indiv) | Level 2 (13 indiv) |
| Highest step | Senior International | Senior Open |
| Team scoring | Yes (Steps 2-9) | Yes |

### Apparatus by Discipline

```
WAG: VT (Vault) → UB (Uneven Bars) → BB (Balance Beam) → FX (Floor Exercise)
MAG: FX (Floor Exercise) → PH (Pommell Horse) → SR (Still Rings) → VT (Vault) → PB (Parallel Bars) → HB (Horizontal Bar)
```

### Competitive Level Progression

```
WAG:  Step 2 < Step 3 < Step 4 < Step 5 < Step 6 < Step 7 < Step 8 < Step 9 < Step 10 < JI < SI
MAG:  Level 2 < Level 3 < Level 4 < Level 5 < Level 6 < Level 7 < Level 8 < Level 9 < U16 < U18 < SO
```

---

## 9. Performance Individuals (585)

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

- **611** eventParticipants (registered athletes)
- **585** performanceIndividuals (athletes who actually competed)
- **26** participants (4.3%) registered but have no performance individual record

Each participant maps to exactly **1** performance individual. The same participant appears across different apparatus and rankings through their `resultTableConfigs[]` entries.

---

## 10. Performance Teams (108)

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
| WAG STEP 5 | 19 |
| WAG STEP 7 | 15 |
| MAG DIV C (L4-6) | 13 |
| WAG STEP 6 | 13 |
| WAG STEP 2 | 9 |
| MAG DIV B (L7-9) | 7 |
| WAG STEP 4 | 7 |
| WAG DIV A (Step 10, JI, SI) | 6 |
| WAG STEP 3 | 6 |
| WAG STEP 8 | 5 |
| MAG DIV D (L2-3) | 5 |
| WAG STEP 9 | 2 |
| MAG DIV A (U16, 18, SO) | 1 |

---

## 11. Scoring System — Node-Tree Architecture

Scoring is driven by a configurable node-tree rule engine defined per unit, rather than simple D-score + E-score = final.

### 11a. Performance Rules (13)

Each unit has one rule set. All use `"FIG 2022/2024"`:

| Units | Rule Name |
|---|---|
| All MAG units | MAG FIG 2022/2024 |
| All WAG units | WAG FIG 2022/2024 |

### 11b. Score Node-Tree Inputs

Each rule contains a `nodeTree` with an `interface` defining scoring inputs. Inputs are identified by opaque IDs:

| Input ID (example) | Input Name | Type |
|---|---|---|
| `d8HhpyHDI77S4XFdLZ2o7` | Did Not Start | Boolean |
| `HI1Kbkw-AnCBqhkcOjhX` | Zero | Boolean |
| `Qs1aq51BmT5T5jEDNLgI` | Difficulty | Float |
| `d8CGsTJtEF0bKv5g-Yf3` | Execution Deductions | Table (Float) |
| `oefv5iCJEBKA3q-xLEl7` | Neutral Deductions | Float |

### 11c. Performance Scores (3641)

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
  publicOutputs:  {}          ← score values keyed by node-tree input IDs
}
```

### 11d. Interpreting a Score

The `publicOutputs` dictionary contains computed values keyed by opaque IDs from the node-tree definition:

```
Sample: score with DNS
{
  "8nc_U6E85tlS3U47ZbPaS": "dns",    ← Did Not Start = true
  "YyNf_PdbUgs8YHr68lvvC": 0,         ← Zero = false
  "P6S70HZD-BWrK7lDa0vfV": 10,        ← Difficulty
  "yNGQdkggT5Ao5uw2x5v-O": 0,         ← Neutral Deductions
}

Sample: score with values
{
  "JnPzDdSPnQabVqIxX570A": 12.866,    ← finalScore
  "7p9hG6Hx50P8xUSgdyXJr": 4.7,       ← difficultyScore
  "NyQa1aYGCDRw2eQ8yoIZ4": 8.166,     ← executionScore
  "bUHxtR18UH7ysLBdjGfve": 0          ← neutral deductions
}
```

Score type values found: numeric (NORMAL), `"dns"` (Did Not Start), `0` (zero/not-applicable).

### 11e. Score Field Resolution

The `publicOutputs` keys do not have meaningful names by themselves. To interpret a score, each key must be cross-referenced against the `performanceRules` entry matching the score's `unitScoreId`. The rule's `nodeTree.interface.inputs[]` maps opaque IDs to human-readable field names.

---

## 12. Result Tables System (282)

### 12a. Structure

```
performanceResultTable {
  _id:                    ObjectId
  eventId:                ObjectId
  unitId:                 ObjectId
  resultTableId:          string (opaque)
  primaryResultSetId:     string → references resultSets[].id
  resultSets[]
    ├── id
    ├── name (optional)
    ├── primaryRanking[]
    │   └── { entityId, value (score), rank, sourceItems[], isEqual }
    ├── secondaryRanking[] (optional apparatus sub-rankings)
    └── tertiaryRanking[] (optional)
  advancingIds[]          (present in 101 tables)
  qualifierIds[]          (present in 101 tables)
  reserveIds[]            (present in 101 tables)
  isPublic:               bool
  maxQualifierCount, maxReserveCount, etc.
}
```

### 12b. Result Table Types by Set Count

| Result Sets | Meaning | Units |
|---|---|---|
| **1 set** | Single ranking (individual apparatus or qualifier list) | Majority of tables |
| **5 sets** | 4 apparatus + 1 allAround (WAG) | Steps 2-10 |
| **7 sets** | 6 apparatus + 1 allAround (MAG) | All MAG divisions |

### 12c. Result Tables per Unit

| Unit | Tables | With Advancement |
|---|---|---|
| MAG DIV A (U16, 18, SO) | 40 | 16 |
| MAG DIV B (L7-9) | 40 | 14 |
| MAG DIV C (L4-6) | 40 | 20 |
| WAG DIV A (Step 10, JI, SI) | 28 | 14 |
| WAG STEP 5 | 19 | 8 |
| WAG STEP 6 | 19 | 9 |
| WAG STEP 7 | 19 | 9 |
| WAG STEP 8 | 19 | 9 |
| MAG DIV D (L2-3) | 15 | 0 |
| WAG STEP 2 | 11 | 0 |
| WAG STEP 3 | 11 | 0 |
| WAG STEP 4 | 11 | 0 |
| WAG STEP 9 | 10 | 3 |

### 12d. Ranking Entry Example

```json
{
  "entityId": "6863d67b046c6afd93da8893",
  "value": 11.933,
  "sourceItems": [
    { "itemId": "686791ddda344472af16de5c",
      "itemType": "score",
      "status": "retained" }
  ],
  "rank": 1,
  "isEqual": false
}
```

---

## 13. Organizations (29 Clubs)

National-level competition drawing clubs from across New Zealand plus one international entry:

| Code | Name | Participants |
|---|---|---|
| CSG | Christchurch School of Gymnastics | 88 |
| OLY | Olympia Gymnastics Sports | 49 |
| AFF | Affinity Gymnastics Academy | 45 |
| TRI | Tri Star Gymnastics | 44 |
| HVG | Hutt Valley Gymnastics | 38 |
| STM | Star-Mites (Australia) | 38 |
| NHG | NHG | 36 |
| TWO | Te Wero | 31 |
| CMG | Counties Manukau Gymnastics | 29 |
| IMP | Impact Gymsport Academy | 25 |
| DGA | Dunedin Gymnastics Academy | 23 |
| CAP | Capital Gymnastics Club | 22 |
| HCG | Hamilton City Gymnastics | 20 |
| KAP | Kapiti Gymnastics Club | 19 |
| MAN | Manawatu Gymsports | 16 |
| INV | Invercargill Gymnastic Club | 16 |
| WTK | Waitakere Gymnastics | 16 |
| HOW | Howick Gymnastics Club | 11 |
| ESG | Eastern Suburbs Gymnastics Club | 8 |
| QUE | Queenstown Gymnastics Club | 7 |
| GNI | Gymnastics Nelson | 7 |
| RIM | Rimutaka Gymsports | 6 |
| SCG | South Canterbury GymSports | 5 |
| ASP | Aspiring Gymsports | 4 |
| PAT | Pathfinders Gymnastic Club | 2 |
| TWI | Twisters Tawa Gymnastics Club | 2 |
| WAI | Waimate Gymnastics Club | 2 |
| OMN | Omni Gymnastic Centre | 1 |
| FRA | Franklin Gymsports | 1 |

---

## 14. Data Flow

```
                    ┌──────────────────┐
                    │   Event (4-day)   │
                    │ CSG CLASSIC 2025  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │ session-   │  │   units    │  │ participants│
     │ folders    │  │  (13 divs) │  │  (611 reg)  │
     │ WAG / MAG  │  └──────┬─────┘  └──────┬──────┘
     └────────────┘         │                │
              │              ▼                ▼
              ▼     ┌─────────────────────────────────┐
     ┌────────────┐ │ performanceIndividuals (585)     │
     │  sessions  │ │  ├ resultTableConfigs[]          │
     │   (28)     │ │  ├ unitId → units                │
     └─────┬──────┘ │  └ participantId → participants  │
           │        └──────────────┬──────────────────┘
           ▼                       │
     ┌────────────┐                ▼
     │ session    │     ┌─────────────────────┐
     │   groups   │     │ performanceScores   │
     │   (97)     │     │ (3641, per pass)    │
     └─────┬──────┘     │ ┌─────────────────┐ │
           │            │ │ performanceRules │ │
           ▼            │ │ (13 node trees)  │ │
     ┌────────────┐     │ └─────────────────┘ │
     │ rotations  │     └──────────┬──────────┘
     │ (477)      │                │
     └────────────┘                ▼
                           ┌─────────────────────┐
                           │ performanceResult-   │
                           │ Tables (282)         │
                           │ ├ apparatus rankings │
                           │ ├ allAround rankings │
                           │ ├ team rankings      │
                           │ └ advancement→finals │
                           └─────────────────────┘
```

---

## 15. Notable Observations

- **Node-tree scoring engine**: Scores are computed through a configurable node tree per unit rather than a simple D + E formula. Input fields include Did Not Start (boolean), Zero (boolean), Difficulty (float), Execution Deductions (table), and Neutral Deductions (float). Only the final computed `publicOutputs` are exported — intermediate deduction breakdowns are not visible.
- **Opaque score field IDs**: `publicOutputs` keys are random-looking strings that must be cross-referenced against the unit's `performanceRules` to map to human-readable field names. There is no direct `difficultyScore` or `finalScore` field name in the score objects.
- **WAG Round 1 / Round 2 are separate streams**: Steps 5, 6, and 7 have two round sessions but they contain mostly different competitors — only 1 gymnast appears in both Step 6 R1 and R2. These are separate qualification groups rather than the same gymnast competing twice.
- **MAG has finals, WAG does not**: Three MAG finals sessions exist (Levels 4-5 App Finals, 6-7 finals, 8-9 finals). WAG has no separate finals sessions — all WAG events use a qualification-only model.
- **101 qualification result tables**: 101 of 282 result tables have advancing/qualifier/reserve IDs linking qualification rounds to finals, with configurable qualifier counts and per-organization limits.
- **International levels**: WAG includes JI (Junior International) and SI (Senior International) levels. MAG includes Under 16, Under 18, and Senior Open — all grouped into single units.
- **Two-vault steps**: WAG Steps 6, 7, and 10/JI/SI require 2 vault passes. All other WAG steps use a single vault.
- **WAG Step 10, JI, and SI share a unit**: All three levels (Step 10, Junior International, Senior International) are grouped into "WAG DIVISION A" — 32 individuals across all three tiers.
- **MAG Division A is the smallest unit**: Only 15 individuals and 1 team, but covers the highest MAG levels (Under 16, Under 18, Senior Open).
- **Australian participation**: Star-Mites Gymnastics from Australia (38 participants) travelled to compete, making this the most geographically diverse competition in the dataset.
- **29 clubs** spanning the full length of New Zealand — from Invercargill (INV) in the south to Howick/Auckland (HOW) in the north.
- **26 participants (4.3%)** registered but never appeared in a performance individual — they did not compete.
- **Empty arrays**: `eventOfficials`, `performanceJudgingPanels`, `performanceRecorders`, `scoreboards`, `products`, `transactions` are all empty — either unused or not included in public exports.