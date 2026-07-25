- athlete ID inconsistencies: 2,046 of 3,698 unique names have multiple different GNZ IDs across events. The reconciliation endpoint (POST /api/admin/reconcile-athletes) handles the common case by grouping by name and unifying to the best ID. Edge cases that may need future work:
  - Nickname/spelling variations ("Liz" vs "Elizabeth")
  - Completely different IDs for the same name with equal frequency (reported as conflicts)
  - Automatic reconciliation on upload (currently manual/admin-triggered only)

- ✅ Name-level suffix stripping: parenthetical metadata `(L#)`, `(STEP #)`, `(YI)`, `(SI)`, `(JI)`, `(SO)`, `(U/18)`, `(Male)`, and nicknames like `(Sasha)`, `(Betty)`, `(Zizzi)` are now stripped at parse time via `_NAME_LEVEL_SUFFIX = r"\s+\([^)]*\)"` at `parser.py:29`. Applied on next upload.

- ✅ Youth vs Youth International inconsistency: `resolve_level()` at `resolver.py:89-91` now returns `"Youth International"` for bare `"youth"` matches, keeping naming consistent with Junior & Senior International.

- ✅ WAG STEP4 extra division: `resolve_level()` regex at `resolver.py:80` now uses `step\s*(\d+)` to match unit names like `"WAG STEP4"` (no space). Applied on next upload.

- ✅ GNZ ID prefix pollution: `fix_gnz_id()` in `resolver.py:110-118` now strips `GS`, `GNZ`, and `GGS` prefixes; non-numeric values (e.g. club codes like `ARG`, `BOI`, `NHG`) return empty string. Applied on next upload; existing data can be fixed via re-upload.

- Gymnasts appear twice on `/gymnasts` page due to case differences in names (e.g. `Toreth Wongeoon` vs `Toreth WONGEOON`, `Alisa Wada` vs `Alisa WADA`). The `list_gymnasts` query groups by exact `(gnz_id, gymnast_name)` but Scoreholder data sometimes has inconsistent casing (ALL CAPS surnames in some files). 20+ gymnasts affected.
  - **Fix:** Normalize case (e.g. title-case) when grouping at the endpoint level, or normalize at parse time.

- ✅ Encoding issues in gymnast names: U+FFFD replacement characters and U+00A0 non-breaking spaces stripped at parse time in `resolve_participants()` at `resolver.py:17`. Applied on next upload.

- `data-collection/2026/nhg-26.json` has no actual GNZ IDs — the `identifier` field contains club codes (`ARG`, `BOI`, `NHG`, etc.) instead of individual athlete IDs. Previously these were stored as-is; now `fix_gnz_id()` returns empty string for non-numeric values. The data parses but gymnasts won't have clickable links. Any future re-upload of this file will store empty IDs.
