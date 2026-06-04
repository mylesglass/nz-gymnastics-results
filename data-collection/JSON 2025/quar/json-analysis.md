# hv-elem-25.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | Hutt Valley Elementary Competition |
| **Date** | 2025-05-24 |
| **Sport** | GYMNASTICS (Artistic) |
| **Scope** | PUBLIC |
| **Organizer** | Hutt Valley Gymnastics |
| **Disciplines** | WAG (Women's) + MAG (Men's) |
| **Competitors** | 287 |
| **Organizations (Clubs)** | 9 |
| **Sessions** | 8 |
| **Rounds** | 9 |
| **Scores** | 1230 |
| **File size** | ~1.4 MB (minified JSON, single line) |

---

## 2. Top-Level Entity Map

```
hv-elem-25.json
├── scope: "PUBLIC"
├── sport: "GYMNASTICS"
├── event: { ... }                          # Event metadata
├── sessions:  [ Session, ... ] (8)         # Competition scheduling
├── rounds:    [ Round, ... ] (9)           # Category/level definitions + results
├── scores:    [ Score, ... ] (1230)        # Judge scores per apparatus pass
├── competitors: [ Competitor, ... ] (287)  # Athlete registry
├── organizations: [ Organization, ... ] (9) # Clubs
├── urls: [ Url, ... ] (139)                # Short-code URL mappings
├── users: [ ]                              # Empty (no user data)
├── certificateTemplates: { ... }           # PDF cert template refs
├── scoreboards: [ ]                        # Empty (no scoreboard config)
└── scoreholderOrganizations: [ { ... } ]   # Scoring org (Hutt Valley Gym)
```

---

## 3. Entity Relationship Diagram

```
event ─────────────────────────────────────────────────┐
  │                                                     │
  ├── sessions[] ─── group[] ── rotation[]              │
  │       │                                             │
  │       └── rounds[] (ref by _id)                     │
  │                                                     │
  ├── rounds[] ─────────────────────────────────────────┤
  │     ├── competitors[] ──→ competitor (ref by id)    │
  │     │     ├── passes[]                              │
  │     │     └── results { scores[], allAround, team } │
  │     │                                               │
  │     ├── teams[] ───→ team results                   │
  │     └── events { apparatus[], allAround, team }     │
  │                                                     │
  ├── scores[] ───→ competitor (ref by competitor id)   │
  │     │              round (ref by round id)           │
  │     └── history[] (NORMAL | ZERO revisions)          │
  │                                                     │
  ├── competitors[] ←─ organizations[] (has many)       │
  │     ├── tags[]                                       │
  │     ├── teams[]                                      │
  │     └── sessions[]  ←─ session/group assignment      │
  │                                                     │
  └── organizations[] (9 clubs, each has competitors+teams)
```

**Key relationships:**
- `sessions[x].rounds[]` references `rounds[y]._id`
- `rounds[x].competitors[].id` references `competitors[y]._id`
- `scores[x].competitor` references `competitors[y]._id`
- `scores[x].round` references `rounds[y]._id`
- `competitors[x].organization` references `organizations[y]._id`
- `rounds[x].teams[].organization` references `organizations[y]._id`

---

## 4. Event Metadata

| Field | Type | Value |
|---|---|---|
| `_id` | ObjectId | `6827d7b1...` |
| `name` | string | Hutt Valley Elementary Competition |
| `organization` | ObjectId | `62183134...` (Hutt Valley Gymnastics) |
| `startDate` | date | 2025-05-24 |
| `timeZone` | string | Pacific/Auckland |
| `stage` | enum | COMPLETED |
| `isPublic` | bool | true |
| `version` | int | 2262 |
| `publicUrl` | code | `6827d7b1...` (maps via `urls[]`) |
| `competitorCount` | int | 287 |
| `organizationCount` | int | 9 |
| `certificateTemplates` | object | INDIVIDUAL_ALL_AROUND, INDIVIDUAL_APPARATUS, TEAM |

---

## 5. Sessions & Organization

8 sessions split by discipline and stream:

| Session | Discipline | Groups | Rounds |
|---|---|---|---|
| Session 1 Green | WAG | 4 | Step 1 Green |
| Session 2 Green | WAG | 4 | Step 2 Green |
| Session 1 Yellow | WAG | 4 | Step 1 Yellow |
| Session 2 Yellow | WAG | 4 | Step 2 Yellow |
| Session 3 | WAG | 4 | Step 3 |
| Session 4 | WAG | 4 | Step 4 |
| Session 3 | MAG | 4 | Level 1, Level 3 |
| Session 4 | MAG | 3 | Level 2 |

### Session Structure

