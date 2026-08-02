<script lang="ts">
  import { onMount } from "svelte";
  import { getRankings, getRankingSteps, type RankingRow } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_PALETTES } from "$lib/regions";
  import ExportMenu from "$lib/ExportMenu.svelte";

  const CSV_HEADERS: Record<string, string> = {
    rank: "Rank", name: "Name", gnz_id: "GNZ ID", club: "Club",
    region: "Region",
    score1: "Score 1", comp1: "Competition 1",
    score2: "Score 2", comp2: "Competition 2",
    total: "Total", average: "Average",
  };

  const EXPORT_KEYS = ["rank", "name", "gnz_id", "club", "region", "score1", "comp1", "score2", "comp2", "total", "average"];

  let loading = $state(true);
  let error = $state("");

  let discipline = $state("WAG");
  let year = $state<string | null>(null);
  let steps = $state<string[]>([]);
  let selectedStep = $state("");
  let rankings = $state<RankingRow[]>([]);
  let years = $state<string[]>([]);

  let subYear: (() => void) | undefined;
  let subYears: (() => void) | undefined;

  onMount(() => {
    subYear = selectedYear.subscribe((v) => {
      year = v;
      if (v) loadSteps();
    });
    subYears = yearOptions.subscribe((v) => {
      years = v;
      if (v.length > 0 && !year) {
        const maxYear = v.reduce((a, b) => (Number(a) > Number(b) ? a : b));
        selectedYear.set(maxYear);
      }
    });
    return () => {
      subYear?.();
      subYears?.();
    };
  });

  function sortSteps(steps: string[]): string[] {
    const stepOrder: Record<string, number> = {};
    for (let i = 1; i <= 10; i++) stepOrder[`STEP ${i}`] = i;
    stepOrder["Youth"] = 101;
    stepOrder["Youth International"] = 102;
    stepOrder["Junior"] = 103;
    stepOrder["Junior International"] = 104;
    stepOrder["Senior"] = 105;
    stepOrder["Senior International"] = 106;
    stepOrder["Senior Open"] = 107;
    return [...steps].sort((a, b) => {
      const oa = stepOrder[a];
      const ob = stepOrder[b];
      if (oa !== undefined && ob !== undefined) return oa - ob;
      if (oa !== undefined) return -1;
      if (ob !== undefined) return 1;
      return a.localeCompare(b);
    });
  }

  async function loadSteps() {
    if (!year) return;
    try {
      const data = await getRankingSteps(Number(year), discipline);
      steps = sortSteps(data.steps);
      if (steps.length > 0 && !steps.includes(selectedStep)) {
        selectedStep = steps[0];
      }
    } catch {
      steps = [];
    }
  }

  let loadingRankings = $state(false);

  let exportRows = $derived(rankings.map((r) => ({
    rank: r.rank, name: r.name, gnz_id: r.gnz_id, club: r.club ?? "", region: r.region,
    score1: r.scores[0]?.toFixed(3) ?? "", comp1: r.competitions[0] ?? "",
    score2: r.scores[1]?.toFixed(3) ?? "", comp2: r.competitions[1] ?? "",
    total: r.total.toFixed(3),
    average: (r.total / r.scores.length).toFixed(3),
  })));

  async function loadRankings() {
    if (!year || !selectedStep) return;
    loadingRankings = true;
    error = "";
    try {
      const data = await getRankings(Number(year), selectedStep, discipline, quotaMode, qualifierMode);
      rankings = data.rankings;
    } catch (e) {
      error = "Failed to load rankings.";
      rankings = [];
    } finally {
      loadingRankings = false;
    }
  }

  let quotaMode = $state(false);
  let qualifierMode = $state(true);

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
  <title>National Rankings — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">National Rankings</h1>
  <p class="text-base-content/70 mb-6">Season rankings — top 2 All Around scores per gymnast (excludes Nationals).</p>

  <div class="flex flex-wrap items-center gap-3 mb-6">
    <div class="tabs tabs-box" aria-label="Discipline">
      <button type="button" aria-pressed={discipline === 'WAG'} class="tab tab-sm {discipline === 'WAG' ? 'bg-primary text-primary-content rounded-lg' : ''}" onclick={() => switchDisc('WAG')}>WAG</button>
      <button type="button" aria-pressed={discipline === 'MAG'} class="tab tab-sm {discipline === 'MAG' ? 'bg-secondary text-secondary-content rounded-lg' : ''}" onclick={() => switchDisc('MAG')}>MAG</button>
    </div>

    {#if steps.length > 0}
      <label for="rank-step" class="sr-only">Step</label>
      <select id="rank-step" class="select select-bordered select-sm" bind:value={selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      <label class="label cursor-pointer gap-2">
        <input type="checkbox" class="checkbox checkbox-sm" bind:checked={quotaMode} />
        <span class="label-text text-sm">Enable Region Quotas</span>
      </label>
      <label class="label cursor-pointer gap-2">
        <input type="checkbox" class="checkbox checkbox-sm" bind:checked={qualifierMode} />
        <span class="label-text text-sm">Exclude non-qualifiers</span>
      </label>

      {#if rankings.length > 0}
        <ExportMenu columns={EXPORT_KEYS} rows={exportRows} headerLabels={CSV_HEADERS} title={`National Rankings ${year} ${discipline} ${selectedStep}`} filename={`National Rankings ${year} ${discipline} ${selectedStep}`} />
      {/if}
    {:else if year}
      <span class="text-sm text-base-content/70">No STEP levels available</span>
    {/if}

    {#if !year}
      <span class="text-sm text-base-content/70">Select a year from the nav</span>
    {/if}
  </div>

  {#if loadingRankings}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if error}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-12">
        <p class="text-error" role="alert">{error}</p>
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
            <th scope="col" class="w-12">Rank</th>
            <th scope="col">Name</th>
            <th scope="col">GNZ ID</th>
            <th scope="col">Club</th>
            <th scope="col">Region</th>
            <th scope="col" class="text-right">Score 1</th>
            <th scope="col" class="text-right">Score 2</th>
            <th scope="col" class="text-right">Total</th>
            <th scope="col" class="text-right">Average</th>
          </tr>
        </thead>
        <tbody>
          {#each rankings as r}
            <tr class="hover:bg-base-300">
              <td class="font-bold text-lg">{r.rank}</td>
              <td class="font-medium">
                <a href="/gymnast/{r.gnz_id}" class="hover:link">{r.name}</a>
              </td>
              <td class="text-base-content/70 text-xs">{r.gnz_id}</td>
              <td>{r.club}</td>
              <td>
                {#if r.region}
                  <RegionBadge region={r.region} colors={REGION_PALETTES[r.region] ?? []} />
                {/if}
              </td>
              {#each r.scores as score, i}
                <td class="text-right">
                  <div class="dropdown dropdown-hover dropdown-top">
                    <button
                      type="button"
                      class="cursor-pointer font-mono"
                      aria-label={`Score ${i + 1} for ${r.name}`}
                      aria-describedby={`rank-comp-${r.gnz_id}-${i}`}
                    >
                      {score.toFixed(3)}
                    </button>
                    <div
                      id={`rank-comp-${r.gnz_id}-${i}`}
                      role="tooltip"
                      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2 text-xs whitespace-nowrap"
                    >
                      {r.competitions[i] || "Unknown competition"}
                    </div>
                  </div>
                </td>
              {/each}
              {#if r.scores.length < 2}
                <td class="text-right text-base-content/70">—</td>
              {/if}
              <td class="text-right font-semibold">{r.total.toFixed(3)}</td>
              <td class="text-right text-base-content/70">{(r.total / r.scores.length).toFixed(3)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>