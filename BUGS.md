All bugs reported in this session are fixed. See `git log` for details.

**Known issues:**
- Inline edit (name/GNZ ID/club) saves to DB but frontend doesn't feel reactive — cache invalidation on `wide-all` works but the table may still show stale data after save. Needs investigation into the data reload path (`doLoad()` / `applyTab()`).
- Mixups with multiple names sharing the same GNZ ID: Phase 0/1 stopped the bleeding (no more destructive name-keyed auto-merge; collision detection on upload; `repair_identities.py` restores split IDs/casing for events with source JSONs). The remaining same-ID-different-people cases that are *in the source data itself* (e.g. `252164` = Arden + Daniel) and the 99 events without a source file still need Phase 2 (athlete identity table) + manual admin review.

**Previously fixed:**
- `repair_identities.py` v1 trusted each source file 100% per-event, so a single file's typo could overwrite a consistent DB ID (e.g. `Alexandra Boys` → 7-digit `6511229`, or near-ties like `emily crisp` 2:3). Diffing the result against a per-(name, club) source consensus exposed 1,016 of 1,787 ID changes moving *away* from consensus. Rewritten to be **consensus-driven**: majority ID across all source files per `(name, club)`, winner must beat runner-up ≥2x; verified the corrected end state has 0 rows differing from consensus.
- Name mangling: `_clean_name` used `w.capitalize()` which lowercased internal caps (`Eva McEwan` → `Eva Mcewan`). Fixed with `_title_case_token` that preserves tokens with an internal uppercase letter; existing rows repaired via `python -m app.repair_identities`
- Destructive name-keyed reconcile: two different people sharing a name (e.g. two Madison Lynches at one event) were irreversibly merged into one GNZ ID after every upload. `reconcile_athletes()` is now evidence-based — same-event ID collision or discipline conflict → `conflicts` with a `reason`, never merged
- Ingest backfill assigned missing IDs by name even when the name mapped to multiple IDs — now only backfills when a name maps to exactly one distinct numeric ID
- Bulk URL upload: events with unknown clubs vanished after Save & Retry — during a batch URL import, any event that opened the unknown-club dialog and was resolved via *Save & Retry* (or *Keep all original*) disappeared from the upload list. The retried event IS imported, but `handleSources()` reset `uploads = []` at the start of every batch and the batch resume ran a fresh `handleSources(rest)` that wiped all previously processed cards (the retried event + any earlier successes). A failed retry (swallowed `saveAliases()` error → re-upload 409s again, or a Scoreholder re-fetch error) was silently hidden the same way. Fixed by adding a `reset` param to `handleSources()` (default `true`); `saveAndRetry()`/`skipUnknown()` resume with `reset=false` so retried events and their success/error results stay visible. Backend was verified correct in isolation: 409 → alias saved → re-import inserts the event.
- `find_unknown_clubs()` read `orgId`/`participantId` fields that never exist in real Scoreholder exports (they use `_id` on `eventOrganizations`, `_id`+`organizationId` on `eventParticipants`) → always returned `[]`, so variant club names silently passed through uploads. Fixed to use real field names; uploads now 409 with the club-mapping dialog for genuinely unknown clubs
- Club name variants (Waitākere, Counties Manakau, Easter Suburbs, Kataia, double-spaces, etc.) showing as separate clubs on `/clubs` — ~40 aliases added to `clubs_and_regions.json`, DB reconciled via `python -m app.reconcile_clubs` (50 names resolved, distinct clubs 126 → 80); `Gymsport Manukau` retargets to regional `Counties - Manukau`; Bay of Islands canonical renamed to plural
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
- ICE Gymsports North/South Canterbury normalized to "ICE Gymsports" (aliases added to clubs_and_regions.json, DB reconciled — no North/South variants remain)
- "Wanganui / Manawatu" club on `/clubs` renamed to "Manawatu - Whanganui" — it was the Manawatu - Whanganui provincial team, stored under the wrong name. Canonical name + aliases updated in clubs_and_regions.json, 306 DB rows reconciled (now 495 rows as one team, shown as the Provincial Team pill next to the header)