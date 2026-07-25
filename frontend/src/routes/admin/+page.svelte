<script lang="ts">
  import { onMount } from "svelte";
  import { getStats, checkDuplicates, fixDuplicates, applyFixes, getSuggestedMerges, mergeNames } from "$lib/api";
  import type { DuplicateGroup, DuplicateInstance, SuggestedMerge } from "$lib/api";

  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let duplicates = $state<DuplicateGroup[]>([]);
  let dupLoading = $state(true);
  let dupError = $state<string | null>(null);
  let showDuplicates = $state(false);
  let fixing = $state(false);
  let fixResult = $state<{ fixed: number } | null>(null);
  let lowConfidence = $state<DuplicateGroup[]>([]);
  let selections = $state<Record<string, string>>({});
  let applying = $state(false);
  let applyResult = $state<{ applied: number } | null>(null);

  let merges = $state<SuggestedMerge[]>([]);
  let mergesLoading = $state(true);
  let mergesError = $state<string | null>(null);
  let showMerges = $state(false);
  let mergeToast = $state<string | null>(null);
  let declinedKeys = $state<Set<string>>(new Set());

  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  function instanceKey(inst: DuplicateInstance, name: string): string {
    return `${name}|${inst.club}|${inst.level_category}`;
  }

  function bestId(inst: DuplicateInstance): string {
    const sorted = Object.entries(inst.id_counts).sort(
      (a, b) => b[1] - a[1] || (b[0].localeCompare(a[0]))
    );
    return sorted[0][0];
  }

  function groupBestId(instances: DuplicateInstance[]): string {
    const all: Record<string, number> = {};
    for (const inst of instances) {
      for (const [id, cnt] of Object.entries(inst.id_counts)) {
        all[id] = (all[id] || 0) + cnt;
      }
    }
    const sorted = Object.entries(all).sort(
      (a, b) => b[1] - a[1] || (b[0].localeCompare(a[0]))
    );
    return sorted[0][0];
  }

  function isLowConfidence(d: DuplicateGroup): boolean {
    return lowConfidence.some(l => l.name === d.name);
  }

  function mergeKey(m: SuggestedMerge): string {
    return `${m.name_a}|${m.name_b}`;
  }

  let visibleMerges = $derived(merges.filter(m => !declinedKeys.has(mergeKey(m))));

  async function runMerge(keep: string, merge: string) {
    merges = merges.filter(m => !(m.name_a === merge && m.name_b === keep));
    clearTimeout(toastTimer);
    try {
      const res = await mergeNames(merge, keep);
      merges = await getSuggestedMerges();
      duplicates = await checkDuplicates();
      mergeToast = `Merged ${res.merged} rows, ${res.names_unified} names unified, ${res.ids_corrected} IDs corrected`;
    } catch (e) {
      mergeToast = `Error: ${e}`;
      merges = await getSuggestedMerges();
    }
    toastTimer = setTimeout(() => { mergeToast = null; }, 4000);
  }

  function runDecline(m: SuggestedMerge) {
    declinedKeys.add(mergeKey(m));
    declinedKeys = new Set(declinedKeys);
  }

  onMount(async () => {
    try {
      stats = await getStats();
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
    try {
      duplicates = await checkDuplicates();
      for (const d of duplicates) {
        for (const inst of d.instances) {
          selections[instanceKey(inst, d.name)] = bestId(inst);
        }
      }
    } catch (e) {
      dupError = String(e);
    } finally {
      dupLoading = false;
    }
    try {
      merges = await getSuggestedMerges();
    } catch (e) {
      mergesError = String(e);
    } finally {
      mergesLoading = false;
    }
  });

  async function runFix() {
    fixing = true;
    fixResult = null;
    lowConfidence = [];
    try {
      const result = await fixDuplicates();
      if (result.fixed > 0) fixResult = { fixed: result.fixed };
      lowConfidence = result.low_confidence;
      duplicates = await checkDuplicates();
      for (const d of duplicates) {
        for (const inst of d.instances) {
          selections[instanceKey(inst, d.name)] = bestId(inst);
        }
      }
    } catch (e) {
      dupError = String(e);
    } finally {
      fixing = false;
    }
  }

  async function runApply() {
    applying = true;
    applyResult = null;
    try {
      const fixes: Array<{ name: string; club: string; level_category: string; chosen_id: string }> = [];
      for (const d of duplicates) {
        for (const inst of d.instances) {
          const key = instanceKey(inst, d.name);
          const chosen = selections[key];
          if (chosen && chosen !== bestId(inst)) {
            fixes.push({ name: d.name, club: inst.club, level_category: inst.level_category, chosen_id: chosen });
          }
        }
      }
      if (fixes.length > 0) applyResult = await applyFixes(fixes);
      lowConfidence = [];
      duplicates = await checkDuplicates();
      for (const d of duplicates) {
        for (const inst of d.instances) {
          selections[instanceKey(inst, d.name)] = bestId(inst);
        }
      }
    } catch (e) {
      dupError = String(e);
    } finally {
      applying = false;
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
        <div class="stat-title text-base-content/60 text-xs">Events</div>
        <div class="stat-value text-2xl">{stats?.total_events ?? "—"}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Gymnasts</div>
        <div class="stat-value text-2xl">{(stats?.total_gymnasts ?? 0).toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Scores</div>
        <div class="stat-value text-2xl">{(stats?.total_scores ?? 0).toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Clubs</div>
        <div class="stat-value text-2xl">{stats?.total_clubs ?? "—"}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
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
    </div>

    <div class="card bg-base-200 border border-base-300">
      <div class="card-body">
        <div class="flex items-center gap-3 mb-3">
          <h2 class="card-title">🔍 Athlete ID Reconciliation</h2>
          {#if !dupLoading && duplicates.length > 0}
            <div class="badge badge-warning gap-1">{duplicates.length}</div>
          {/if}
        </div>
        <p class="text-sm text-base-content/70 mb-3">
          Gymnast names with multiple GNZ IDs — likely data entry errors where the wrong ID was assigned.
          Groups with strong evidence (one ID >2x more common) are auto-fixed; others need manual review.
        </p>

        {#if dupLoading}
          <span class="loading loading-spinner loading-sm"></span>
        {:else if dupError}
          <div role="alert" class="alert alert-error mb-3">
            <span>{dupError}</span>
          </div>
        {:else if duplicates.length > 0}
          <button class="btn btn-ghost btn-xs self-start mb-2" onclick={() => (showDuplicates = !showDuplicates)}>
            {showDuplicates ? "Hide" : "View"} {duplicates.length} athlete groups
          </button>

          {#if showDuplicates}
            <div class="overflow-x-auto mb-3">
              <table class="table table-xs">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Club / Step</th>
                    <th>IDs (count)</th>
                    <th>Correct ID</th>
                    <th>Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {#each duplicates as d}
                    {@const low = isLowConfidence(d)}
                    {#each d.instances as inst, i}
                      <tr class={low ? "bg-warning/5" : ""}>
                        {#if i === 0}
                          <td class="font-medium align-top" rowspan={d.instances.length}>{d.name}</td>
                        {/if}
                        <td class="text-xs">{inst.club}<br><span class="text-base-content/50">{inst.level_category}</span></td>
                        <td class="text-xs">
                          {#each Object.entries(inst.id_counts) as [id, cnt], j}
                            {j > 0 ? ", " : ""}<a href="/gymnast/{id}" class="link link-hover">{id}</a><span class="text-base-content/50"> ({cnt})</span>
                          {/each}
                        </td>
                        <td>
                          <select
                            class="select select-bordered select-xs w-28"
                            bind:value={selections[instanceKey(inst, d.name)]}
                          >
                            {#each Object.keys(inst.id_counts) as id}
                              <option value={id}>{id}</option>
                            {/each}
                          </select>
                        </td>
                        <td class="text-xs">{inst.total_rows}</td>
                      </tr>
                    {/each}
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}

          {#if fixResult}
            <div role="alert" class="alert alert-success mb-2">
              <span>✅ Auto-fixed {fixResult.fixed} rows (high confidence)</span>
            </div>
          {/if}

          {#if applyResult}
            <div role="alert" class="alert alert-success mb-2">
              <span>✅ Applied {applyResult.applied} manual fixes</span>
            </div>
          {/if}

          {#if lowConfidence.length > 0}
            <div role="alert" class="alert alert-warning mb-2">
              <span>⚠ {lowConfidence.length} groups need manual review — confidence too low to auto-fix. Use the dropdowns above to select the correct ID, then click "Apply Selected Fixes".</span>
            </div>
          {/if}

          <div class="flex gap-2">
            <button
              class="btn btn-primary btn-sm"
              onclick={runFix}
              disabled={fixing}
            >
              {fixing ? "Running..." : "Quick Fix"}
            </button>
            <button
              class="btn btn-outline btn-sm"
              onclick={runApply}
              disabled={applying || duplicates.length === 0}
            >
              {applying ? "Applying..." : "Apply Selected Fixes"}
            </button>
          </div>
        {:else}
          <p class="text-sm text-base-content/60">No ID inconsistencies found. All gymnasts have consistent GNZ IDs.</p>
        {/if}
      </div>
    </div>

    <div class="card bg-base-200 border border-base-300 mt-4">
      <div class="card-body">
        <h2 class="card-title">🔗 Suggested Merges</h2>
        <p class="text-sm text-base-content/70 mb-3">
          Names that may refer to the same gymnast — review and merge if correct.
        </p>

        {#if mergesLoading}
          <span class="loading loading-spinner loading-sm"></span>
        {:else if mergesError}
          <div role="alert" class="alert alert-error mb-3">
            <span>{mergesError}</span>
          </div>
        {:else if visibleMerges.length > 0}
          <button class="btn btn-ghost btn-xs self-start mb-2" onclick={() => (showMerges = !showMerges)}>
            {showMerges ? "Hide" : "View"} {visibleMerges.length} suggestions
          </button>
          {#if showMerges}
            <div class="overflow-x-auto">
              <table class="table table-xs">
                <thead>
                  <tr>
                    <th>Name A</th>
                    <th>Name B</th>
                    <th>Similarity</th>
                    <th>IDs</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {#each visibleMerges as m}
                    <tr>
                      <td class="font-medium">{m.name_a}<span class="text-xs text-base-content/50 ml-1">({m.rows_a})</span></td>
                      <td class="font-medium">{m.name_b}<span class="text-xs text-base-content/50 ml-1">({m.rows_b})</span></td>
                      <td>{m.score.toFixed(2)}</td>
                      <td class="text-xs">
                        {#each m.gnz_ids_a as id, i}{i > 0 ? ", " : ""}<a href="/gymnast/{id}" class="link link-hover">{id}</a>{/each}
                        &rarr;
                        {#each m.gnz_ids_b as id, i}{i > 0 ? ", " : ""}<a href="/gymnast/{id}" class="link link-hover">{id}</a>{/each}
                      </td>
                      <td class="flex gap-1">
                        <button
                          class="btn btn-ghost btn-xs"
                          onclick={() => runMerge(m.name_a, m.name_b)}
                        >
                          Keep A
                        </button>
                        <button
                          class="btn btn-primary btn-xs"
                          onclick={() => runMerge(m.name_b, m.name_a)}
                        >
                          Keep B
                        </button>
                        <button
                          class="btn btn-ghost btn-xs text-error"
                          onclick={() => runDecline(m)}
                        >
                          Decline
                        </button>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {:else if merges.length > 0 && visibleMerges.length === 0}
          <p class="text-sm text-base-content/60">All suggestions dismissed. Refresh the page to see new suggestions.</p>
        {:else}
          <p class="text-sm text-base-content/60">No similar name pairs found.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>

{#if mergeToast}
  <div class="toast toast-bottom toast-end z-50">
    <div class="alert alert-success text-sm">
      <span>{mergeToast}</span>
    </div>
  </div>
{/if}
