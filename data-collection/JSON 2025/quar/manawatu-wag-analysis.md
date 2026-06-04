# manawatu-wag-25.json — Architecture & Layout Analysis

## 1. File Overview

| Attribute | Value |
|---|---|
| **Event** | Manawatu GymSports WAG Opens 2025 |
| **Date** | 2025-05-31 |
| **Sport** | GYMNASTICS (Artistic) |
| **Discipline** | WAG only |
| **Scope** | PUBLIC |
| **Organizer** | Manawatu GymSports |
| **Competitors** | 453 |
| **Organizations (Clubs)** | 15 |
| **Sessions** | 14 |
| **Rounds** | 21 |
| **Scores** | 2513 |
| **File size** | ~2.8 MB (minified JSON, single line) |

---

## 2. Top-Level Entity Map

```
manawatu-wag-25.json
├── scope: "PUBLIC"
├── sport: "GYMNASTICS"
├── event: { ... }                            # Event metadata
├── sessions:  [ Session, ... ] (14)          # Competition scheduling
├── rounds:    [ Round, ... ] (21)            # Category/level definitions + results
├── scores:    [ Score, ... ] (2513)          # Judge scores per apparatus pass
├── competitors: [ Competitor, ... ] (453)    # Athlete registry
├── organizations: [ Organization, ... ] (15) # Clubs
├── urls: [ Url, ... ] (273)                  # Short-code URL mappings
├── users: [ ]                                # Empty
├── certificateTemplates: { ... }             # PDF cert template refs
├── scoreboards: [ ]                          # Empty
└── scoreholderOrganizations: [ { ... } ]     # Scoring org (Manawatu GymSports)
```

---

## 3. Entity Relationship Diagram

```
event ─────────────────────────────────────────────────────────┐
  │                                                             │
  ├── sessions[] ─── group[] ── rotation[]                      │
  │       │                                                     │
  │       └── rounds[] (ref by _id)                             │
  │                                                             │
  ├── rounds[] ─── 21 rounds in 2 tiers:                       │
  │     │            DAY 1 (sessions 1-10): AA + Teams          │
  │     │            DAY 2 (sessions 11-14): Apparatus only     │
  │     ├── competitors[] ──→ competitor (ref by id)            │
  │     │     ├── passes[] (VT may have count=2)                │
  │     │     └── results { scores[], allAround, team }         │
  │     ├── teams[] ──→ team results                            │
  │     └── events { apparatus[], allAround, team }             │
  │                                                             │
  ├── scores[] ───→ competitor (ref by competitor id)           │
  │     │              round (ref by round id)                   │
  │     └── history[] (NORMAL | ZERO | DNS revisions)           │
  │                                                             │
  ├── competitors[] ←─ organizations[]                          │
  │     ├── tags[] (abbreviated format)                         │
  │     ├── teams[]                                              │
  │     └── sessions[] ←─ session/group assignment              │
  │                                                             │
  └── organizations[] (15 clubs, each has competitors+teams)    │
```

**Key relationships:**
- `sessions[x].rounds[]` references `rounds[y]._id`
- `rounds[x].competitors[].id` references `competitors[y]._id`
- `scores[x].competitor` references `competitors[y]._id`
- `scores[x].round` references `rounds[y]._id`
- `competitors[x].organization` references `organizations[y]._id`
- 143 competitors appear in **2 rounds** (AA Day 1 + Apparatus Day 2)

---

## 4. Two-Day Competition Model

This competition runs across two days with distinct purposes:

| Aspect | Day 1 | Day 2 |
|---|---|---|
| **Sessions** | Sessions 1–10 | Sessions 11–14 |
| **Round type** | AA, Apps and Teams / All Around, Teams / All Around | Apparatus only |
| **Steps** | 1–10 | 5–10 |
| **Competitors** | All 453 | 143 subset (Steps 5–10) |
| **Teams scored** | Yes (Steps 1–8) | No |
| **VT scoring** | Single or dual vault (per Step rules) | Single or dual vault (per Step rules) |

