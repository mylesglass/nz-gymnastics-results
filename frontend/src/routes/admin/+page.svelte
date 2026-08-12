<script lang="ts">
  import { onMount } from "svelte";
  import { getStats, getIdentityReview, mergeAthletes, splitAthlete, refreshCache } from "$lib/api";
  import type { AthleteReviewInfo, IdentityReview, MultiIdAthlete } from "$lib/api";

  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let review = $state<IdentityReview | null>(null);
  let reviewLoading = $state(true);
  let reviewError = $state<string | null>(null);
  let reviewToast = $state<string | null>(null);
  let cacheToast = $state<string | null>(null);
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

  onMount(async () => {
    try {
      stats = await getStats();
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
    await loadReview();
  });

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
  }

  function showToast(kind: "success" | "error", message: string) {
    clearTimeout(toastTimer);
    reviewToast = `${kind === "success" ? "✅" : "⚠"} ${message}`;
    toastTimer = setTimeout(() => { reviewToast = null; }, 5000);
  }

  async function runMerge(survivor: AthleteReviewInfo, merged: AthleteReviewInfo) {
    busy = true;
    try {
      const res = await mergeAthletes(survivor.athlete_id, merged.athlete_id);
      showToast("success", `Merged ${res.merged_rows} rows — kept "${survivor.name}"`);
      await loadReview();
    } catch (e) {
      showToast("error", String(e));
    } finally {
      busy = false;
    }
  }

  async function mergeGroupInto(group: { name?: string; gnz_id?: string; athletes: AthleteReviewInfo[] }, survivor: AthleteReviewInfo) {
    busy = true;
    try {
      let total = 0;
      for (const other of group.athletes) {
        if (other.athlete_id === survivor.athlete_id) continue;
        const res = await mergeAthletes(survivor.athlete_id, other.athlete_id);
        total += res.merged_rows;
      }
      showToast("success", `Merged ${total} rows — kept "${survivor.name}"`);
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

  async function runRefresh() {
    clearTimeout(toastTimer);
    try {
      await refreshCache();
      stats = await getStats();
      await loadReview();
      cacheToast = "Cache refreshed — all data is now fresh";
    } catch (e) {
      cacheToast = `Error: ${e}`;
    }
    toastTimer = setTimeout(() => { cacheToast = null; }, 4000);
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

<svelte:head>
  <title>Admin — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-4xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Admin Dashboard</h1>
  <p class="text-base-content/70 mb-6">Server overview and management.</p>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if error}
    <div role="alert" class="alert alert-error">
      <span>{error}</span>
    </div>
  {:else}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/70 text-xs">Events</div>
        <div class="stat-value text-2xl">{stats?.total_events ?? "—"}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/70 text-xs">Gymnasts</div>
        <div class="stat-value text-2xl">{(stats?.total_gymnasts ?? 0).toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/70 text-xs">Scores</div>
        <div class="stat-value text-2xl">{(stats?.total_scores ?? 0).toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/70 text-xs">Clubs</div>
        <div class="stat-value text-2xl">{stats?.total_clubs ?? "—"}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <a href="/admin/users" class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer">
        <div class="card-body">
          <h2 class="card-title">👥 User Management</h2>
          <p class="text-sm text-base-content/70">Create, update, and delete user accounts</p>
        </div>
      </a>
      <a href="/upload" class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer">
        <div class="card-body">
          <h2 class="card-title">📄 Upload Event</h2>
          <p class="text-sm text-base-content/70">Upload a Scoreholder JSON file</p>
        </div>
      </a>
      <button onclick={runRefresh} class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer text-left">
        <div class="card-body">
          <h2 class="card-title">🔄 Refresh Cache</h2>
          <p class="text-sm text-base-content/70">Clear backend cache so all pages show the latest data</p>
        </div>
      </button>
      <a href="/admin/activity" class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer">
        <div class="card-body">
          <h2 class="card-title">📋 Activity Log</h2>
          <p class="text-sm text-base-content/70">Pages and API requests made by logged-in users</p>
        </div>
      </a>
    </div>

    <div class="card bg-base-200 border border-base-300">
      <div class="card-body">
        <div class="flex items-center gap-3 mb-2">
          <h2 class="card-title">🆔 Identity Review</h2>
          {#if !reviewLoading && totalCount > 0}
            <div class="badge badge-warning gap-1">{totalCount}</div>
          {/if}
        </div>
        <p class="text-sm text-base-content/70 mb-3">
          Athlete-level identity conflicts in both directions — similar names that may be one
          gymnast, the same name on multiple athletes, the same ID on multiple athletes, and
          athletes carrying more than one ID. Review the evidence, then merge confirmed
          duplicates or split athletes that actually contain two people.
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
              <h3 class="font-semibold text-sm">Similar names</h3>
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
                        <td>{@render evidence(m.athlete_a)}</td>
                        <td>{@render evidence(m.athlete_b)}</td>
                        <td>{m.score.toFixed(2)}</td>
                        <td class="flex flex-col gap-1 min-w-44">
                          <button class="btn btn-primary btn-xs" onclick={() => runMerge(m.athlete_b, m.athlete_a)} disabled={busy}>Keep {m.name_a}</button>
                          <button class="btn btn-ghost btn-xs" onclick={() => runMerge(m.athlete_a, m.athlete_b)} disabled={busy}>Keep {m.name_b}</button>
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
              <h3 class="font-semibold text-sm">Same name, multiple athletes</h3>
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
                              <button class="btn btn-primary btn-xs" onclick={() => mergeGroupInto(g, survivor)} disabled={busy}>
                                Merge others into {survivor.name}
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
              <h3 class="font-semibold text-sm">Same GNZ ID, multiple athletes</h3>
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
                              <button class="btn btn-primary btn-xs" onclick={() => mergeGroupInto(g, survivor)} disabled={busy}>
                                Merge others into {survivor.name}
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
              <h3 class="font-semibold text-sm">One athlete with multiple IDs — may need a split</h3>
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
    </div>
  {/if}
</div>

{#if splitTarget}
  <div class="card bg-base-200 border border-base-300 mt-4 mx-auto max-w-4xl" role="dialog" aria-modal="false" aria-labelledby="split-title">
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

{#snippet evidence(a: AthleteReviewInfo)}
  <div class="text-xs space-y-0.5">
    <div>
      <a href="/gymnast/{a.slug}" class="link link-hover font-medium">{a.name}</a>
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

{#if cacheToast}
  <div class="toast toast-bottom toast-start z-50" role="status">
    <div class="alert alert-info text-sm">
      <span>{cacheToast}</span>
    </div>
  </div>
{/if}
