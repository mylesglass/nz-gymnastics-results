<script lang="ts">
  import { onMount } from "svelte";
  import { getApparatusRankings, getRankingSteps, type ApparatusLeaderboard, type ApparatusRankingRow } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_ORDER, REGION_PALETTES } from "$lib/regions";
  import ExportMenu from "$lib/ExportMenu.svelte";

  const EXPORT_HEADERS: Record<string, string> = {
    rank: "Rank", name: "Name", gnz_id: "GNZ ID", club: "Club",
    region: "Region", d: "D-Score", best: "Best", event: "Competition",
  };

  const EXPORT_KEYS = ["rank", "name", "gnz_id", "club", "region", "d", "best", "event"];

  let error = $state("");

  let discipline = $state("WAG");
  let year = $state<string | null>(null);
  let steps = $state<string[]>([]);
  let selectedStep = $state("");
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

  let divisionFilter = $state("");

  let clubFilter = $state("");
  let regionFilter = $state("");
  let clubMenuOpen = $state(false);
  let regionMenuOpen = $state(false);

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
        (!clubFilter || r.club === clubFilter) &&
        (!regionFilter || r.region === regionFilter)
    )
  );

  let exportRows = $derived(filteredRows.map((r) => ({
    rank: r.rank, name: r.name, gnz_id: r.gnz_id, club: r.club ?? "", region: r.region,
    d: r.d?.toFixed(1) ?? "", best: r.best.toFixed(3), event: r.event,
  })));

  let divisionDisabled = $derived(["STEP 9", "STEP 10", "Youth International", "Junior International", "Senior International"].includes(selectedStep));

  function switchDisc(d: string) {
    discipline = d;
    divisionFilter = "";
    if (year) loadSteps();
  }

  let prevStepKey = "";
  $effect(() => {
    const stepKey = `${discipline}|${selectedStep}`;
    if ((prevStepKey && prevStepKey !== stepKey) || divisionDisabled) {
      divisionFilter = "";
    }
    prevStepKey = stepKey;
  });

  // Stale-response guard. Plain `let` (NOT $state) — incrementing it inside
  // loadLeaderboards must not re-trigger the effects (AGENTS.md gotcha).
  let fetchToken = 0;

  async function loadLeaderboards() {
    if (!year || !selectedStep) return;
    const token = ++fetchToken;
    loadingRankings = true;
    error = "";
    try {
      const data = await getApparatusRankings(Number(year), selectedStep, discipline, divisionFilter);
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

  $effect(() => {
    if (year && selectedStep && discipline) {
      clubFilter = "";
      regionFilter = "";
      clubMenuOpen = false;
      regionMenuOpen = false;
      loadLeaderboards();
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

{#snippet filterDropdown(label: string, options: string[], value: string, onPick: (v: string) => void, open: boolean, onToggle: () => void, ariaLabel: string)}
  <span class="dropdown dropdown-bottom dropdown-end {open ? "dropdown-open" : ""}">
    <button
      type="button"
      class="inline-flex items-center cursor-pointer"
      aria-label={ariaLabel}
      aria-haspopup="menu"
      aria-expanded={open}
      onclick={() => onToggle()}
      onkeydown={(e) => {
        if (e.key === "Escape") onToggle();
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        class="size-3.5 {value ? 'text-primary' : 'text-base-content/50'}"
        aria-hidden="true"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
      </svg>
    </button>
    <ul role="menu" class="dropdown-content z-50 bg-base-100 border border-base-300 rounded-box shadow-xl p-1 max-h-72 overflow-y-auto w-52 text-sm">
      <li role="none">
        <button
          type="button"
          role="menuitemradio"
          aria-checked={value === ""}
          class="w-full text-left px-2 py-1.5 rounded hover:bg-base-200 {value === '' ? 'font-semibold' : ''}"
          onclick={() => {
            onPick("");
            onToggle();
          }}
        >
          All {label}s
        </button>
      </li>
      {#each options as opt}
        <li role="none">
          <button
            type="button"
            role="menuitemradio"
            aria-checked={value === opt}
            class="w-full text-left px-2 py-1.5 rounded hover:bg-base-200 {value === opt ? 'font-semibold' : ''}"
            onclick={() => {
              onPick(opt);
              onToggle();
            }}
          >
            {opt}
          </button>
        </li>
      {/each}
    </ul>
  </span>
{/snippet}

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-1">Apparatus Rankings</h1>
  <p class="text-base-content/70 mb-6">
    Best single score per apparatus this season. Each gymnast is ranked by their highest mark on that apparatus.
  </p>

  <div class="flex flex-wrap items-center gap-3 mb-6">
    <div class="tabs tabs-box" aria-label="Discipline">
      <button type="button" aria-pressed={discipline === 'WAG'} class="tab tab-sm {discipline === 'WAG' ? 'bg-primary text-primary-content rounded-lg' : ''}" onclick={() => switchDisc('WAG')}>WAG</button>
      <button type="button" aria-pressed={discipline === 'MAG'} class="tab tab-sm {discipline === 'MAG' ? 'bg-secondary text-secondary-content rounded-lg' : ''}" onclick={() => switchDisc('MAG')}>MAG</button>
    </div>

    {#if steps.length > 0}
      <label for="app-step" class="sr-only">Step</label>
      <select id="app-step" class="select select-bordered select-sm w-40" bind:value={selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      {#if discipline === "WAG"}
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
        <ExportMenu columns={EXPORT_KEYS} rows={exportRows} headerLabels={EXPORT_HEADERS} title={`Apparatus Rankings ${year} ${discipline} ${selectedStep}${divisionLabel} ${selectedApp}`} filename={`Apparatus Rankings ${year} ${discipline} ${selectedStep}${divisionLabel} ${selectedApp}`} />
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
        <button class="btn btn-ghost btn-sm mt-2" onclick={() => { clubFilter = ""; regionFilter = ""; }}>
          Clear filters
        </button>
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
            <th scope="col">
              <span class="inline-flex items-center gap-1">
                Club
                {@render filterDropdown("club", clubOptions, clubFilter, (v) => (clubFilter = v), clubMenuOpen, () => (clubMenuOpen = !clubMenuOpen), "Filter by club")}
              </span>
            </th>
            <th scope="col">
              <span class="inline-flex items-center gap-1">
                Region
                {@render filterDropdown("region", regionOptions, regionFilter, (v) => (regionFilter = v), regionMenuOpen, () => (regionMenuOpen = !regionMenuOpen), "Filter by region")}
              </span>
            </th>
            <th scope="col" class="text-right">D-Score</th>
            <th scope="col" class="text-right">Best</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredRows as r, i (i)}
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
              <td class="text-right text-base-content/70 font-mono">
                {#if r.d != null}
                  {r.d.toFixed(1)}
                {:else}
                  —
                {/if}
              </td>
              <td class="text-right">
                <div class="dropdown dropdown-hover dropdown-top dropdown-end">
                  <button
                    type="button"
                    class="cursor-pointer font-mono font-semibold"
                    aria-label={`Best ${selectedApp} score for ${r.name}`}
                    aria-describedby={`app-best-${i}`}
                  >
                    {r.best.toFixed(3)}
                  </button>
                  <div
                    id={`app-best-${i}`}
                    role="tooltip"
                    class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2 text-xs whitespace-nowrap"
                  >
                    Set at {r.event || "unknown competition"}
                  </div>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