### Flow for a typical competitor in Steps 5–10:

```
Competitor
├── Day 1 Session (e.g. Session 8 STEP 6)
│   └── Round: "All Around and Teams"
│       ├── VT pass(es)
│       ├── UB pass
│       ├── BB pass
│       └── FX pass
│
└── Day 2 Session (e.g. Session 12 STEP 6)
    └── Round: "Apparatus"
        ├── VT pass(es)
        ├── UB pass
        ├── BB pass
        └── FX pass
```

For Steps 1–4, competitors compete on Day 1 only (no separate Apparatus round).

---

## 5. Sessions Breakdown

| # | Session Name | Discipline | Groups | Rounds (mapped categories) |
|---|---|---|---|---|
| 1 | Session 1 STEP 1 | WAG | 8 | STEP 1 Green AA + STEP 1 Blue AA |
| 2 | Session 2 STEP 2 | WAG | 8 | STEP 2 Blue AA + STEP 2 Green AA |
| 3 | Session 3 STEP 3 | WAG | 8 | STEP 3 Blue AA + STEP 3 Green AA |
| 4 | Session 4 STEP 4 Blue | WAG | 4 | STEP 4 Blue AA |
| 5 | Session 5 STEP 4 Green | WAG | 4 | STEP 4 Green AA |
| 6 | Session 6 STEP 5 Green | WAG | 4 | STEP 5 Green AA |
| 7 | Session 7 STEP 5 Blue | WAG | 4 | STEP 5 Blue AA |
| 8 | Session 8 STEP 6 | WAG | 4 | STEP 6 AA |
| 9 | Session 9 STEP 7 | WAG | 4 | STEP 7 AA |
| 10 | Session 10 STEP 8, 9, 10 | WAG | 4 | STEP 8 AA + STEP 9 AA + STEP 10 AA |
| 11 | Session 11 STEP 5 | WAG | 4 | STEP 5 Apparatus |
| 12 | Session 12 STEP 6 | WAG | 4 | STEP 6 Apparatus |
| 13 | Session 13 STEP 8, 9, 10 | WAG | 4 | STEP 8 Apparatus + STEP 9 Apparatus + STEP 10 Apparatus |
| 14 | Session 14 STEP 7 | WAG | 4 | STEP 7 Apparatus |

All sessions use default apparatus order: **VT → UB → BB → FX**.

---

## 6. Rounds Breakdown (21 rounds)

### 6a. Day 1 Rounds — All Around & Teams

| # | Category | Round Name | Competitors | Teams | Divisions |
|---|---|---|---|---|---|
| 1 | STEP 1 Green | AA, Apps and Teams | 49 | 6 | Unders / Overs |
| 2 | STEP 1 Blue | AA, Apps and Teams | 35 | 4 | Unders / Overs |
| 3 | STEP 2 Blue | AA, Apps and Teams | 35 | 4 | Unders / Overs |
| 4 | STEP 2 Green | AA, Apps and Teams | 47 | 6 | Unders / Overs |
| 5 | STEP 3 Blue | AA, Apps and Teams | 33 | 4 | Unders / Overs |
| 6 | STEP 3 Green | AA, Apps and Teams | 39 | 7 | Unders / Overs |
| 7 | STEP 4 Blue | AA, Apps and Teams | 38 | 6 | Unders / Overs |
| 8 | STEP 4 Green | AA, Apps and Teams | 32 | 5 | Unders / Overs |
| 9 | STEP 5 Green | All Around, Teams | 24 | 4 | Unders / Overs |
| 10 | STEP 5 Blue | All Around, Teams | 30 | 5 | Unders / Overs |
| 11 | STEP 6 | All Around and Teams | 34 | 6 | Unders / Overs |
| 12 | STEP 7 | All Around and Teams | 37 | 6 | Unders / Overs |
| 13 | STEP 8 | All Around and Teams | 12 | 2 | Unders / Overs |
| 14 | STEP 9 | All Around | 4 | 0 | — |
| 15 | STEP 10 | All Around | 2 | 0 | — |

