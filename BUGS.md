All bugs reported in this session are fixed. See `git log` for details.

**Previously fixed:**
- Name suffix stripping: `(L#)`, `(STEP #)`, `(YI)`, `(SI)`, `(JI)`, `(SO)`, `(U/18)`, `(Male)` and nicknames like `(Sasha)` stripped at parse time
- Youth vs Youth International normalization
- WAG STEP4 unit name parsing
- GNZ/GGS prefix stripping and club code rejection in `fix_gnz_id()`
- U+FFFD replacement character and non-breaking space stripping from names
- Case-insensitive grouping on `/gymnasts` page
- GFA-only clubs no longer trigger unknown-club dialog on upload
- Batch upload continues after club dialog dismissal
- Unified athlete ID reconciliation card (grouped by name, per-instance dropdowns, confidence-gated auto-fix)
- Missing AA totals for gymnasts with all apparatus scores but no stored AA score
- "MAG Level3" (no space) not normalized to "Level 3" (resolver regex fix)
- Club name duplicates: 10+ missing aliases added to clubs_and_regions.json
- Next page button immediately reset to page 1 (page-reset effect tracking currentPage)
