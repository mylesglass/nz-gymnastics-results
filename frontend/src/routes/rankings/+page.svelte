<script lang="ts">
  import { onMount } from "svelte";
  import { getRankings, getRankingSteps, type RankingRow, type ApparatusSpecialistRow, type ApparatusQualifyingApp } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_ORDER, REGION_PALETTES } from "$lib/regions";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import FilterDropdown from "$lib/FilterDropdown.svelte";

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

  let divisionFilter = $state("");

  let scoreCols = $derived(["STEP 5", "STEP 6"].includes(selectedStep) ? 3 : 2);

  let clubFilters = $state<string[]>([]);
  let regionFilters = $state<string[]>([]);

  let specialists = $state<ApparatusSpecialistRow[]>([]);
  let appQualScore = $state<number | null>(null);
  let appQualCount = $state(2);

  const SPECIALIST_NOTES: Record<string, string> = {
    "STEP 8": "STEP 8–10 athletes who reached 11.000 at two different competitions but didn't qualify for the All Around ranking. Greyed-out badges show an apparatus where the mark has been reached once so far.",
    "STEP 9": "STEP 8–10 athletes who reached 11.000 at two different competitions but didn't qualify for the All Around ranking. Greyed-out badges show an apparatus where the mark has been reached once so far.",
    "STEP 10": "STEP 8–10 athletes who reached 11.000 at two different competitions but didn't qualify for the All Around ranking. Greyed-out badges show an apparatus where the mark has been reached once so far.",
    "Level 7": "MAG Level 7+ athletes who reached 11.500 on one apparatus but didn't qualify for the All Around ranking.",
    "Level 8": "MAG Level 7+ athletes who reached 11.500 on one apparatus but didn't qualify for the All Around ranking.",
    "Level 9": "MAG Level 7+ athletes who reached 11.500 on one apparatus but didn't qualify for the All Around ranking.",
    "U18": "MAG Level 7+ athletes who reached 11.500 on one apparatus but didn't qualify for the All Around ranking.",
    "Senior Open": "MAG Level 7+ athletes who reached 11.500 on one apparatus but didn't qualify for the All Around ranking.",
    "Junior International": "Junior International athletes who reached an apparatus specialist mark (VT 12.200, UB 10.400, BB 10.500, FX 11.400) on one apparatus but didn't qualify for the All Around ranking.",
    "Senior International": "Senior International athletes who reached an apparatus specialist mark (VT 12.500, UB 11.300, BB 11.200, FX 11.400) on one apparatus but didn't qualify for the All Around ranking.",
  };

  let specialistNote = $derived(SPECIALIST_NOTES[selectedStep] ?? "");

  function appBadgeClass(app: string): string {
    switch (app) {
      case "VT": return "badge-primary";
      case "UB": return "badge-secondary";
      case "BB": return "badge-accent";
      case "FX": return "badge-info";
      default: return "badge-neutral";
    }
  }

  const APPARATUS_MARKS: Record<string, Record<string, number>> = {
    "Junior International": { VT: 12.2, UB: 10.4, BB: 10.5, FX: 11.4 },
    "Senior International": { VT: 12.5, UB: 11.3, BB: 11.2, FX: 11.4 },
  };

  function appMarkText(app: string): string {
    if (appQualScore != null) return appQualScore.toFixed(3);
    return (APPARATUS_MARKS[selectedStep]?.[app] ?? null)?.toFixed(3) ?? "the qualifying mark";
  }

  function appTooltip(a: ApparatusQualifyingApp): string {
    const mark = appMarkText(a.app);
    if (a.count >= appQualCount) {
      return a.competitions.length > 0
        ? `${a.app} ${a.best.toFixed(3)} — reached ${mark} at ${a.competitions.join(", ")}`
        : a.event || "Unknown competition";
    }
    return `Reached ${mark} once at ${a.event || "unknown competition"} — needs ${appQualCount} different competitions`;
  }

  let filteredSpecialists = $derived(
    specialists.filter(
      (s) =>
        (clubFilters.length === 0 || clubFilters.includes(s.club)) &&
        (regionFilters.length === 0 || regionFilters.includes(s.region))
    )
  );

  let clubOptions = $derived([...new Set(rankings.map((r) => r.club).filter(Boolean) as string[])].sort());
  let regionOptions = $derived(
    [...new Set(rankings.map((r) => r.region).filter(Boolean) as string[])].sort(
      (a, b) => REGION_ORDER.indexOf(a) - REGION_ORDER.indexOf(b)
    )
  );
  let filteredRankings = $derived(
    rankings.filter(
      (r) =>
        (clubFilters.length === 0 || clubFilters.includes(r.club)) &&
        (regionFilters.length === 0 || regionFilters.includes(r.region))
    )
  );

  let exportKeys = $derived([
    ...BASE_EXPORT_KEYS,
    ...SCORE_KEYS.slice(0, scoreCols * 2),
    "total",
    "average",
  ]);
  let headerLabels = $derived(Object.fromEntries(exportKeys.map((k) => [k, EXPORT_HEADERS[k]])));

  let exportRows = $derived(filteredRankings.map((r) => {
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
      const data = await getRankings(Number(year), selectedStep, discipline, quotaMode, qualifierMode, divisionFilter);
      rankings = data.rankings;
      specialists = data.apparatus_specialists ?? [];
      appQualScore = data.apparatus_qualifying_score ?? null;
      appQualCount = data.apparatus_qualifying_count ?? 2;
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

  const APPARATUS_RULES: Record<string, string> = {
    "STEP 8": "11.000 on one apparatus at two different competitions",
    "STEP 9": "11.000 on one apparatus at two different competitions",
    "STEP 10": "11.000 on one apparatus at two different competitions",
    "Level 7": "11.500 on one apparatus",
    "Level 8": "11.500 on one apparatus",
    "Level 9": "11.500 on one apparatus",
    "U18": "11.500 on one apparatus",
    "Senior Open": "11.500 on one apparatus",
    "Junior International": "VT 12.200, UB 10.400, BB 10.500, FX 11.400 on one apparatus",
    "Senior International": "VT 12.500, UB 11.300, BB 11.200, FX 11.400 on one apparatus",
  };
  let apparatusNote = $derived(APPARATUS_RULES[selectedStep] ?? "");

  let rankingNote = $derived(["STEP 5", "STEP 6"].includes(selectedStep)
    ? "Ranked by the average of each gymnast's top 3 competition scores."
    : "Ranked by the average of each gymnast's top 2 competition scores.");

  let showRankingToggles = $derived(!["STEP 1", "STEP 2", "STEP 3", "STEP 4", "Level 1", "Level 2", "Level 3"].includes(selectedStep));
  let showMarkColumn = $derived(["STEP 1", "STEP 2", "STEP 3", "STEP 4"].includes(selectedStep));
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

  $effect(() => {
    if (year && selectedStep && discipline) {
      clubFilters = [];
      regionFilters = [];
      loadRankings();
    }
  });

  $effect(() => {
    if (divisionFilter) {
      loadRankings();
    }
  });
</script>

<svelte:head>
  <title>National Rankings — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-6">National Rankings</h1>

  {#if showRankingToggles && selectedStep}
    <div class="card bg-base-200 border border-base-300 mb-6">
      <div class="card-body py-4">
        <div class="flex items-start gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="size-6 shrink-0 mt-0.5 fill-info">
            <path fill="currentColor" d="M11 17h2v-6h-2zm1.713-8.287Q13 8.425 13 8t-.288-.712T12 7t-.712.288T11 8t.288.713T12 9t.713-.288M12 22q-2.075 0-3.9-.788t-3.175-2.137T2.788 15.9T2 12t.788-3.9t2.137-3.175T8.1 2.788T12 2t3.9.788t3.175 2.137T21.213 8.1T22 12t-.788 3.9t-2.137 3.175t-3.175 2.138T12 22"/>
          </svg>
          <div class="min-w-0">
            <h3 class="card-title text-sm mb-1">{selectedStep}</h3>
            <div class="text-xs text-base-content/70 space-y-1.5">
              <div>
                <span class="font-semibold text-base-content/90">Ranking:</span>
                {rankingNote}
              </div>
              {#if qualifierHint}
                <div>
                  <span class="font-semibold text-base-content/90">Qualification Criteria:</span>
                  {qualifierHint}
                </div>
              {/if}
              {#if apparatusNote}
                <div>
                  <span class="font-semibold text-base-content/90">Apparatus:</span>
                  {apparatusNote}
                </div>
              {/if}
              <div>
                <span class="font-semibold text-base-content/90">Toggles:</span>
                <ul class="list-disc list-inside ml-3 mt-1 space-y-0.5">
                  <li><span class="font-semibold text-base-content/90">Region Quotas</span> — caps each region at 4 gymnasts initially.</li>
                  <li><span class="font-semibold text-base-content/90">Qualified</span> — filters to gymnasts who reached the qualifying mark and shows the App Specialists table below (AA-qualified gymnasts excluded).</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <div class="flex flex-wrap items-center gap-3 mb-6">
    <div class="tabs tabs-box" aria-label="Discipline">
      <button type="button" aria-pressed={discipline === 'WAG'} class="tab tab-sm {discipline === 'WAG' ? 'bg-primary text-primary-content rounded-lg' : ''}" onclick={() => switchDisc('WAG')}>WAG</button>
      <button type="button" aria-pressed={discipline === 'MAG'} class="tab tab-sm {discipline === 'MAG' ? 'bg-secondary text-secondary-content rounded-lg' : ''}" onclick={() => switchDisc('MAG')}>MAG</button>
    </div>

    {#if steps.length > 0}
      <label for="rank-step" class="sr-only">Step</label>
      <select id="rank-step" class="select select-bordered select-sm w-40" bind:value={selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      {#if discipline === "WAG"}
        <label for="rank-division" class="sr-only">Division</label>
        <select id="rank-division" class="select select-bordered select-sm w-40 {divisionDisabled ? 'select-disabled opacity-60' : ''}" bind:value={divisionFilter} disabled={divisionDisabled} aria-disabled={divisionDisabled}>
          <option value="">All Divisions</option>
          <option value="OVER">Over</option>
          <option value="UNDER">Under</option>
        </select>
      {/if}

  {#if showRankingToggles && selectedStep}
      <div class="flex items-center gap-3 whitespace-nowrap">
        <div class="flex items-center gap-1.5">
          <label class="label cursor-pointer gap-2">
            <input type="checkbox" class="checkbox checkbox-sm" bind:checked={quotaMode} />
            <span class="label-text text-sm">Region Quotas</span>
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
            <span class="label-text text-sm">Qualified</span>
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
      </div>
      {/if}

      {#if filteredRankings.length > 0}
        {@const divisionLabel = divisionFilter === "OVER" ? " Over" : divisionFilter === "UNDER" ? " Under" : ""}
        <ExportMenu columns={exportKeys} rows={exportRows} headerLabels={headerLabels} title={`National Rankings ${year} ${discipline} ${selectedStep}${divisionLabel}`} filename={`National Rankings ${year} ${discipline} ${selectedStep}${divisionLabel}`} />
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
  {:else if filteredRankings.length === 0}
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
            <th scope="col" class="w-12">Rank</th>
            <th scope="col">Name</th>
            <th scope="col">GNZ ID</th>
            <th scope="col">
              <span class="inline-flex items-center gap-1">
                Club
                <FilterDropdown label="club" options={clubOptions} selected={clubFilters} onPick={(v) => (clubFilters = v)} ariaLabel="Filter by club" />
              </span>
            </th>
            <th scope="col">
              <span class="inline-flex items-center gap-1">
                Region
                <FilterDropdown label="region" options={regionOptions} selected={regionFilters} onPick={(v) => (regionFilters = v)} ariaLabel="Filter by region" />
              </span>
            </th>
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
                    Has met Gymnastics NZ qualifying score of 52.000 at two different competitions
                  </span>
                </span>
              </th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each filteredRankings as r}
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
          <span class="font-semibold">Can't find someone?</span> The <span class="font-medium">Qualified</span> filter is on — gymnasts who haven't reached the {selectedStep} qualifying mark are hidden. Turn it off to show everyone.
        </div>
      </div>
    {/if}
  {/if}

  {#if filteredSpecialists.length > 0}
    <h2 class="text-2xl font-bold mt-8 mb-1">Apparatus Qualifiers</h2>
    <p class="text-base-content/70 mb-4">
      {specialistNote}
      Best score per apparatus across the season is shown.
    </p>
    <table class="table table-zebra">
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col">GNZ ID</th>
          <th scope="col">Club</th>
          <th scope="col">Region</th>
          <th scope="col" class="text-right">Apparatus</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredSpecialists as s}
          <tr class="hover:bg-base-300">
            <td class="font-medium">
              <a href="/gymnast/{s.gnz_id}" class="hover:link">{s.name}</a>
            </td>
            <td class="text-base-content/70 text-xs">{s.gnz_id}</td>
            <td>{s.club}</td>
            <td>
              {#if s.region}
                <RegionBadge region={s.region} colors={REGION_PALETTES[s.region] ?? []} />
              {/if}
            </td>
            <td>
              <div class="flex flex-wrap gap-1 justify-end">
                {#each s.apparatus as a}
                  {@const qual = a.count >= appQualCount}
                  <div class="dropdown dropdown-hover dropdown-top dropdown-end">
                    <button
                      type="button"
                      class="cursor-help"
                      aria-label={appTooltip(a)}
                      aria-describedby={`spec-badge-${s.gnz_id}-${a.app}`}
                    >
                      {#if qual}
                        <span class="badge badge-sm {appBadgeClass(a.app)}">{a.app} {a.best.toFixed(3)}</span>
                      {:else}
                        <span class="badge badge-sm badge-outline text-base-content/60">{a.app} {a.best.toFixed(3)}</span>
                      {/if}
                    </button>
                    <div
                      id={`spec-badge-${s.gnz_id}-${a.app}`}
                      role="tooltip"
                      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs w-72 whitespace-normal break-words space-y-1"
                    >
                      <div class="font-semibold text-sm">{a.app} {a.best.toFixed(3)}</div>
                      <div>
                        {#if qual}
                          Reached {appMarkText(a.app)} at {a.count} competition{a.count === 1 ? "" : "s"}
                        {:else}
                          Reached {appMarkText(a.app)} once at {a.event || "unknown competition"}
                        {/if}
                      </div>
                      {#if qual && a.competitions.length > 0}
                        <ul class="list-disc list-inside mt-1 space-y-0.5">
                          {#each a.competitions as c}
                            <li>{c}</li>
                          {/each}
                        </ul>
                      {/if}
                      {#if !qual}
                        <div>Needs {appQualCount} different competitions to qualify</div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>