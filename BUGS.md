- athlete ID inconsistencies: 2,046 of 3,698 unique names have multiple different GNZ IDs across events. The reconciliation endpoint (POST /api/admin/reconcile-athletes) handles the common case by grouping by name and unifying to the best ID. Edge cases that may need future work:
  - Nickname/spelling variations ("Liz" vs "Elizabeth")
  - Completely different IDs for the same name with equal frequency (reported as conflicts)
  - Automatic reconciliation on upload (currently manual/admin-triggered only)

- Name-level suffix stripping: `(L#)`, `(STEP 10)`, `(YI)` suffixes are now cleaned from gymnast names at parse time via `_NAME_LEVEL_SUFFIX` regex. Existing events need re-upload to apply.