```
Session
├── id, event, discipline, name, stage
├── rounds[] (ref to rounds._id)
├── defaultApparatusOrder[]
├── groups[]
│   ├── id
│   ├── apparatusOrder[]
│   ├── competitors[]
│   │   └── { id (ref), round (ref) }
│   └── rotations[]
│       ├── id, apparatus
│       ├── competitorOrder[]
│       └── recorderUrl
├── judgesPanels[]
└── recorderPasscodes[]
```

### WAG Apparatus Order (default)

```
VT → UB → BB → FX
```

### MAG Apparatus Order

```
FX → PH → SR → VT → PB → HB
```

---

## 6. Rounds Breakdown

9 rounds across 2 disciplines, 7 categories:

| # | Name | Category | Discipline | Competitors | Teams | Divisions |
|---|---|---|---|---|---|---|
| 1 | All-around, App, Teams | Step 1 Green | WAG | 35 | 5 | Under / Over |
| 2 | All-around, App, Teams | Step 1 Yellow | WAG | 37 | 5 | Under / Over |
| 3 | All-around, App, Teams | Step 2 Green | WAG | 39 | 6 | Under / Over |
| 4 | All-around, App, Teams | Step 2 Yellow | WAG | 42 | 6 | Under / Over |
| 5 | All-around, App, Team | Step 3 | WAG | 41 | 7 | Under / Over |
| 6 | All-around, App, Teams | Step 4 | WAG | 40 | 6 | Under / Over |
| 7 | All-around, App, Teams | Level 1 | MAG | 13 | 3 | (none) |
| 8 | All-around, App, Teams | Level 2 | MAG | 25 | 5 | (none) |
| 9 | All-around, App, Teams | Level 3 | MAG | 11 | 0 | (none) |

### Round Object Fields

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Unique round identifier |
| `name` | string | "All-around, App, Teams" (or "Team" for Step 3) |
| `category` | string | e.g. "Step 1 Green", "Level 2" |
| `discipline` | enum | WAG / MAG |
| `divisions[]` | array | WAG: [{name: "Under"}, {name: "Over"}]; MAG: empty |
| `stage` | enum | COMPLETED |
| `codeOfPoints` | string | "FIG_2022/2024" |
| `useReferenceJudgesSystem` | bool | false |
| `useExecutionDeductions` | bool | true |
| `carryOverResults.to` | array | (empty — no carry-over between rounds) |
| `carryOverResults.aggregationMethod` | string | "ADD" |
| `competitors[]` | array | Competitor entries with passes + results |
| `teams[]` | array | Team entries with aggregated results |
| `events` | object | Apparatus config + allAround + team settings |

---

## 7. WAG vs MAG Structural Comparison

| Aspect | WAG (Steps 1–4) | MAG (Levels 1–3) |
|---|---|---|
| **Apparatus** | 4: VT, UB, BB, FX | 6: FX, PH, SR, VT, PB, HB |
| **Divisions** | Under / Over (age-based) | None |
| **Category naming** | "Step {N} {Green/Yellow}" | "Level {N}" |
| **Levels** | Step 1, 2, 3, 4 | Level 1, 2, 3 |
| **Pass count** | 1 per apparatus | 1 per apparatus |
| **Pass aggregation** | AVERAGE | AVERAGE |
| **Team scoring** | top 3 scores count (where applicable) | top 3 scores count |
| **Competitors** | 234 total (81.5%) | 49 total (18.5%) |

### WAG Apparatus (4 events)
```
VT (Vault)     → 1 pass, AVERAGE
UB (Uneven Bars) → 1 pass, AVERAGE
BB (Balance Beam) → 1 pass, AVERAGE
FX (Floor Exercise) → 1 pass, AVERAGE
```

### MAG Apparatus (6 events)
```
FX (Floor Exercise)  → 1 pass, AVERAGE
PH (Pommell Horse)   → 1 pass, AVERAGE
SR (Still Rings)     → 1 pass, AVERAGE
VT (Vault)           → 1 pass, AVERAGE
PB (Parallel Bars)   → 1 pass, AVERAGE
HB (Horizontal Bar)  → 1 pass, AVERAGE
```

---

## 8. Competitor Entity

```
Competitor {
  _id:           ObjectId    # unique ID
  organization: ObjectId    # ref → organizations._id
  name:          string      # e.g. "Lola MacIntyre"
  number:        string      # e.g. "683694"
  tags:          string[]    # e.g. ["Step 2", "Under", "Capital", "CAP", "S2G Grp 1"]
  rounds:        string[]    # ref → rounds._id
  teams:         [{ id, round }]  # team memberships
  ensembles:     []          # (unused)
  sessions:      [{ id, group, round }]  # session/group assignment
}
```

