- athlete ID inconsistencies: 2,046 of 3,698 unique names have multiple different GNZ IDs across events. The reconciliation endpoint (POST /api/admin/reconcile-athletes) handles the common case by grouping by name and unifying to the best ID. Edge cases that may need future work:
  - Nickname/spelling variations ("Liz" vs "Elizabeth")
  - Completely different IDs for the same name with equal frequency (reported as conflicts)
  - Automatic reconciliation on upload (currently manual/admin-triggered only)

- ✅ Name-level suffix stripping: `(L#)`, `(STEP 10)`, `(YI)`, `(SI)`, `(JI)` suffixes cleaned at parse time via `_NAME_LEVEL_SUFFIX` regex at `parser.py:29`. Applied on next upload.

- ✅ Youth vs Youth International inconsistency: `resolve_level()` at `resolver.py:89-91` now returns `"Youth International"` for bare `"youth"` matches, keeping naming consistent with Junior & Senior International.

- ✅ WAG STEP4 extra division: `resolve_level()` regex at `resolver.py:80` now uses `step\s*(\d+)` to match unit names like `"WAG STEP4"` (no space). Applied on next upload.

- ✅ GNZ ID prefix pollution: `fix_gnz_id()` in `resolver.py:110-118` now strips `GS`, `GNZ`, and `GGS` prefixes; non-numeric values (e.g. club codes like `ARG`, `BOI`, `NHG`) return empty string. Applied on next upload; existing data can be fixed via re-upload.

- Gymnasts appear twice on `/gymnasts` page due to case differences in names (e.g. `Toreth Wongeoon` vs `Toreth WONGEOON`, `Alisa Wada` vs `Alisa WADA`). The `list_gymnasts` query groups by exact `(gnz_id, gymnast_name)` but Scoreholder data sometimes has inconsistent casing (ALL CAPS surnames in some files). 20+ gymnasts affected.
  - **Fix:** Normalize case (e.g. title-case) when grouping at the endpoint level, or normalize at parse time.

- Encoding issues in gymnast names: `Amor� Visser` (with Unicode replacement character U+FFFD) appears alongside `Amore Visser` (with proper `e`). Same GNZ ID 528197, same club ARGOS. The `�` comes from a JSON file that likely had `é` but was decoded incorrectly. `Amore Visser` also has a second ID 593863 in STEP 4.
  - **Fix:** Detect/replace non-ASCII replacement chars at parse time. Handle the `é` vs `e` variant in reconciliation.

- Nickname/parenthetical names not stripped: `Alexander (Sasha) Bradley Hide` and `Sasha Hide` share the same GNZ ID 805374 and club (Kapiti Gymnastics) but appear as separate gymnasts. The `(Sasha)` nickname is embedded in the name and not stripped by the current `_NAME_LEVEL_SUFFIX` regex. Also: `Zack (Zizzi) Nikolai Hide` vs `Zizzi Hide` (ID 805370).
  - **Fix:** Extend `_NAME_LEVEL_SUFFIX` (or add a separate pass) to strip parenthesized nicknames like `(Sasha)`, `(Zizzi)` from names at parse time.

- `data-collection/2026/nhg-26.json` has no actual GNZ IDs — the `identifier` field contains club codes (`ARG`, `BOI`, `NHG`, etc.) instead of individual athlete IDs. Previously these were stored as-is; now `fix_gnz_id()` returns empty string for non-numeric values. The data parses but gymnasts won't have clickable links. Any future re-upload of this file will store empty IDs.
