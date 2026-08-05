<script lang="ts">
  import { onMount } from "svelte";
  import { getRankings, getRankingSteps, type RankingRow } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_PALETTES } from "$lib/regions";
  import ExportMenu from "$lib/ExportMenu.svelte";

  const SCORE_KEYS = ["score1", "comp1", "score2", "comp2", "score3", "comp3"];

  const EXPORT_HEADERS: Record<string, string> = {
    rank: "Rank", name: "Name", gnz_id: "GNZ ID", club: "Club",
    region: "Region",
    score1: "Score 1", comp1: "Competition 1",
    score2: "Score 2", comp2: "Competition 2",
    score3: "Score 3", comp3: "Competition 3",
    total: "Total", average: "Average",
  };

  const BASE_EXPORT_KEYS = ["rank", "name", "gnz_id", "club", "region"];

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

  let scoreCols = $derived(["STEP 5", "STEP 6"].includes(selectedStep) ? 3 : 2);
  let exportKeys = $derived([
    ...BASE_EXPORT_KEYS,
    ...SCORE_KEYS.slice(0, scoreCols * 2),
    "total",
    "average",
  ]);
  let headerLabels = $derived(Object.fromEntries(exportKeys.map((k) => [k, EXPORT_HEADERS[k]])));

  let exportRows = $derived(rankings.map((r) => {
    const row: Record<string, string> = {
      rank: r.rank, name: r.name, gnz_id: r.gnz_id, club: r.club ?? "", region: r.region,
      total: r.total.toFixed(3),
      average: (r.total / r.scores.length).toFixed(3),
    };
    for (let i = 0; i < scoreCols; i++) {
      row[`score${i + 1}`] = r.scores[i]?.toFixed(3) ?? "";
      row[`comp${i + 1}`] = r.competitions[i] ?? "";
    }
    return row;
  }));

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

  const QUALIFIER_RULES: Record<string, string> = {
    "STEP 5": "2 marks at 50.000, one outside home province",
    "STEP 6": "2 marks at 50.000, one outside home province",
    "STEP 7": "2 marks at 43.000 (different competitions)",
    "STEP 8": "2 marks at 43.000 (different competitions)",
    "STEP 9": "2 marks at 43.000 (different competitions)",
    "STEP 10": "2 marks at 43.000 (different competitions)",
    "Youth International": "1 mark at 42.500",
    "Junior International": "1 mark at 43.000",
    "Senior International": "1 mark at 45.000",
    "Level 7": "1 mark at 63.000",
    "Level 8": "1 mark at 63.000",
    "Level 9": "1 mark at 63.000",
    "U18": "1 mark at 63.000",
    "Senior Open": "1 mark at 63.000",
  };

  let qualifierHint = $derived(QUALIFIER_RULES[selectedStep] ?? "");

  let showRankingToggles = $derived(!["STEP 1", "STEP 2", "STEP 3", "STEP 4", "Level 1", "Level 2", "Level 3"].includes(selectedStep));
  let showMarkColumn = $derived(["STEP 1", "STEP 2", "STEP 3", "STEP 4"].includes(selectedStep));

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
  <p class="text-base-content/70 mb-6">Season rankings — top {scoreCols} All Around scores per gymnast (excludes Nationals).</p>

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

      {#if showRankingToggles}
      <div class="flex items-center gap-1.5">
        <label class="label cursor-pointer gap-2">
          <input type="checkbox" class="checkbox checkbox-sm" bind:checked={quotaMode} />
          <span class="label-text text-sm">Enable Region Quotas</span>
        </label>
        <span class="dropdown dropdown-hover dropdown-top">
          <button
            type="button"
            class="cursor-help"
            aria-label="About region quotas"
            aria-describedby="quota-tooltip"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              class="size-4 text-base-content/60"
              aria-hidden="true"
            >
              <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022ZM12 9a.75.75 0 1 0 0-1.5A.75.75 0 0 0 12 9Z" clip-rule="evenodd" />
            </svg>
          </button>
          <span
            id="quota-tooltip"
            role="tooltip"
            class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2 text-xs whitespace-nowrap"
          >
            Caps each region at 4 gymnasts in the initial ranking, then fills the remaining places with the next best gymnasts from any region.
          </span>
        </span>
      </div>
      <div class="flex items-center gap-1.5">
        <label class="label cursor-pointer gap-2">
          <input type="checkbox" class="checkbox checkbox-sm" bind:checked={qualifierMode} />
          <span class="label-text text-sm">Exclude non-qualifiers</span>
        </label>
        {#if qualifierHint}
          <span class="dropdown dropdown-hover dropdown-top">
            <button
              type="button"
              class="cursor-help"
              aria-label="About the qualifying marks"
              aria-describedby="qualifier-tooltip"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                class="size-4 text-base-content/60"
                aria-hidden="true"
              >
                <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022ZM12 9a.75.75 0 1 0 0-1.5A.75.75 0 0 0 12 9Z" clip-rule="evenodd" />
              </svg>
            </button>
            <span
              id="qualifier-tooltip"
              role="tooltip"
              class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2 text-xs whitespace-nowrap"
            >
              Qualifies: {qualifierHint}
            </span>
          </span>
        {/if}
      </div>
      {/if}

      {#if rankings.length > 0}
        <ExportMenu columns={exportKeys} rows={exportRows} headerLabels={headerLabels} title={`National Rankings ${year} ${discipline} ${selectedStep}`} filename={`National Rankings ${year} ${discipline} ${selectedStep}`} />
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
            {#each Array(scoreCols) as _, i}
              <th scope="col" class="text-right">Score {i + 1}</th>
            {/each}
            <th scope="col" class="text-right">Average</th>
            {#if showMarkColumn}
              <th scope="col" class="text-center">
                <span class="dropdown dropdown-hover dropdown-end">
                  <button
                    type="button"
                    class="cursor-help inline-flex items-center gap-0.5"
                    aria-label="About the Q column (Gymnastics NZ qualifying mark)"
                    aria-describedby="q-tooltip"
                  >
                    Q
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      class="size-3.5 text-base-content/60"
                      aria-hidden="true"
                    >
                      <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022ZM12 9a.75.75 0 1 0 0-1.5A.75.75 0 0 0 12 9Z" clip-rule="evenodd" />
                    </svg>
                  </button>
                  <span
                    id="q-tooltip"
                    role="tooltip"
                    class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2 text-xs whitespace-nowrap"
                  >
                    Has met Gymnastics NZ qualifying score of 52.000 twice
                  </span>
                </span>
              </th>
            {/if}
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
              {#each Array(scoreCols) as _, i}
                {@const score = r.scores[i]}
                {#if score != null}
                  <td class="text-right">
                    <div class="dropdown dropdown-hover dropdown-top dropdown-end">
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
                {:else}
                  <td class="text-right text-base-content/70">—</td>
                {/if}
              {/each}
              <td class="text-right font-semibold">{(r.total / r.scores.length).toFixed(3)}</td>
              {#if showMarkColumn}
                <td class="text-center">
                  {#if r.reached_mark}
                    <span class="text-success font-bold" role="img" aria-label="Reached 52.000 twice">&#10003;</span>
                  {:else}
                    <span class="text-base-content/40" role="img" aria-label="Has not reached 52.000 twice">&mdash;</span>
                  {/if}
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if qualifierMode && showRankingToggles}
      <div class="alert alert-info mt-4" role="status">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          class="size-5 shrink-0"
          aria-hidden="true"
        >
          <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022ZM12 9a.75.75 0 1 0 0-1.5A.75.75 0 0 0 12 9Z" clip-rule="evenodd" />
        </svg>
        <div class="text-sm">
          <span class="font-semibold">Can't find someone?</span> The <span class="font-medium">Exclude non-qualifiers</span> filter is on — gymnasts who haven't reached the {selectedStep} qualifying mark are hidden. Turn the filter off to show everyone.
        </div>
      </div>
    {/if}
  {/if}
</div>