### Tags Convention
Tags encode several pieces of metadata:
- **Level**: "Step 1", "Step 2", "Level 1", etc.
- **Division**: "Under", "Over"
- **Club name**: "Capital", "Hutt Valley", etc.
- **Club code**: "CAP", "HVG", etc.
- **Group**: "S1G Grp 1", "S2G Grp 1", etc.

---

## 9. Scoring & Results System

Three layers of scoring data exist at different levels of the hierarchy:

### 9a. Round → Competitor → Passes

```
round.competitors[].passes[]
├── apparatus: "VT" | "UB" | "BB" | "FX" | "PH" | "SR" | "PB" | "HB"
├── count: 1
└── processed[]
    └── { index, didNotStart, score }
```

### 9b. Round → Competitor → Results

```
round.competitors[].results
├── scores[]        → ObjectId[] refs to scores[] entries
├── allAround
│   ├── apparatusScores[]
│   │   └── { code, ranks[{rank}], score }
│   └── total { score, ranks[] }
├── team / teamApparatus
└── divisionRankings
```

### 9c. Scores Array (Flat, 1230 Entries)

```
Score {
  _id:        ObjectId
  apparatus:  enum     # VT, UB, BB, FX, PH, SR, PB, HB
  competitor: ObjectId # ref → competitors._id
  discipline: enum     # WAG / MAG
  round:      ObjectId # ref → rounds._id
  pass:       int      # 1 (single pass for these levels)
  revision:   int      # 1 (no multi-revision scores exist)
  codeOfPoints: string # "FIG_2022/2024"
  useReferenceJudgesSystem: bool
  history[]
    ├── timestamp         ISO datetime
    ├── revision          int
    ├── type              enum: NORMAL | ZERO
    ├── difficultyScore   float  (D-score)
    ├── executionJuryScores[]
    │   └── { index, score, isRetained }
    ├── referenceExecutionJuryScores[]  (empty for this comp)
    ├── executionScore    float  (E-score)
    ├── finalScore        float  (D + E = final)
    └── recorderPasscode  string (hashed)
}
```

### Score Derivation Formula

```
finalScore = difficultyScore + executionScore

Where:
  executionScore = avg(retained executionJuryScores)
  difficultyScore = awarded D-score based on FIG 2022/2024 CoP
```

### Score Distribution

```
Total scores: 1230
  ├── WAG: 936 (76.1%)
  └── MAG: 294 (23.9%)
```

---

## 10. Organizations (Clubs)

| Club | Code | Competitors | Teams |
|---|---|---|---|
| Hutt Valley Gymnastics | HVG | 64 | 8 |
| Manawatu Gymnastics | MAN | 38 | 6 |
| Kapiti Gymnastics | KAP | 35 | 5 |
| Twisters Gymnastics | TWI | 34 | 4 |
| Rimutaka Gymnastics | RIM | 31 | 5 |
| Levin Gymnastics | LEV | 28 | 5 |
| Onslow Gymnastics | ONS | 23 | 5 |
| Harbour City Gymnastics | HCG | 20 | 3 |
| Capital Gymnastics | CAP | 14 | 2 |

---

## 11. Data Flow Summary

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│   Event      │────→│   Session    │────→│   Group           │
│ (metadata)   │     │ (time/place) │     │ (apparatus order) │
└──────────────┘     └──────────────┘     └──────────┬────────┘
                                                      │
                                                      ▼
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Score       │←────│  Round           │←────│  Rotation    │
│ (per pass)   │     │ (category/level) │     │ (apparatus)  │
│  ├ D-score   │     │  ├ competitors[] │     └──────────────┘
│  ├ E-score   │     │  ├ teams[]       │
│  └ final     │     │  └ events{}      │
└──────────────┘     └──────────────────┘

Data origin (typical flow):
  1. Event is created with metadata
  2. Sessions scheduled with groups & rotations
  3. Competitors registered & assigned to sessions/groups
  4. Rounds define categories (Step/Level), divisions, and apparatus config
  5. Judges record scores per apparatus pass → scores[] array
  6. Processed results aggregated into round.competitors[].passes[].processed[]
  7. Rankings computed for allAround, apparatus, and team events
```

---

## 12. Notable Observations

- **No carry-over** between rounds (`carryOverResults.to` is empty in all rounds).
- **Single-pass format** for all levels — no multi-pass apparatus (e.g., no two VT attempts averaged for WAG).
- **Score type `ZERO`** exists in history types — indicates zero scores recorded (likely DNS or DNF entries).
- **Step 3** uses slightly different naming (`"All-around, App, Team"` singular) vs other rounds (`"Teams"`).
- **MAG Level 3** has 0 teams — competitors compete individually only.
- **`users[]` is empty** — no user/account data exposed in this public export.
- **`scoreboards[]` is empty** — scoreboard display config not included in this export.
- **All scores have exactly 1 revision** — no multi-revision score corrections present in this dataset.