<script lang="ts">
  import { onMount } from "svelte";
  import { getStats, reconcileAthletes, checkDuplicates, fixDuplicates, applyFixes } from "$lib/api";
  import type { DuplicateGroup } from "$lib/api";

  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let reconciling = $state(false);
  let reconcileResult = $state<{
    total_athletes: number;
    ids_corrected: number;
    names_unified: number;
    conflicts: Array<{ name: string; previous_ids: string[]; chosen_id: string | null; rows_updated: number }>;
  } | null>(null);
  let reconcileError = $state<string | null>(null);
  let showConflicts = $state(false);

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

  function bestId(d: DuplicateGroup): string {
    const sorted = Object.entries(d.id_counts).sort((a, b) => b[1] - a[1] || (b[0].localeCompare(a[0])));
    return sorted[0][0];
  }

  function groupKey(d: DuplicateGroup): string {
    return `${d.name}|${d.club}|${d.level_category}`;
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
        selections[groupKey(d)] = bestId(d);
      }
    } catch (e) {
      dupError = String(e);
    } finally {
      dupLoading = false;
    }
  });

  async function runReconcile() {
    reconciling = true;
    reconcileResult = null;
    reconcileError = null;
    try {
      reconcileResult = await reconcileAthletes();
    } catch (e) {
      reconcileError = String(e);
    } finally {
      reconciling = false;
    }
  }

  async function runFix() {
    fixing = true;
    fixResult = null;
    lowConfidence = [];
    try {
      const result = await fixDuplicates();
      if (result.fixed > 0) {
        fixResult = { fixed: result.fixed };
      }
      lowConfidence = result.low_confidence;
      duplicates = await checkDuplicates();
      for (const d of duplicates) {
        selections[groupKey(d)] = bestId(d);
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
      const fixes = Object.entries(selections)
        .filter(([key, chosen]) => {
          const parts = key.split("|");
          const d = lowConfidence.find(g => groupKey(g) === key)
            || duplicates.find(g => groupKey(g) === key);
          return d && chosen !== bestId(d);
        })
        .map(([key, chosen_id]) => {
          const parts = key.split("|");
          return { name: parts[0], club: parts[1], level_category: parts[2], chosen_id };
        });
      if (fixes.length > 0) {
        applyResult = await applyFixes(fixes);
      }
      lowConfidence = [];
      duplicates = await checkDuplicates();
      for (const d of duplicates) {
        selections[groupKey(d)] = bestId(d);
      }
    } catch (e) {
      dupError = String(e);
    } finally {
      applying = false;
    }
  }

  function selectedIdsChanged(d: DuplicateGroup) {
    // Only used for low-confidence groups to track if dropdown changed
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
        <h2 class="card-title">🔄 Reconcile Athlete IDs</h2>
        <p class="text-sm text-base-content/70 mb-3">
          Scan all events and unify inconsistent GNZ IDs by matching athlete names.
          Athletes with multiple IDs across events will be consolidated to a single ID.
        </p>

        {#if reconcileResult}
          <div role="alert" class="alert alert-success mb-3">
            <div class="flex flex-col gap-1 w-full">
              <span class="font-medium">✅ Reconciliation complete</span>
              <span class="text-sm">{reconcileResult.total_athletes} athletes scanned</span>
              <span class="text-sm">{reconcileResult.names_unified} names unified</span>
              <span class="text-sm">{reconcileResult.ids_corrected} rows corrected</span>
              {#if reconcileResult.conflicts.length > 0}
                <span class="text-sm text-warning">{reconcileResult.conflicts.length} conflicts (tied IDs — review manually)</span>
                <button class="btn btn-ghost btn-xs self-start" onclick={() => (showConflicts = !showConflicts)}>
                  {showConflicts ? "Hide" : "View"} conflicts
                </button>
                {#if showConflicts}
                  <div class="overflow-x-auto mt-2">
                    <table class="table table-xs">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>IDs</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each reconcileResult.conflicts as c}
                          <tr>
                            <td class="font-medium">{c.name}</td>
                            <td>{c.previous_ids.join(", ")}</td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {/if}
              {:else}
                <span class="text-sm text-base-content/60">No conflicts found</span>
              {/if}
            </div>
          </div>
        {/if}

        {#if reconcileError}
          <div role="alert" class="alert alert-error mb-3">
            <span>{reconcileError}</span>
          </div>
        {/if}

        <button
          class="btn btn-primary btn-sm"
          onclick={runReconcile}
          disabled={reconciling}
        >
          {reconciling ? "Reconciling..." : "Run Reconciliation"}
        </button>
      </div>
    </div>

    <div class="card bg-base-200 border border-base-300 mt-4">
      <div class="card-body">
        <div class="flex items-center gap-3 mb-3">
          <h2 class="card-title">🔍 Potential Duplicates</h2>
          {#if !dupLoading && duplicates.length > 0}
            <div class="badge badge-warning gap-1">{duplicates.length}</div>
          {/if}
        </div>
        <p class="text-sm text-base-content/70 mb-3">
          Gymnasts with the same name, club, and level but different GNZ IDs.
        </p>

        {#if dupLoading}
          <span class="loading loading-spinner loading-sm"></span>
        {:else if dupError}
          <div role="alert" class="alert alert-error mb-3">
            <span>{dupError}</span>
          </div>
        {:else if duplicates.length > 0 || lowConfidence.length > 0}
          <button class="btn btn-ghost btn-xs self-start mb-2" onclick={() => (showDuplicates = !showDuplicates)}>
            {showDuplicates ? "Hide" : "View"} {duplicates.length} duplicate groups
          </button>

          {#if showDuplicates}
            <div class="overflow-x-auto mb-3">
              <table class="table table-xs">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Club</th>
                    <th>Step</th>
                    <th>Conflicting IDs</th>
                    <th>Correct ID</th>
                    <th>Total Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {#each duplicates as d}
                    {@const key = groupKey(d)}
                    {@const isLow = lowConfidence.some(g => groupKey(g) === key)}
                    <tr class={isLow ? "bg-warning/5" : ""}>
                      <td class="font-medium">{d.name}</td>
                      <td>{d.club}</td>
                      <td>{d.level_category}</td>
                      <td>
                        {#each Object.entries(d.id_counts) as [id, count], i}
                          {i > 0 ? ", " : ""}{id} <span class="text-base-content/50 text-xs">({count})</span>
                        {/each}
                      </td>
                      <td>
                        <select
                          class="select select-bordered select-xs w-32"
                          bind:value={selections[key]}
                        >
                          {#each Object.keys(d.id_counts) as id}
                            <option value={id}>{id}</option>
                          {/each}
                        </select>
                      </td>
                      <td>{d.total_rows}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}

          {#if fixResult}
            <div role="alert" class="alert alert-success mb-2">
              <span>✅ Fixed {fixResult.fixed} rows (high confidence)</span>
            </div>
          {/if}

          {#if applyResult}
            <div role="alert" class="alert alert-success mb-2">
              <span>✅ Applied {applyResult.applied} row fixes</span>
            </div>
          {/if}

          {#if lowConfidence.length > 0}
            <div role="alert" class="alert alert-warning mb-2">
              <span>⚠ {lowConfidence.length} groups need manual review (confidence too low to auto-fix)</span>
            </div>
          {/if}

          <div class="flex gap-2">
            <button
              class="btn btn-primary btn-sm"
              onclick={runFix}
              disabled={fixing}
            >
              {fixing ? "Fixing..." : "Quick Fix"}
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
          <p class="text-sm text-base-content/60">No duplicates found</p>
        {/if}
      </div>
    </div>
  {/if}
</div>
