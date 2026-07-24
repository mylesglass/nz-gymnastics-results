<script lang="ts">
  import { onMount } from "svelte";
  import { getRankings, getRankingSteps, type RankingRow } from "$lib/api";
  import { selectedYear } from "$lib/year";

  let loading = $state(true);
  let error = $state("");

  let discipline = $state("WAG");
  let year = $state<string | null>(null);
  let steps = $state<string[]>([]);
  let selectedStep = $state("");
  let rankings = $state<RankingRow[]>([]);

  let subYear: (() => void) | undefined;

  onMount(() => {
    subYear = selectedYear.subscribe((v) => {
      year = v;
      if (v) loadSteps();
    });
    return () => subYear?.();
  });

  async function loadSteps() {
    if (!year) return;
    try {
      const data = await getRankingSteps(Number(year), discipline);
      steps = data.steps;
      if (steps.length > 0 && !steps.includes(selectedStep)) {
        selectedStep = steps[0];
      }
    } catch {
      steps = [];
    }
  }

  let loadingRankings = $state(false);

  async function loadRankings() {
    if (!year || !selectedStep) return;
    loadingRankings = true;
    error = "";
    try {
      const data = await getRankings(Number(year), selectedStep, discipline);
      rankings = data.rankings;
    } catch (e) {
      error = "Failed to load rankings.";
      rankings = [];
    } finally {
      loadingRankings = false;
    }
  }

  function switchDisc(d: string) {
    discipline = d;
    if (year) loadSteps();
  }

  $effect(() => {
    if (year && selectedStep && discipline) {
      loadRankings();
    }
  });
</script>

<svelte:head>
  <title>Rankings — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Rankings</h1>
  <p class="text-base-content/70 mb-6">Season rankings — top 2 All Around scores per gymnast (excludes Nationals).</p>

  <div class="flex flex-wrap items-center gap-3 mb-6">
    <div role="tablist" class="tabs tabs-box">
      <button role="tab" class="tab tab-sm {discipline === 'WAG' ? 'tab-active' : ''}" onclick={() => switchDisc('WAG')}>WAG</button>
      <button role="tab" class="tab tab-sm {discipline === 'MAG' ? 'tab-active' : ''}" onclick={() => switchDisc('MAG')}>MAG</button>
    </div>

    {#if steps.length > 0}
      <select class="select select-bordered select-sm" bind:value={selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>
    {:else if year}
      <span class="text-sm text-base-content/50">No STEP levels available</span>
    {/if}

    {#if !year}
      <span class="text-sm text-base-content/50">Select a year from the nav</span>
    {/if}
  </div>

  {#if loadingRankings}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if error}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-12">
        <p class="text-error">{error}</p>
      </div>
    </div>
  {:else if rankings.length === 0}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-12">
        <p class="text-base-content/70">No rankings data for this selection.</p>
      </div>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="table table-zebra">
        <thead>
          <tr>
            <th class="w-12">Rank</th>
            <th>Name</th>
            <th>GNZ ID</th>
            <th>Club</th>
            <th class="text-right">Score 1</th>
            <th class="text-right">Score 2</th>
            <th class="text-right">Total</th>
          </tr>
        </thead>
        <tbody>
          {#each rankings as r}
            <tr class="hover:bg-base-300">
              <td class="font-bold text-lg">{r.rank}</td>
              <td class="font-medium">{r.name}</td>
              <td class="text-base-content/60 text-xs">{r.gnz_id}</td>
              <td>{r.club}</td>
              {#each r.scores as score, i}
                <td class="text-right">
                  <div class="dropdown dropdown-hover dropdown-left">
                    <div class="cursor-pointer font-mono" tabindex="0">
                      {score.toFixed(3)}
                    </div>
                    <div
                      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2 text-xs whitespace-nowrap"
                      tabindex="0"
                    >
                      {r.competitions[i] || "Unknown competition"}
                    </div>
                  </div>
                </td>
              {/each}
              {#if r.scores.length < 2}
                <td class="text-right text-base-content/40">—</td>
              {/if}
              <td class="text-right font-semibold">{r.total.toFixed(3)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>