### 6b. Day 2 Rounds — Apparatus Only

| # | Category | Round Name | Competitors | Teams | Divisions |
|---|---|---|---|---|---|
| 16 | STEP 5 | Apparatus | 55 | 0 | Unders / Overs |
| 17 | STEP 6 | Apparatus | 34 | 0 | Unders / Overs |
| 18 | STEP 7 | Apparatus | 37 | 0 | Unders / Overs |
| 19 | STEP 8 | Apparatus | 12 | 0 | Unders / Overs |
| 20 | STEP 9 | Apparatus | 4 | 0 | — |
| 21 | STEP 10 | Apparatus | 2 | 0 | — |

---

## 7. Two-Vault Apparatus (Steps 6, 7, 10)

Steps 6, 7, and 10 require gymnasts to perform **two vaults**. The scoring aggregation differs by step and round type:

### VT Pass Count & Aggregation

| Step | Round | VT passCount | VT aggregation | allAround VT passCount | allAround VT aggregation |
|---|---|---|---|---|---|
| **6** | All Around and Teams | 2 | AVERAGE | 2 | AVERAGE |
| **6** | Apparatus | 2 | AVERAGE | — | — |
| **7** | All Around and Teams | 2 | AVERAGE | 2 | AVERAGE |
| **7** | Apparatus | 2 | AVERAGE | — | — |
| **10** | All Around | 2 | AVERAGE | **1** | AVERAGE |
| **10** | Apparatus | 2 | **BEST** | — | — |

All other Steps (1–5, 8–9) use **single vault** (passCount=1, AVERAGE) across all round types.

### Key observations on VT scoring:

- **Steps 6 & 7**: Both vaults are averaged (`(V1 + V2) / 2`) for both AA and Apparatus results.
- **Step 10 AA**: The allAround settings show passCount=1 (only 1 vault counts toward AA total), but the apparatus settings show passCount=2 with AVERAGE aggregation. The competitor data confirms an AA VT score matching **only the first vault**.
- **Step 10 Apparatus**: Uses **BEST** aggregation — the higher of the 2 vaults is taken, rather than the average.

### Example: Step 6 AA competitor VT data

```
passes:
  ├── apparatus: "VT"
  ├── count: 2
  └── processed:
      ├── { index: 1, score: 12.95 }
      └── { index: 2, score: 13.40 }

results.allAround.apparatusScores:
  └── { code: "VT", score: 13.175, ranks: [{ rank: 7 }] }
       (12.95 + 13.40) / 2 = 13.175
```

---

## 8. WAG Step Progression (Steps 1–10)

| Step | Round Name Style | Team scoring | Divisions | VT vaults | Competitors |
|---|---|---|---|---|---|
| 1 | AA, Apps and Teams | Yes (top 3) | Unders / Overs | 1 | 84 (Green + Blue) |
| 2 | AA, Apps and Teams | Yes (top 3) | Unders / Overs | 1 | 82 (Blue + Green) |
| 3 | AA, Apps and Teams | Yes (top 3) | Unders / Overs | 1 | 72 (Blue + Green) |
| 4 | AA, Apps and Teams | Yes (top 3) | Unders / Overs | 1 | 70 (Blue + Green) |
| 5 | All Around, Teams | Yes (top 3) | Unders / Overs | 1 | 54 (Blue + Green) |
| 6 | All Around and Teams | Yes (top 3) | Unders / Overs | **2 (avg)** | 34 |
| 7 | All Around and Teams | Yes (top 3) | Unders / Overs | **2 (avg)** | 37 |
| 8 | All Around and Teams | Yes (top 3) | Unders / Overs | 1 | 12 |
| 9 | All Around | **No** | — | 1 | 4 |
| 10 | All Around | **No** | — | **2 (1 for AA)** | 2 |

---

