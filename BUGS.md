- athlete ID inconsistencies: 2,046 of 3,698 unique names have multiple different GNZ IDs across events. The reconciliation endpoint (POST /api/admin/reconcile-athletes) handles the common case by grouping by name and unifying to the best ID. Edge cases that may need future work:
  - Nickname/spelling variations ("Liz" vs "Elizabeth")
  - Completely different IDs for the same name with equal frequency (reported as conflicts)
  - Automatic reconciliation on upload (currently manual/admin-triggered only)

- Name-level suffix stripping: `(L#)`, `(STEP 10)`, `(YI)` suffixes are cleaned from gymnast names at parse time via `_NAME_LEVEL_SUFFIX` regex at `parser.py:29`. Missing `(SI)` and `(JI)` — these are not stripped and remain in displayed names. Existing events need re-upload to apply fix.
  - **Fix:** Add `SI|JI` to the regex.
  - **File:** `backend/app/parser.py:29`

- Youth vs Youth International inconsistency: `resolve_level()` at `resolver.py:77-91` returns `"Youth International"` when unit name contains `"youth international"`, but `"Youth"` for bare `"youth"`. These are distinct `level_category` values. Should normalize to `"Youth International"` to stay inline with Junior & Senior International naming.
  - **Fix:** Change bare `"youth"` check to return `"Youth International"` instead of `"Youth"`.
  - **File:** `backend/app/resolver.py:89-91`

- WAG STEP4 extra division: `resolve_level()` regex at `resolver.py:81` uses `step\s+(\d+)` (>=1 whitespace required). Unit names like `"WAG STEP4"` (no space, e.g. `data-collection/2026/gissy-2026.json`) don't match and fall through to the raw unit name.
  - **Fix:** Change to `step\s*(\d+)` (zero-or-more whitespace).
  - **File:** `backend/app/resolver.py:81`

- Gymnasts appear twice on `/gymnasts` page due to case differences in names (e.g. `Toreth Wongeoon` vs `Toreth WONGEOON`, `Alisa Wada` vs `Alisa WADA`). The `list_gymnasts` query groups by exact `(gnz_id, gymnast_name)` but Scoreholder data sometimes has inconsistent casing (ALL CAPS surnames in some files). 20+ gymnasts affected.
  - **Fix:** Normalize case (e.g. title-case) when grouping at the endpoint level, or normalize at parse time.

- Encoding issues in gymnast names: `Amor� Visser` (with Unicode replacement character U+FFFD) appears alongside `Amore Visser` (with proper `e`). Same GNZ ID 528197, same club ARGOS. The `�` comes from a JSON file that likely had `é` but was decoded incorrectly. `Amore Visser` also has a second ID 593863 in STEP 4.
  - **Fix:** Detect/replace non-ASCII replacement chars at parse time. Handle the `é` vs `e` variant in reconciliation.

- Nickname/parenthetical names not stripped: `Alexander (Sasha) Bradley Hide` and `Sasha Hide` share the same GNZ ID 805374 and club (Kapiti Gymnastics) but appear as separate gymnasts. The `(Sasha)` nickname is embedded in the name and not stripped by the current `_NAME_LEVEL_SUFFIX` regex. Also: `Zack (Zizzi) Nikolai Hide` vs `Zizzi Hide` (ID 805370).
  - **Fix:** Extend `_NAME_LEVEL_SUFFIX` (or add a separate pass) to strip parenthesized nicknames like `(Sasha)`, `(Zizzi)` from names at parse time.

- GNZ ID prefix pollution: Some IDs have non-numeric prefixes that should be stripped:
  - `GNZ` prefix: `GNZ699917`, `GNZ592969`, `GNZ723457`, `GNZ691749`, `GNZ758664`, `GNZ691634`, `GNZ691798`, `GNZ775527`, `GNZ765054`, `GNZ625530`, `GNZ782597`, `GNZ624320`, `GNZ816963`
  - `GGS` prefix: `GGS200576`
  - Club code IDs treated as GNZ IDs: `AGA`, `TWG`, `SCG`, `CSG`, `GNI`, `WGC`, `TGC`, `CMG`, `TRI`, `NHG`, `TPG`, `WHG`, `KER`, `KPR`, `ESG`, `BOI`
  - Note: No `GS` prefix IDs found, but related `GNZ` and `GGS` prefixes are present.
  - **Fix:** Strip `GNZ`/`GGS` prefix from IDs in `fix_gnz_id()` in resolver.py; filter out club-code IDs during reconciliation.
