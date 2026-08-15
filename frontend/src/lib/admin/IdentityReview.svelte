<script lang="ts">
  import { onMount } from "svelte";
  import { getIdentityReview, mergeAthletes, mergePreview, splitAthlete } from "$lib/api";
  import type { AthleteReviewInfo, IdentityReview, MergePreview, MultiIdAthlete } from "$lib/api";
  import { gymnastPath } from "$lib/seo";
  import Dialog from "$lib/Dialog.svelte";

  let {
    onCount,
  }: {
    onCount?: (count: number) => void;
  } = $props();

  let review = $state<IdentityReview | null>(null);
  let reviewLoading = $state(true);
  let reviewError = $state<string | null>(null);
  let reviewToast = $state<string | null>(null);
  let declinedKeys = $state<Set<string>>(new Set());
  let showSection = $state<Record<string, boolean>>({ similar: true, names: true, ids: true, multi: true });

  let toastTimer: ReturnType<typeof setTimeout> | undefined;
  let busy = $state(false);

  const totalCount = $derived(
    (review?.similar_names.length ?? 0) +
    (review?.name_conflicts.length ?? 0) +
    (review?.id_conflicts.length ?? 0) +
    (review?.multi_id_athletes.length ?? 0)
  );

  function groupKey(group: { name?: string; gnz_id?: string }): string {
    return group.name ?? group.gnz_id ?? "";
  }

  function isDismissed(group: { name?: string; gnz_id?: string }): boolean {
    return declinedKeys.has(groupKey(group));
  }

  function visiblePair(m: { name_a: string; name_b: string }): boolean {
    return !declinedKeys.has(`${m.name_a}|${m.name_b}`);
  }

  const visibleSimilar = $derived((review?.similar_names ?? []).filter(visiblePair));
  const visibleNameConflicts = $derived((review?.name_conflicts ?? []).filter(g => !isDismissed(g)));
  const visibleIdConflicts = $derived((review?.id_conflicts ?? []).filter(g => !isDismissed(g)));
  const visibleMultiId = $derived((review?.multi_id_athletes ?? []).filter(m => !isDismissed({ name: m.name })));

  onMount(loadReview);

  async function loadReview() {
    reviewLoading = true;
    try {
      review = await getIdentityReview();
      reviewError = null;
    } catch (e) {
      reviewError = String(e);
    } finally {
      reviewLoading = false;
    }
    onCount?.(totalCount);
  }

  function showToast(kind: "success" | "error", message: string) {
    clearTimeout(toastTimer);
    reviewToast = `${kind === "success" ? "✅" : "⚠"} ${message}`;
    toastTimer = setTimeout(() => { reviewToast = null; }, 5000);
  }

  // --- Merge confirm ---------------------------------------------------
  // Every merge goes through a preview dialog so the admin sees exactly which
  // rows change (name/GNZ ID before -> after, highlighted) before committing.
  let mergeSurvivor = $state<AthleteReviewInfo | null>(null);
  let mergeMerged = $state<AthleteReviewInfo[]>([]);
  let mergePreviewData = $state<MergePreview | null>(null);
  let mergePreviewLoading = $state(false);
  let mergePreviewError = $state<string | null>(null);

  async function requestMerge(survivor: AthleteReviewInfo, mergedList: AthleteReviewInfo[]) {
    if (mergedList.length === 0) return;
    mergeSurvivor = survivor;
    mergeMerged = mergedList;
    mergePreviewData = null;
    mergePreviewError = null;
    mergePreviewLoading = true;
    try {
      mergePreviewData = await mergePreview(
        survivor.athlete_id,
        mergedList.map(m => m.athlete_id)
      );
    } catch (e) {
      mergePreviewError = String(e);
    } finally {
      mergePreviewLoading = false;
    }
  }

  function closeMergeConfirm() {
    mergeSurvivor = null;
    mergeMerged = [];
    mergePreviewData = null;
    mergePreviewError = null;
  }

  async function applyMerge() {
    if (!mergeSurvivor) return;
    busy = true;
    try {
      let total = 0;
      for (const merged of mergeMerged) {
        const res = await mergeAthletes(mergeSurvivor.athlete_id, merged.athlete_id);
        total += res.merged_rows;
      }
      showToast("success", `Merged ${total} rows — kept "${mergeSurvivor.name}"`);
      closeMergeConfirm();
      await loadReview();
    } catch (e) {
      showToast("error", String(e));
    } finally {
      busy = false;
    }
  }

  function runDismiss(group: { name?: string; gnz_id?: string }) {
    declinedKeys.add(groupKey(group));
    declinedKeys = new Set(declinedKeys);
  }

  function runDismissPair(m: { name_a: string; name_b: string }) {
    declinedKeys.add(`${m.name_a}|${m.name_b}`);
    declinedKeys = new Set(declinedKeys);
  }

  // --- Split ------------------------------------------------------------
  let splitTarget = $state<MultiIdAthlete | null>(null);
  let splitBy = $state<"gnz_id" | "event_id" | "club_name">("gnz_id");
  let splitValue = $state<string>("");
  let splitNewId = $state<string>("");
  let splitError = $state<string | null>(null);

  const splitOptions = $derived.by(() => {
    if (!splitTarget) return [];
    if (splitBy === "gnz_id") return Object.entries(splitTarget.gnz_ids).map(([id, cnt]) => ({ value: id, label: `GNZ ID ${id} (${cnt} rows)` }));
    if (splitBy === "event_id") return splitTarget.event_ids.map(eid => ({ value: String(eid), label: `Event #${eid}` }));
    return splitTarget.clubs.map(c => ({ value: c, label: `Club: ${c}` }));
  });

  function openSplit(athlete: MultiIdAthlete) {
    splitTarget = athlete;
    splitBy = "gnz_id";
    splitNewId = "";
    splitError = null;
    splitValue = Object.keys(athlete.gnz_ids)[0] ?? "";
  }

  function closeSplit() {
    splitTarget = null;
  }

  async function runSplit() {
    if (!splitTarget) return;
    busy = true;
    splitError = null;
    try {
      const res = await splitAthlete({
        athlete_id: splitTarget.athlete_id,
        split_by: splitBy,
        value: splitValue,
        new_gnz_id: splitNewId.trim() || undefined,
      });
      showToast("success", `Split ${res.split_rows} rows into a new athlete`);
      closeSplit();
      await loadReview();
    } catch (e) {
      splitError = String(e);
    } finally {
      busy = false;
    }
  }