## 9. Competitor Entity

Same structure as hv-elem, but with notable differences in tag format:

### Competitor Fields

```
Competitor {
  _id:           ObjectId
  organization: ObjectId    # ref → organizations._id
  name:          string
  number:        string
  tags:          string[]   # Abbreviated format
  rounds:        string[]   # 1 or 2 rounds (AA + optionally Apparatus)
  teams:         [{ id, round }]
  ensembles:     []
  sessions:      [{ id, group, round }]  # 1 or 2 sessions
}
```

### Tags Convention (abbreviated vs hv-elem's verbose)

```
hv-elem:   ["Step 2", "Under", "Capital", "CAP", "S2G Grp 1"]
Manawatu:  ["STEP 6", "U", "WAI", "1", "367"]
            [Level]   [Div] [Club] [Group] [Number]
```

| Index | Meaning | Example |
|---|---|---|
| 0 | Level | "STEP 6", "STEP 5" |
| 1 | Division | "U" (Unders), "O" (Overs) |
| 2 | Club code | "WAI", "HCG", "CAP" |
| 3 | Group number | "1", "3", "8" |
| 4 | Competitor number | "367", "384" |

### Two-Round Competitors

- **309** competitors (68.2%) in 1 round (Day 1 only — Steps 1–4 or Apparatus-only gymnasts)
- **143** competitors (31.6%) in 2 rounds (Day 1 AA + Day 2 Apparatus — Steps 5–10)
- **1** competitor in 0 rounds (registered but not assigned)

---

## 10. Scoring & Results System

Three scoring layers (same as hv-elem), with additions for multi-vault and new score types.

### 10a. Scores Array (Flat, 2513 Entries)

```
Score {
  _id:        ObjectId
  apparatus:  enum     # VT, UB, BB, FX
  competitor: ObjectId
  discipline: enum     # "WAG"
  round:      ObjectId
  pass:       int      # 1 or 2 (VT only, Steps 6/7/10)
  revision:   int      # Always 1
  codeOfPoints: string
  useReferenceJudgesSystem: bool
  history[]
    ├── timestamp
    ├── revision
    ├── type:     NORMAL | ZERO | DNS
    ├── difficultyScore
    ├── executionJuryScores[]
    ├── executionScore
    ├── finalScore
    └── recorderPasscode
}
```

### 10b. Score Distribution

```
Total scores: 2513
  ├── VT:   735 (29.2%)  ← includes 144 second-pass vaults
  ├── UB:   592 (23.6%)
  ├── BB:   593 (23.6%)
  └── FX:   593 (23.6%)
```

### 10c. Multi-Pass VT Scores

```
144 scores have pass > 1 (all VT, Steps 6/7/10)
  ├── STEP 6 AA:       34 competitors × 2 vaults = 68 passes
  ├── STEP 6 Apparatus: 34 competitors × 2 vaults = 68 passes
  ├── STEP 7 AA:       37 competitors × 2 vaults = 74 passes
  ├── STEP 7 Apparatus: 37 competitors × 2 vaults = 74 passes
  ├── STEP 10 AA:       2 competitors × 2 vaults  = 4 passes
  └── STEP 10 Apparatus: 2 competitors × 2 vaults = 4 passes
                          Total = 292 passes → half stored as pass=2 scores
                          (since each gymnast on each round has 2 score entries for VT)
```

### 10d. Score History Types

| Type | Description | Present in hv-elem? |
|---|---|---|
| **NORMAL** | Standard scored pass | Yes |
| **ZERO** | Zero score recorded | Yes |
| **DNS** | Did Not Start | **No** (new) |

---

## 11. Organizations (Clubs)

15 clubs from across New Zealand's North Island:

