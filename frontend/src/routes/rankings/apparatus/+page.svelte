<script lang="ts">
  import { onMount } from "svelte";
  import { getApparatusRankings, getRankingSteps, type ApparatusLeaderboard, type ApparatusRankingRow } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import { rankingState } from "$lib/rankingState.svelte.ts";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import RegionCheck from "$lib/RegionCheck.svelte";
  import { REGION_ORDER, REGION_PALETTES } from "$lib/regions";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import FilterDropdown from "$lib/FilterDropdown.svelte";
  import Tooltip from "$lib/Tooltip.svelte";
  import { gymnastPath } from "$lib/seo";

  const EXPORT_HEADERS: Record<string, string> = {
    rank: "Rank", name: "Name", gnz_id: "GNZ ID", club: "Club",
    region: "Region", d: "D-Score", best: "Best", event: "Competition",
  };

  const EXPORT_KEYS = ["rank", "name", "gnz_id", "club", "region", "d", "best", "event"];

  let error = $state("");

  let year = $state<string | null>(null);
  let steps = $state<string[]>([]);
  let leaderboards = $state<ApparatusLeaderboard[]>([]);
  let selectedApp = $state("");
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
      const data = await getRankingSteps(Number(year), rankingState.discipline);
      steps = sortSteps(data.steps);
      if (steps.length > 0 && !steps.includes(rankingState.selectedStep)) {
        rankingState.selectedStep = steps[0];
      }
    } catch {
      steps = [];
    }
  }

  let loadingRankings = $state(false);

  let divisionFilter = $state("");

  let clubFilters = $state<string[]>([]);
  let regionFilters = $state<string[]>([]);

  let availableApps = $derived(leaderboards.map((l) => l.app));

  let currentRows = $derived(
    leaderboards.find((l) => l.app === selectedApp)?.rankings ?? []
  );

  let clubOptions = $derived([...new Set(currentRows.map((r) => r.club).filter(Boolean) as string[])].sort());
  let regionOptions = $derived(
    [...new Set(currentRows.map((r) => r.region).filter(Boolean) as string[])].sort(
      (a, b) => REGION_ORDER.indexOf(a) - REGION_ORDER.indexOf(b)
    )
  );

  let filteredRows = $derived(
    currentRows.filter(
      (r) =>
        (clubFilters.length === 0 || clubFilters.includes(r.club)) &&
        (regionFilters.length === 0 || regionFilters.includes(r.region))
    )
  );

  let exportRows = $derived(filteredRows.map((r) => ({
    rank: r.rank, name: r.name, gnz_id: r.gnz_id, club: r.club ?? "", region: r.region,
    d: r.d?.toFixed(1) ?? "", best: r.best.toFixed(3), event: r.event,
  })));

  let divisionDisabled = $derived(["STEP 9", "STEP 10", "Youth International", "Junior International", "Senior International"].includes(rankingState.selectedStep));

  function switchDisc(d: string) {
    rankingState.discipline = d;
    divisionFilter = "";
    if (year) loadSteps();
  }

  $effect(() => {
    if (divisionDisabled) {
      divisionFilter = "";
    }
  });

  // Stale-response guard. Plain `let` (NOT $state) — incrementing it inside
  // loadLeaderboards must not re-trigger the effects (AGENTS.md gotcha).
  let fetchToken = 0;

  async function loadLeaderboards() {
    if (!year || !rankingState.selectedStep) return;
    const token = ++fetchToken;
    loadingRankings = true;
    error = "";
    try {
      const data = await getApparatusRankings(Number(year), rankingState.selectedStep, rankingState.discipline, divisionFilter);
      if (token !== fetchToken) return;
      leaderboards = data.apparatus ?? [];
      if (!availableApps.includes(selectedApp)) {
        selectedApp = leaderboards[0]?.app ?? "";
      }
    } catch {
      if (token !== fetchToken) return;
      error = "Failed to load rankings.";
      leaderboards = [];
    } finally {
      if (token === fetchToken) loadingRankings = false;
    }
  }

  let prevYear = "";
  let prevDiscipline = "";
  $effect(() => {
    if (year && rankingState.selectedStep && rankingState.discipline) {
      if (year !== prevYear || rankingState.discipline !== prevDiscipline) {
        clubFilters = [];
        regionFilters = [];
      }
      prevYear = year;
      prevDiscipline = rankingState.discipline;
      loadLeaderboards();
    }
  });

  $effect(() => {
    const validClubs = new Set(clubOptions);
    if (clubFilters.some((c) => !validClubs.has(c))) {
      clubFilters = clubFilters.filter((c) => validClubs.has(c));
    }
  });

  $effect(() => {
    const validRegions = new Set(regionOptions);
    if (regionFilters.some((r) => !validRegions.has(r))) {
      regionFilters = regionFilters.filter((r) => validRegions.has(r));
    }
  });

  $effect(() => {
    if (divisionFilter) {
      loadLeaderboards();
    }
  });
</script>

