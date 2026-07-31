All bugs reported in this session are fixed. See `git log` for details.

**Known issues:**
- Inline edit (name/GNZ ID/club) saves to DB but frontend doesn't feel reactive — cache invalidation on `wide-all` works but the table may still show stale data after save. Needs investigation into the data reload path (`doLoad()` / `applyTab()`).

**Previously fixed:**
- `fetchToken` in `wellington-ranking/+page.svelte` made `$state` caused infinite API request loop (incrementing it re-triggered the `$effect`); must stay a plain `let`
- `ApparatusSpecialistRow` referenced in `main.py` but not imported → `NameError` 500 on `/api/rankings/wellington` for WAG STEP 8–10; fixed import + added endpoint regression test
- Cross-site POST form submissions blocked on upload — SvelteKit default CSRF; fixed with `csrf: { checkOrigin: false }` in `svelte.config.js`
- STEP dropdown showed `STEP 1, STEP 10, STEP 2...` (alphabetical) — frontend `sortSteps()` now orders STEP 1–10 numerically, then Youth/Junior/Senior
- Apparatus specialist tooltips squashed + scrollbars — replaced custom absolute-positioned tooltip with DaisyUI `tooltip`, removed `overflow-x-auto` wrapper
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