</script>

<div>
  <p class="text-sm text-base-content/70 mb-3">
    Athlete-level identity conflicts in both directions — similar names that may be one
    gymnast, the same name on multiple athletes, the same ID on multiple athletes, and
    athletes carrying more than one ID. Review the evidence, then merge confirmed
    duplicates or split athletes that actually contain two people.
    {#if !reviewLoading && totalCount > 0}
      <span class="badge badge-warning gap-1 ml-1">{totalCount}</span>
    {/if}
  </p>

  {#if reviewLoading}
    <span class="loading loading-spinner loading-sm"></span>
  {:else if reviewError}
    <div role="alert" class="alert alert-error mb-3">
      <span>{reviewError}</span>
    </div>
  {:else}
    <!-- Similar names -->
    {#if visibleSimilar.length > 0}
      <div class="flex items-center justify-between mt-2">
        <h4 class="font-semibold text-sm">Similar names</h4>
        <button class="btn btn-ghost btn-xs" onclick={() => (showSection.similar = !showSection.similar)} aria-expanded={showSection.similar}>
          {showSection.similar ? "Hide" : "Show"} {visibleSimilar.length}
        </button>
      </div>
      {#if showSection.similar}
        <div class="overflow-x-auto mb-3">
          <table class="table table-xs">
            <thead>
              <tr>
                <th>Name A</th>
                <th>Name B</th>
                <th>Similarity</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each visibleSimilar as m}
                <tr>
                  <td>
                    <div class="flex items-start gap-2">
                      <button class="btn btn-primary btn-xs h-auto min-h-0 whitespace-normal text-left leading-tight justify-start shrink-0" onclick={() => requestMerge(m.athlete_a, [m.athlete_b])} disabled={busy}>Keep {m.athlete_a.name}{m.athlete_a.gnz_id ? ` · ${m.athlete_a.gnz_id}` : ""}</button>
                      <div class="min-w-0">
                        {@render evidence(m.athlete_a)}
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="flex items-start gap-2">
                      <button class="btn btn-secondary btn-xs h-auto min-h-0 whitespace-normal text-left leading-tight justify-start shrink-0" onclick={() => requestMerge(m.athlete_b, [m.athlete_a])} disabled={busy}>Keep {m.athlete_b.name}{m.athlete_b.gnz_id ? ` · ${m.athlete_b.gnz_id}` : ""}</button>
                      <div class="min-w-0">
                        {@render evidence(m.athlete_b)}
                      </div>
                    </div>
                  </td>
                  <td>{m.score.toFixed(2)}</td>
                  <td>
                    <button class="btn btn-ghost btn-xs text-error" onclick={() => runDismissPair(m)}>Dismiss</button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {/if}

    <!-- Same name, multiple athletes -->
    {#if visibleNameConflicts.length > 0}
      <div class="flex items-center justify-between mt-2">
        <h4 class="font-semibold text-sm">Same name, multiple athletes</h4>
        <button class="btn btn-ghost btn-xs" onclick={() => (showSection.names = !showSection.names)} aria-expanded={showSection.names}>
          {showSection.names ? "Hide" : "Show"} {visibleNameConflicts.length}
        </button>
      </div>
      {#if showSection.names}
        <div class="overflow-x-auto mb-3">
          <table class="table table-xs">
            <thead>
              <tr>
                <th>Gymnast</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each visibleNameConflicts as g}
                <tr>
                  <td>
                    <div class="space-y-2">
                      {#each g.athletes as a}
                        {@render evidence(a)}
                      {/each}
                    </div>
                  </td>
                  <td class="align-top">
                    <div class="flex flex-col gap-1 min-w-44">
                      {#each g.athletes as survivor}
                        <button class="btn btn-primary btn-xs h-auto min-h-0 whitespace-normal text-left leading-tight justify-start" onclick={() => requestMerge(survivor, g.athletes.filter(a => a.athlete_id !== survivor.athlete_id))} disabled={busy}>
                          Merge others into {survivor.name}{survivor.gnz_id ? ` · ${survivor.gnz_id}` : ""}
                        </button>
                      {/each}
                      <button class="btn btn-ghost btn-xs text-error" onclick={() => runDismiss(g)}>Separate people — dismiss</button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {/if}

    <!-- Same ID, multiple athletes -->
    {#if visibleIdConflicts.length > 0}
      <div class="flex items-center justify-between mt-2">
        <h4 class="font-semibold text-sm">Same GNZ ID, multiple athletes</h4>
        <button class="btn btn-ghost btn-xs" onclick={() => (showSection.ids = !showSection.ids)} aria-expanded={showSection.ids}>
          {showSection.ids ? "Hide" : "Show"} {visibleIdConflicts.length}
        </button>
      </div>
      {#if showSection.ids}
        <div class="overflow-x-auto mb-3">
          <table class="table table-xs">
            <thead>
              <tr>
                <th>GNZ ID</th>
                <th>Gymnast</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each visibleIdConflicts as g}
                <tr>
                  <td class="font-medium align-top">{g.gnz_id}</td>
                  <td>
                    <div class="space-y-2">
                      {#each g.athletes as a}
                        {@render evidence(a)}
                      {/each}
                    </div>
                  </td>
                  <td class="align-top">
                    <div class="flex flex-col gap-1 min-w-44">
                      {#each g.athletes as survivor}
                        <button class="btn btn-primary btn-xs h-auto min-h-0 whitespace-normal text-left leading-tight justify-start" onclick={() => requestMerge(survivor, g.athletes.filter(a => a.athlete_id !== survivor.athlete_id))} disabled={busy}>
                          Merge others into {survivor.name}{survivor.gnz_id ? ` · ${survivor.gnz_id}` : ""}
                        </button>
                      {/each}
                      <button class="btn btn-ghost btn-xs text-error" onclick={() => runDismiss(g)}>Different people — dismiss</button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {/if}

    <!-- One athlete, multiple IDs -->
    {#if visibleMultiId.length > 0}
      <div class="flex items-center justify-between mt-2">
        <h4 class="font-semibold text-sm">One athlete with multiple IDs — may need a split</h4>
        <button class="btn btn-ghost btn-xs" onclick={() => (showSection.multi = !showSection.multi)} aria-expanded={showSection.multi}>
          {showSection.multi ? "Hide" : "Show"} {visibleMultiId.length}
        </button>
      </div>
      {#if showSection.multi}
        <div class="overflow-x-auto mb-3">
          <table class="table table-xs">
            <thead>
              <tr>
                <th>Gymnast</th>
                <th>IDs (rows)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each visibleMultiId as m}
                <tr>
                  <td>{@render evidence({ athlete_id: m.athlete_id, slug: m.slug, name: m.name, gnz_id: Object.keys(m.gnz_ids)[0], clubs: m.clubs, events: m.events, event_ids: m.event_ids, years: m.years, disciplines: m.disciplines, rows: m.rows, intent_years: [] })}</td>
                  <td class="text-xs">
                    {#each Object.entries(m.gnz_ids) as [id, cnt], j}
                      {j > 0 ? ", " : ""}<span class="font-mono">{id}</span><span class="text-base-content/70"> ({cnt})</span>
                    {/each}
                  </td>
                  <td>
                    <button class="btn btn-outline btn-xs" onclick={() => openSplit(m)} disabled={busy}>Split…</button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {/if}

    {#if totalCount === 0}
      <p class="text-sm text-base-content/70">No identity conflicts found. All athletes have consistent names and IDs.</p>
    {/if}
  {/if}
</div>

{#if splitTarget}
  <div class="card bg-base-200 border border-base-300 mt-4" role="dialog" aria-modal="false" aria-labelledby="split-title">
    <div class="card-body">
      <div class="flex items-center justify-between">
        <h3 id="split-title" class="card-title text-lg">Split "{splitTarget.name}"</h3>
        <button class="btn btn-ghost btn-xs" onclick={closeSplit} aria-label="Close split panel">✕</button>
      </div>
      <p class="text-sm text-base-content/70 mb-2">
        Move one group of this athlete's rows into a brand-new athlete. The new athlete keeps the
        same name; if no GNZ ID is supplied a synthetic one (starting with "S") is generated and
        can be corrected later with an inline edit.
      </p>

      <label for="split-by" class="text-sm font-medium">Split off rows by</label>
      <select id="split-by" class="select select-bordered select-sm mb-2" bind:value={splitBy} onchange={() => (splitValue = splitOptions[0]?.value ?? "")}>
        <option value="gnz_id">GNZ ID</option>
        <option value="event_id">Event</option>
        <option value="club_name">Club</option>
      </select>

      <label for="split-value" class="text-sm font-medium">Which rows move to the new athlete?</label>
      <select id="split-value" class="select select-bordered select-sm mb-2" bind:value={splitValue}>
        {#each splitOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
      </select>

      <label for="split-new-id" class="text-sm font-medium">New GNZ ID (optional)</label>
      <input id="split-new-id" class="input input-bordered input-sm mb-2" placeholder="e.g. 123456 — leave blank for a synthetic ID" bind:value={splitNewId} />

      {#if splitError}
        <div role="alert" class="alert alert-error mb-2 text-sm py-2">
          <span>{splitError}</span>
        </div>
      {/if}

      <div class="flex gap-2">
        <button class="btn btn-primary btn-sm" onclick={runSplit} disabled={busy || !splitValue}>
          {busy ? "Splitting..." : "Split into new athlete"}
        </button>
        <button class="btn btn-ghost btn-sm" onclick={closeSplit} disabled={busy}>Cancel</button>
      </div>
    </div>
  </div>
{/if}

{#if mergeSurvivor}
  <Dialog title={`Merge into ${mergeSurvivor.name}?`} onClose={closeMergeConfirm} maxWidth="max-w-2xl">
    <div class="text-sm space-y-3">
      <p class="text-base-content/70">
        Every row of the merged profile(s) is rewritten to the kept profile's name and GNZ ID.
        The merged profile's old URL redirects to the kept profile.
      </p>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div class="card bg-base-200 border border-base-300 p-3">
          <div class="text-xs font-semibold uppercase tracking-wide text-base-content/60 mb-1">Keep</div>
          <div class="font-medium">{mergeSurvivor.name}</div>
          <div class="text-xs text-base-content/70 font-mono">{mergeSurvivor.gnz_id || "no GNZ ID"}</div>
          <div class="text-xs text-base-content/70">
            {mergeSurvivor.rows} rows · {mergeSurvivor.events} event{mergeSurvivor.events === 1 ? "" : "s"}
            {#if mergeSurvivor.clubs.length > 0} · {mergeSurvivor.clubs.join(", ")}{/if}
          </div>
        </div>
        <div class="card bg-base-200 border border-base-300 p-3">
          <div class="text-xs font-semibold uppercase tracking-wide text-base-content/60 mb-1">Merged into it</div>
          {#each mergeMerged as m}
            <div class="mb-1.5">
              <div class="font-medium line-through text-base-content/60">{m.name}</div>
              <div class="text-xs text-base-content/70 font-mono line-through">{m.gnz_id || "no GNZ ID"}</div>
              <div class="text-xs text-base-content/70">{m.rows} rows · {m.events} event{m.events === 1 ? "" : "s"}</div>
            </div>
          {/each}
        </div>
      </div>

      {#if mergePreviewLoading}
        <div class="flex items-center gap-2 text-base-content/70">
          <span class="loading loading-spinner loading-sm"></span> Preparing change preview…
        </div>
      {:else if mergePreviewError}
        <div role="alert" class="alert alert-error text-sm py-2">
          <span>{mergePreviewError}</span>
        </div>
      {:else if mergePreviewData}
        {#each mergePreviewData.pairs as pair}
          {#if pair.changes.length > 0}
            <div>
              <div class="text-xs font-semibold uppercase tracking-wide text-base-content/60 mb-1">
                Rows that change — {pair.merged.name}
              </div>
              <div class="overflow-x-auto">
                <table class="table table-xs">
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Rows</th>
                      <th>Name</th>
                      <th>GNZ ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pair.changes as ch}
                      <tr>
                        <td class="max-w-52 truncate" title={ch.event_name}>{ch.event_name}</td>
                        <td>{ch.rows}</td>
                        <td>
                          {#if ch.old_name !== ch.new_name}
                            <span class="badge badge-warning badge-xs mr-1">changed</span>
                            <span class="line-through text-base-content/50">{ch.old_name}</span>
                            <span class="mx-0.5">→</span>
                            <span class="font-semibold">{ch.new_name}</span>
                          {:else}
                            {ch.new_name}
                          {/if}
                        </td>
                        <td>
                          {#if (ch.old_gnz_id || "") !== (ch.new_gnz_id || "")}
                            <span class="badge badge-warning badge-xs mr-1">changed</span>
                            <span class="line-through text-base-content/50 font-mono">{ch.old_gnz_id || "—"}</span>
                            <span class="mx-0.5">→</span>
                            <span class="font-semibold font-mono">{ch.new_gnz_id || "—"}</span>
                          {:else}
                            <span class="font-mono">{ch.new_gnz_id || "—"}</span>
                          {/if}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          {/if}
          {#if pair.intent_moves.length > 0}
            <p class="text-xs text-base-content/70">
              Wellington intent{pair.intent_moves.length > 1 ? "s" : ""} {pair.intent_moves.join(", ")} move{pair.intent_moves.length > 1 ? "" : "s"} to the kept profile.
            </p>
          {/if}
        {/each}
        <p class="text-xs text-base-content/60">
          {#if mergePreviewData.pairs.some(p => p.survivor_slug !== p.survivor.slug)}
            The kept profile's URL changes because it gains the merged GNZ ID — both old URLs redirect.
          {:else}
            The kept profile's URL stays the same; the merged profile's old URL redirects to it.
          {/if}
        </p>
      {/if}

      <div class="flex gap-2 justify-end">
        <button class="btn btn-ghost btn-sm" onclick={closeMergeConfirm} disabled={busy}>Cancel</button>
        <button class="btn btn-primary btn-sm" onclick={applyMerge} disabled={busy || mergePreviewLoading || !mergePreviewData}>
          {busy ? "Merging..." : `Merge ${mergeMerged.length} profile${mergeMerged.length === 1 ? "" : "s"} into ${mergeSurvivor.name}`}
        </button>
      </div>
    </div>
  </Dialog>
{/if}

{#snippet evidence(a: AthleteReviewInfo)}
  <div class="text-xs space-y-0.5">
    <div>
      <a href={gymnastPath(a.slug, a.gnz_id || "", a.name)} class="link link-hover font-medium">{a.name}</a>
      {#if a.gnz_id}<span class="text-base-content/60"> · {a.gnz_id}</span>{/if}
      {#if a.intent_years.length > 0}<span class="badge badge-primary badge-xs ml-1">intent</span>{/if}
    </div>
    <div class="text-base-content/70">
      {a.clubs.join(", ") || "no club"} · {a.events} event{a.events === 1 ? "" : "s"}
      {#if a.years.length > 0} ({a.years.join(", ")}){/if} · {a.rows} rows
      {#if a.disciplines.length > 0} · {a.disciplines.join("/")}{/if}
    </div>
  </div>
{/snippet}

{#if reviewToast}
  <div class="toast toast-bottom toast-end z-50" role="status">
    <div class="alert alert-success text-sm">
      <span>{reviewToast}</span>
    </div>
  </div>
{/if}