<svelte:head>
  <title>Apparatus Rankings — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-1">Apparatus Rankings</h1>
  <p class="text-base-content/70 mb-6">
    Best single score per apparatus this season. Each gymnast is ranked by their highest mark on that apparatus.
  </p>

  <div class="flex flex-wrap items-center gap-3 mb-6">
    <div class="tabs tabs-box" aria-label="Discipline">
      <button type="button" aria-pressed={rankingState.discipline === 'WAG'} class="tab tab-sm {rankingState.discipline === 'WAG' ? 'bg-primary text-primary-content rounded-lg' : ''}" onclick={() => switchDisc('WAG')}>WAG</button>
      <button type="button" aria-pressed={rankingState.discipline === 'MAG'} class="tab tab-sm {rankingState.discipline === 'MAG' ? 'bg-secondary text-secondary-content rounded-lg' : ''}" onclick={() => switchDisc('MAG')}>MAG</button>
    </div>

    {#if steps.length > 0}
      <label for="app-step" class="sr-only">Step</label>
      <select id="app-step" class="select select-bordered select-sm w-40" bind:value={rankingState.selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      {#if rankingState.discipline === "WAG"}
        <label for="app-division" class="sr-only">Division</label>
        <select id="app-division" class="select select-bordered select-sm w-40 {divisionDisabled ? 'select-disabled opacity-60' : ''}" bind:value={divisionFilter} disabled={divisionDisabled} aria-disabled={divisionDisabled}>
          <option value="">All Divisions</option>
          <option value="OVER">Over</option>
          <option value="UNDER">Under</option>
        </select>
      {/if}

      {#if availableApps.length > 0}
        <div class="tabs tabs-box" aria-label="Apparatus">
          {#each availableApps as app}
            <input
              type="radio"
              name="apparatus_tabs"
              class="tab tab-sm checked:bg-secondary checked:text-secondary-content"
              aria-label={app}
              checked={selectedApp === app}
              onchange={() => (selectedApp = app)}
            />
          {/each}
        </div>
      {/if}

      {#if filteredRows.length > 0}
        {@const divisionLabel = divisionFilter === "OVER" ? " Over" : divisionFilter === "UNDER" ? " Under" : ""}
        <ExportMenu columns={EXPORT_KEYS} rows={exportRows} headerLabels={EXPORT_HEADERS} title={`Apparatus Rankings ${year} ${rankingState.discipline} ${rankingState.selectedStep}${divisionLabel} ${selectedApp}`} filename={`Apparatus Rankings ${year} ${rankingState.discipline} ${rankingState.selectedStep}${divisionLabel} ${selectedApp}`} />
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
  {:else if availableApps.length === 0}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-12">
        <p class="text-base-content/70">No apparatus data for this selection.</p>
      </div>
    </div>
  {:else if currentRows.length === 0}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-12">
        <p class="text-base-content/70">No results on {selectedApp} for this selection.</p>
      </div>
    </div>
  {:else if filteredRows.length === 0}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-12">
        <p class="text-base-content/70">No gymnasts match this filter.</p>
        <button class="btn btn-ghost btn-sm mt-2" onclick={() => { clubFilters = []; regionFilters = []; }}>
          Clear filters
        </button>
      </div>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="table table-zebra">
        <thead>
          <tr>
            <th scope="col" class="sticky left-0 z-10 bg-base-100 w-10 min-w-10 px-1">Rank</th>
            <th scope="col" class="sticky left-10 z-10 bg-base-100">Name</th>
            <th scope="col" class="hidden md:table-cell">GNZ ID</th>
            <th scope="col">
              <span class="inline-flex items-center gap-1">
                Club
                <FilterDropdown label="club" options={clubOptions} selected={clubFilters} onPick={(v) => (clubFilters = v)} ariaLabel="Filter by club" />
              </span>
            </th>
            <th scope="col">
              <span class="inline-flex items-center gap-1">
                <span class="hidden md:inline">Region</span>
                <FilterDropdown label="region" options={regionOptions} selected={regionFilters} onPick={(v) => (regionFilters = v)} ariaLabel="Filter by region" />
              </span>
            </th>
            <th scope="col" class="text-right">D</th>
            <th scope="col" class="text-right">Best</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredRows as r, i (i)}
            <tr class="group hover:bg-base-300">
              <td class="font-bold text-base md:text-lg sticky left-0 z-10 w-10 min-w-10 px-1 group-hover:bg-base-300 {i % 2 === 1 ? 'bg-base-200' : 'bg-base-100'}">{r.rank}</td>
              <td class="font-medium sticky left-10 z-10 border-r border-base-300 group-hover:bg-base-300 {i % 2 === 1 ? 'bg-base-200' : 'bg-base-100'}">
                <a href={gymnastPath(r.slug, r.gnz_id, r.name)} class="hover:link">{r.name}</a>
              </td>
              <td class="text-base-content/70 text-xs hidden md:table-cell">{r.gnz_id}</td>
              <td>{r.club}</td>
              <td>
                {#if r.region}
                  <span class="hidden md:inline-flex">
                    <RegionBadge region={r.region} colors={REGION_PALETTES[r.region] ?? []} />
                  </span>
                  <span class="md:hidden">
                    <RegionCheck region={r.region} colors={REGION_PALETTES[r.region] ?? []} />
                  </span>
                {/if}
              </td>
              <td class="text-right text-base-content/70 font-mono">
                {#if r.d != null}
                  {r.d.toFixed(1)}
                {:else}
                  —
                {/if}
              </td>
              <td class="text-right">
                <Tooltip
                  tipId={`app-best-${i}`}
                  label={`Best ${selectedApp} score for ${r.name}`}
                  placement="top"
                  triggerClass="cursor-pointer font-mono font-bold"
                  panelClass="p-2 whitespace-nowrap"
                >
                  {#snippet trigger()}
                    {r.best.toFixed(3)}
                  {/snippet}
                  {#snippet content()}
                    Set at {r.event || "unknown competition"}
                  {/snippet}
                </Tooltip>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
