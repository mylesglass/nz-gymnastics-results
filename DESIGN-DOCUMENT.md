# AI Agent Design Document: Gymnastics Score Parsing Pipeline & Web Viewer

## 1. Project Overview
* **Goal:** Build an end-to-end pipeline to ingest complex, flat-relational JSON gymnastics scoring data (from Scoreholder), parse it, store it in a normalized database, dynamically pivot it into a wide format, export to CSV/XLSX, and display it in a web interface.
* **Data Source Architecture:** The input JSON files use a flat, reference-based `performance*` model with 22 top-level arrays (e.g., `events`, `eventParticipants`, `performanceScores`, `performanceResultTables`).
* **Target Environment:** Self-hosted home server, low traffic. Containerized deployment.

## 2. Technology Stack
* **Backend:** Python with FastAPI.
* **Data Processing:** Python native `json` library, `pandas` for data manipulation, pivoting, and `.csv`/`.xlsx` export.
* **Database:** SQLite.
* **Frontend:** Svelte (SvelteKit or Vite) for a lightweight data-table display.
* **Infrastructure:** Docker Compose.

## 3. Storage Schema (SQLite - "Long Format")
The raw data must be parsed and stored in SQLite in a normalized, "long" format. **One row = one apparatus pass for one gymnast.**

| Column Name | Data Type | Description & Source Mapping |
| :--- | :--- | :--- |
| `Event_Name` | String | Extracted from `events[].name`. |
| `Gymnast_Name` | String | Mapped via `performanceIndividuals[]` -> `eventParticipants[].name`. |
| `GNZ_ID` | String | Mapped via `eventParticipants[].identifier`. |
| `Club_Name` | String | Mapped via `eventOrganizations[].name`. |
| `Discipline` | String | WAG or MAG (inferred from Unit/Session/Event). |
| `Level_Category` | String | Extracted from `units[].name` (e.g., "STEP 6 AA"). |
| `Apparatus` | String | Extracted from `performanceScores[].unitEventId` (VT, UB, BB, etc.). |
| `Pass_Number` | Integer | Extracted from `performanceScores[].unitPassId`. |
| `D_Score` | Float | Difficulty score. Decoded from `performanceScores[].publicOutputs`. |
| `E_Score` | Float | Execution score. Decoded from `performanceScores[].publicOutputs`. |
| `Neutral_Deductions` | Float | Penalties/Deductions. Decoded from `performanceScores[].publicOutputs`. |
| `Pass_Final_Score` | Float | Total score for this specific pass. Decoded from `performanceScores[].publicOutputs`. |

## 4. Export & Display Schema (Pandas - "Wide Format")
Before exporting to CSV/XLSX or sending data to the Svelte frontend, Pandas must construct the final "All Around" table by grouping the long-format data by Gymnast/Round, aggregating the vault scores, and joining the official rankings from `performanceResultTables`. 

The target wide-format output is:
`gnz-id, name, club, step, division, competition, round-type, day, v-total, v-d, v-e, v-n, v-rank, ub-total, ub-d, ub-e, ub-n, ub-rank, bb-total, bb-d, bb-e, bb-n, bb-rank, fx-total, fx-d, fx-e, fx-n, fx-rank, aa-score, aa-rank, date-created` *(Note: MAG will include PH, SR, PB, HB).*

## 5. Core Parsing Logic Requirements (The "Smart Pipeline")
The Python backend must implement a dynamic parsing strategy to handle the structural complexities of the Scoreholder format:

1.  **ID Resolution Chains:** Data is not nested. The script must resolve foreign keys to link scores to gymnast names and clubs.
2.  **Node-Tree Score Decoding:** The values for Difficulty, Execution, and Final Score are hidden behind dynamic, opaque keys inside `performanceScores[].publicOutputs` (e.g., `{"Ut2MuKcIkOof-N8vvxB20": 13.65}`). The script must cross-reference `performanceRules[].scores[].nodeTree` to dynamically map these opaque keys to their human-readable metrics.
3.  **Ranking Extraction:** While raw scores come from `performanceScores`, the official apparatus ranks (`v-rank`, `ub-rank`) and All-Around ranks (`aa-rank`) must be extracted from `performanceResultTables` and mapped to the gymnast via their `entityId`.
4.  **Multi-Unit Deduplication:** Up to 38% of gymnasts may compete in two separate units (e.g., Day 1 All-Around, Day 2 Apparatus). The script must ensure these are handled gracefully without duplicating base participant data in the final wide view.

## 6. Application Flow (MVP)
1.  **Upload:** User uploads a `.json` file to the Svelte frontend.
2.  **Ingestion & Parsing:** FastAPI endpoint passes the file to Python, which decodes the node-tree, resolves IDs, and grabs scores and ranks.
3.  **Storage:** Data is written to SQLite in the "Long Format."
4.  **Transformation & Export:** Pandas queries SQLite, pivots the data into the "Wide Format," calculates `aa-score` (if not provided in rankings), and generates downloadable `.csv` and `.xlsx` files.
5.  **View:** Svelte fetches the pivoted wide-format data via FastAPI and displays it in a clean HTML table.


## Additional Resources:
- `data-collection/data-structure-analysis` contains files that have been analysed and give deeper insight into how various json files have been formed. 
- `data-collection/sc-convert-v3.py` is the previous python script used to parse this data, it is not perfect but gives insight into how this data has been parsed previously. 