| Club | Code | Competitors | Teams |
|---|---|---|---|
| Hutt Valley Gymnastics | HUT | 67 | 8 |
| Manawatu GymSports | MGI | 60 | 7 |
| OMNI Gymnastic Centre | OMN | 48 | 8 |
| Twisters Tawa Gymnastics Club | TWI | 46 | 6 |
| Gymnastics Waitara | WAI | 44 | 6 |
| Whanganui Boys and Girls Gym Club | WBG | 34 | 5 |
| Rimutaka Gymsports | RIM | 33 | 5 |
| Levin Gymnastics Club | LVN | 22 | 4 |
| Hastings Gymnastics | HAS | 21 | 5 |
| Gisborne Gymnastics Club | GGC | 20 | 3 |
| Kapiti Gymnastics | KAP | 19 | 3 |
| Harbour City Gymnastics | HCG | 16 | 2 |
| Capital Gymnastics | CAP | 9 | 1 |
| Onslow Gymnastics | ONS | 9 | 2 |
| Central Gym Club | CEN | 5 | 0 |

---

## 12. Data Flow

```
┌─────────────────────────┐
│    Day 1 (Sessions 1-10)│
│                         │
│  STEP 1-4: "AA, Apps    │
│            and Teams"   │
│  STEP 5-8: "All Around, │
│            Teams"       │
│  STEP 9-10: "All Around"│
│                         │
│  ┌─ VT (1 or 2 passes)  │
│  ├─ UB (1 pass)         │
│  ├─ BB (1 pass)         │
│  └─ FX (1 pass)         │
│                         │
│  → allAround computed   │
│  → team scores computed │
└─────────────────────────┘
           │
           │ 143 competitors continue
           ▼
┌─────────────────────────┐
│   Day 2 (Sessions 11-14)│
│                         │
│  STEP 5-10: "Apparatus" │
│                         │
│  ┌─ VT (1 or 2 passes)  │
│  ├─ UB (1 pass)         │
│  ├─ BB (1 pass)         │
│  └─ FX (1 pass)         │
│                         │
│  → apparatus-only scores│
│  → NO team scores       │
│  → NO allAround         │
└─────────────────────────┘

Data origin flow:
  1. Event created with metadata
  2. 14 sessions scheduled across 2 days
  3. 453 competitors registered, assigned to sessions/groups
  4. 21 rounds define Step levels, apparatus config, and pass counts
  5. Judges record scores → scores[] array (2513 entries)
  6. For Steps 6/7/10: 2 VT passes recorded per gymnast per round
  7. Day 1: allAround and team rankings computed
  8. Day 2: apparatus-only rankings computed (no carry-over to AA)
```

---

## 13. Notable Observations

- **Two-day format**: This is the first file in this dataset with a multi-day structure (14 sessions, 2 distinct round tiers).
- **Two-vault steps**: Steps 6, 7, 10 are the only levels with dual vaults — matching real-world FIG/WAG rules where higher levels require a second vault.
- **Step 10 AA anomaly**: The apparatus says passCount=2 (AVERAGE), but the allAround settings say passCount=1 — meaning AA counts only 1 vault attempt, while raw apparatus scoring uses 2. Actual data confirms `allAround VT score = vault 1 score` (not averaged).
- **Step 10 Apparatus uses BEST**: Unlike Steps 6/7 which average both vaults, Step 10 Apparatus takes the higher of 2 vaults.
- **Steps 9–10 are tiny**: Only 4 and 2 competitors respectively, and no team scoring.
- **Apparatus rounds have no teams**: All 6 Apparatus-only rounds have `teams: []`.
- **DNS score type** appears in this file (not present in hv-elem), indicating some gymnasts registered but didn't start specific apparatus.
- **No carry-over relationships**: Despite the two-day structure, `carryOverResults` between AA and Apparatus rounds is empty — they are treated as independent competitions.
- **15 clubs** from across the North Island (Gisborne to Whanganui) compared to 9 in the Hutt Valley competition.
- **Tag format differs** from hv-elem: abbreviated codes (`"U"` vs `"Under"`, `"WAI"` vs `"Gymnastics Waitara"`).
- **All scores have exactly 1 revision** — no score corrections in this dataset.