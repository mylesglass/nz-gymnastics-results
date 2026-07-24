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
