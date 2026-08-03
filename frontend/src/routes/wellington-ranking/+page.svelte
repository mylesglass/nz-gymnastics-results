<script lang="ts">
  import { onMount } from "svelte";
  import { getWellingtonRankings, getRankingSteps, getIntents, toggleIntent, type WellingtonRankingRow, type ApparatusSpecialistRow, type WellingtonNotRankedRow } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import { currentUser } from "$lib/auth";
  import ExportMenu from "$lib/ExportMenu.svelte";


  const CSV_HEADERS: Record<string, string> = {
    rank: "Rank", name: "Name", gnz_id: "GNZ ID", club: "Club",
    region: "Region",
    score1: "Score 1", comp1: "Competition 1", cat1: "Category 1",
    score2: "Score 2", comp2: "Competition 2", cat2: "Category 2",
    score3: "Score 3", comp3: "Competition 3", cat3: "Category 3",
    total: "Total", average: "Average",
  };

  const EXPORT_KEYS = ["rank", "name", "gnz_id", "club", "region",
    "score1", "comp1", "cat1",
    "score2", "comp2", "cat2",
    "score3", "comp3", "cat3",
    "total", "average"];

  const CONFIG_INFO: Record<string, {
    title: string;
    regional: string[];
    club: string[];
    selection: string;
    qual_note?: string;
  }> = {
    "wag_step_5_6": {
      title: "WAG STEP 5–6",
      regional: ["WAG Wellington Champs", "Central Championships"],
      club: ["Capital Junior Competition", "Rimutaka Juniors"],
      selection: "Best regional mark (1) + next best from remaining named events (2) + best away mark (3). Three marks averaged to rank.",
      qual_note: "GNZ: 50.000 at two separate events (one outside Wellington). Wellington: 53.000 on one occasion.",
    },
    "wag_step_7_10": {
      title: "WAG STEP 7–10",
      regional: ["WAG Wellington Champs", "Central Championships"],
      club: [],
      selection: "Best regional mark (1) + best two endorsed competitions with one away (2, 3). Three marks averaged to rank.",
      qual_note: "GNZ: 43.000 on one occasion (any province). No separate Wellington threshold.",
    },
    "mag_level_4_6": {
      title: "MAG Level 4–6",
      regional: ["MAG Wellington Champs", "Central Championships"],
      club: ["Capital Competition"],
      selection: "Best two Wellington marks (1, 2) + best away mark (3). Three marks averaged to rank.",
      qual_note: "Athletes must achieve 58.000 at two of the three named events and one away.",
    },
    "mag_level_7_plus": {
      title: "MAG Level 7+",
      regional: ["MAG Wellington Champs", "Central Championships"],
      club: [],
      selection: "Best regional mark (1) + best two away marks (2, 3). Three marks averaged to rank.",
      qual_note: "Athletes must achieve 63.000 (Wellington) on one occasion at a regional event (Wellington Champs or Central Champs) and two away events.",
    },
    "wag_youth_international": {
      title: "WAG Youth International",
      regional: [],
      club: [],
      selection: "Single highest All Around mark across the season, ranked by that mark.",
      qual_note: "Gymnastics NZ: 42.500 on one occasion.",
    },
    "wag_junior_international": {
      title: "WAG Junior International",
      regional: [],
      club: [],
      selection: "Single highest All Around mark across the season, ranked by that mark.",
      qual_note: "Gymnastics NZ: 43.000 on one occasion, or an apparatus specialist mark (VT 12.200, UB 10.400, BB 10.500, FX 11.400) on one apparatus.",
    },
    "wag_senior_international": {
      title: "WAG Senior International",
      regional: [],
      club: [],
      selection: "Single highest All Around mark across the season, ranked by that mark.",
      qual_note: "Gymnastics NZ: 45.000 on one occasion, or an apparatus specialist mark (VT 12.500, UB 11.300, BB 11.200, FX 11.400) on one apparatus.",
    },
  };

  const INTERNATIONAL_CONFIGS = new Set([
    "wag_youth_international",
    "wag_junior_international",
    "wag_senior_international",
  ]);

  const STEP7_CONFIGS = new Set(["wag_step_7_10", "mag_level_7_plus"]);

  const CATEGORY_LABELS: Record<string, string> = {
    regional: "Regional Best",
    club: "Club Best",
    away: "Away Best",
  };

  const HEADER_LABELS: Record<string, string[]> = {
    wag_step_5_6: ["Regional Best", "Next Best", "Away Best"],
    wag_step_7_10: ["Regional Best", "Endorsed Best", "Endorsed 2nd"],
    mag_level_4_6: ["Wellington Best", "Wellington 2nd", "Away Best"],
    mag_level_7_plus: ["Regional Best", "Away Best", "Away 2nd"],
    wag_youth_international: ["Best AA"],
    wag_junior_international: ["Best AA"],
    wag_senior_international: ["Best AA"],
  };

  let loading = $state(true);
  let error = $state("");

  let discipline = $state("WAG");
  let year = $state<string | null>(null);
  let steps = $state<string[]>([]);
  let selectedStep = $state("");
  let rankings = $state<WellingtonRankingRow[]>([]);
  let specialists = $state<ApparatusSpecialistRow[]>([]);
  let notRanked = $state<WellingtonNotRankedRow[]>([]);
  let years = $state<string[]>([]);
  let configKey = $state("");
  let gnzScore = $state<number | null>(null);
  let wgtnScore = $state<number | null>(null);

  let subYear: (() => void) | undefined;
  let subYears: (() => void) | undefined;

  onMount(() => {
    const unsubUser = currentUser.subscribe((v) => user = v);
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
      unsubUser();
      subYear?.();
      subYears?.();
    };
  });

  const EXCLUDE_STEPS = ["STEP 1", "STEP 2", "STEP 3", "STEP 4", "Level 1", "Level 2", "Level 3"];

  function sortSteps(stepsList: string[]): string[] {
    const stepOrder: Record<string, number> = {};
    for (let i = 1; i <= 10; i++) stepOrder[`STEP ${i}`] = i;
    for (let i = 1; i <= 10; i++) stepOrder[`Level ${i}`] = 10 + i;
    stepOrder["Youth"] = 101;
    stepOrder["Youth International"] = 102;
    stepOrder["Junior"] = 103;
    stepOrder["Junior International"] = 104;
    stepOrder["Senior"] = 105;
    stepOrder["Senior International"] = 106;
    stepOrder["Senior Open"] = 107;
    stepOrder["U18"] = 108;
    stepOrder["U16"] = 109;
    return [...stepsList].sort((a, b) => {
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
      steps = sortSteps(data.steps.filter((s) => !EXCLUDE_STEPS.includes(s)));
      if (steps.length > 0 && !steps.includes(selectedStep)) {
        selectedStep = steps[0];
      }
    } catch {
      steps = [];
    }
  }

  let loadingRankings = $state(false);

  let specialistNote = $derived.by(() => {
    switch (configKey) {
      case "wag_step_7_10":
        return "STEP 8–10 athletes who submitted intent and reached 11.000 on two apparatus, but did not qualify via the All Around path.";
      case "mag_level_7_plus":
        return "MAG Level 7+ athletes who submitted intent and reached 11.500 on one apparatus, but did not qualify via the All Around path.";
      case "wag_junior_international":
        return "Junior International athletes who submitted intent and reached an apparatus specialist mark (VT 12.200, UB 10.400, BB 10.500, FX 11.400) on one apparatus, but did not qualify via the All Around path.";
      case "wag_senior_international":
        return "Senior International athletes who submitted intent and reached an apparatus specialist mark (VT 12.500, UB 11.300, BB 11.200, FX 11.400) on one apparatus, but did not qualify via the All Around path.";
      default:
        return "";
    }
  });

  let exportRows = $derived(rankings.map((r) => {
    const obj: Record<string, string> = {
      rank: r.rank, name: r.name, gnz_id: r.gnz_id, club: r.club ?? "", region: r.region,
      total: r.total.toFixed(3), average: r.average.toFixed(3),
    };
    for (let i = 0; i < 3; i++) {
      obj[`score${i + 1}`] = r.scores[i]?.toFixed(3) ?? "";
      obj[`comp${i + 1}`] = r.competitions[i] ?? "";
      obj[`cat${i + 1}`] = CATEGORY_LABELS[r.categories[i]] ?? r.categories[i] ?? "";
    }
    return obj;
  }));

  let fetchToken = 0;

  async function loadRankings() {
    if (!year || !selectedStep) return;
    const token = ++fetchToken;
    loadingRankings = true;
    error = "";
    try {
      const [data, intentIds] = await Promise.all([
        getWellingtonRankings(Number(year), selectedStep, discipline),
        getIntents(Number(year)),
      ]);
      if (token !== fetchToken) return;
      rankings = data.rankings;
      specialists = data.apparatus_specialists ?? [];
      notRanked = data.not_ranked ?? [];
      configKey = data.config_key;
      gnzScore = data.qualifying_score;
      wgtnScore = data.wellington_qualifying_score;
      intents = new Set(intentIds);
    } catch (e) {
      error = "Failed to load rankings.";
      rankings = [];
    } finally {
      loadingRankings = false;
    }
  }

  let user = $state<{ username: string; role: string; permissions: string[] } | null>(null);
  let intents = $state<Set<string>>(new Set());

  function switchDisc(d: string) {
    discipline = d;
    if (year) loadSteps();
  }

  $effect(() => {
    if (year && selectedStep && discipline) {
      loadRankings();
    }
  });

  function catBadge(cat: string): string {
    switch (cat) {
      case "regional": return "badge badge-info badge-xs";
      case "club": return "badge badge-secondary badge-xs";
      case "away": return "badge badge-warning badge-xs";
      default: return "badge badge-ghost badge-xs";
    }
  }

  function appBadgeClass(app: string): string {
    switch (app) {
      case "VT": return "badge-primary";
      case "UB": return "badge-secondary";
      case "BB": return "badge-accent";
      case "FX": return "badge-info";
      default: return "badge-neutral";
    }
  }
</script>

<svelte:head>
  <title>Wellington Rankings — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-1 flex items-center gap-3">
    <span class="inline-flex flex-wrap w-6 h-6 shrink-0 overflow-hidden rounded">
      <span class="w-3 h-3" style="background: #000000"></span>
      <span class="w-3 h-3" style="background: #FFC72C"></span>
      <span class="w-3 h-3" style="background: #FFC72C"></span>
      <span class="w-3 h-3" style="background: #000000"></span>
    </span>
    Wellington Rankings
  </h1>
  <p class="text-base-content/70 mb-6">
    Wellington regional ranking for NZ Nationals representatives selection.
  </p>

  {#if configKey && CONFIG_INFO[configKey]}
    {@const info = CONFIG_INFO[configKey]}
    <div class="card bg-base-200 border border-base-300 mb-6">
      <div class="card-body py-4">
        <div class="flex items-start gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="size-6 shrink-0 mt-0.5 fill-info">
            <path fill="currentColor" d="M11 17h2v-6h-2zm1.713-8.287Q13 8.425 13 8t-.288-.712T12 7t-.712.288T11 8t.288.713T12 9t.713-.288M12 22q-2.075 0-3.9-.788t-3.175-2.137T2.788 15.9T2 12t.788-3.9t2.137-3.175T8.1 2.788T12 2t3.9.788t3.175 2.137T21.213 8.1T22 12t-.788 3.9t-2.137 3.175t-3.175 2.138T12 22"/>
          </svg>
          <div class="min-w-0">
            <h3 class="card-title text-sm mb-1">{info.title}</h3>

            <div class="text-xs text-base-content/70 space-y-1.5">
              {#if info.regional.length > 0}
                <div>
                  <span class="font-semibold text-base-content/90">Regional events:</span>
                  {info.regional.join(", ")}
                </div>
              {/if}
              {#if info.club.length > 0}
                <div>
                  <span class="font-semibold text-base-content/90">Club endorsed events:</span>
                  {info.club.join(", ")}
                </div>
              {/if}
              <div>{info.selection}</div>
              {#if gnzScore !== null}
                <div>
                  <span class="font-semibold text-base-content/90">Gymnastics NZ:</span>
                  {gnzScore.toFixed(3)} — {configKey === "wag_step_5_6" ? "Reach score at two separate events (one outside Wellington)." : "Reach score on one occasion (any province)."}
                </div>
              {/if}
              {#if wgtnScore !== null}
                <div>
                  <span class="font-semibold text-base-content/90">Wellington:</span>
                  {wgtnScore.toFixed(3)} — Reach score on one occasion.
                </div>
              {/if}
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
      <label for="wgtn-step" class="sr-only">Step</label>
      <select id="wgtn-step" class="select select-bordered select-sm" bind:value={selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      {#if rankings.length > 0}
        <ExportMenu columns={EXPORT_KEYS} rows={exportRows} headerLabels={CSV_HEADERS} title={`Wellington Rankings ${year} ${discipline} ${selectedStep}`} filename={`Wellington Rankings ${year} ${discipline} ${selectedStep}`} />
      {/if}
    {:else if year}
      <span class="text-sm text-base-content/70">No STEP levels available</span>
    {/if}

    {#if !year}
      <span class="text-sm text-base-content/70">Select a year from the nav</span>
    {/if}
  </div>

  {#if rankings.length === 0 && loadingRankings}
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
    <div class="transition-opacity duration-200" class:opacity-50={loadingRankings && rankings.length > 0}>
      <table class="table table-zebra">
        <thead>
          <tr>
            <th scope="col" class="w-12">Rank</th>
            <th scope="col" class="w-12"></th>
            <th scope="col">Name</th>
            <th scope="col">GNZ ID</th>
            <th scope="col">Club</th>
            <th scope="col" class="w-10">Intent</th>
            {#each HEADER_LABELS[configKey] ?? ["Score 1", "Score 2", "Score 3"] as label}
              <th scope="col" class="text-right">{label}</th>
            {/each}
            {#if !INTERNATIONAL_CONFIGS.has(configKey)}
              <th scope="col" class="text-right">Average</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each rankings as r, i}
            <tr class="hover:bg-base-300" class:border-l-4={configKey === 'wag_step_5_6' && i < 4} class:border-l-primary={configKey === 'wag_step_5_6' && i < 4}>
              <td class="font-bold text-lg">{r.rank}</td>
              <td class="text-center w-12">
                {#if (configKey === 'wag_step_5_6' || STEP7_CONFIGS.has(configKey)) && i < 4}
                  <span class="inline-flex items-center justify-center size-4 rounded-full text-[10px] font-bold" style="background:#FFC72C;color:#000000">1</span>
                {/if}
              </td>
              <td class="font-medium">
                <a href="/gymnast/{r.gnz_id}" class="hover:link">{r.name}</a>
              </td>
              <td class="text-base-content/70 text-xs">{r.gnz_id}</td>
              <td>{r.club}</td>
            <td class="text-center w-10">
              {#if user?.role === "admin"}
                <input
                  type="checkbox"
                  class="checkbox checkbox-xs checkbox-primary"
                  aria-label={`Intent submitted for ${r.name}`}
                  bind:checked={r.intent_submitted}
                  onchange={() => {
                    const row = r;
                    notRanked = notRanked.filter((x) => x !== row);
                    toggleIntent(row.gnz_id, Number(year), row.intent_submitted)
                      .then(loadRankings)
                      .catch(() => loadRankings());
                  }}
                />
              {:else}
                <input type="checkbox" class="checkbox checkbox-xs" checked={r.intent_submitted} disabled aria-label={`Intent submitted for ${r.name}`} />
              {/if}
            </td>
              {#each r.scores as score, i}
                <td class="text-right">
                  <span class="dropdown dropdown-hover dropdown-right">
                    <button
                      type="button"
                      class="cursor-pointer font-mono border-b border-dotted border-base-content/40 hover:border-base-content/70 leading-tight"
                      aria-label={`Score ${i + 1} for ${r.name}`}
                      aria-describedby={`wgtn-comp-${r.gnz_id}-${i}`}
                    >
                      {score.toFixed(3)}
                    </button>
                    <span
                      id={`wgtn-comp-${r.gnz_id}-${i}`}
                      role="tooltip"
                      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2.5 text-xs min-w-44"
                    >
                      <span class="block font-medium text-xs truncate max-w-48 mb-1">{r.competitions[i] || "Unknown competition"}</span>
                      <span>
                        <span class={catBadge(r.categories[i])}>
                          {(HEADER_LABELS[configKey] ?? [])[i] ?? CATEGORY_LABELS[r.categories[i]] ?? r.categories[i]}
                        </span>
                      </span>
                      {#if r.apparatus?.[i]?.length}
                        <span class="divider my-1"></span>
                        {#each r.apparatus[i] as pass}
                          <span class="flex justify-between leading-tight gap-4">
                            <span class="font-semibold">{pass.app}</span>
                            <span>{pass.total?.toFixed(3) ?? "DNS"}</span>
                          </span>
                        {/each}
                        <span class="divider my-0.5"></span>
                        <span class="flex justify-between font-semibold">
                          <span>AA</span>
                          <span>{score.toFixed(3)}</span>
                        </span>
                      {/if}
                    </span>
                  </span>
                </td>
              {/each}
              {#if !INTERNATIONAL_CONFIGS.has(configKey)}
                <td class="text-right font-bold">{r.average.toFixed(3)}</td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if specialists.length > 0}
    <h2 class="text-2xl font-bold mt-8 mb-1">Apparatus Specialists</h2>
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
          <th scope="col" class="text-right">Apparatus</th>
        </tr>
      </thead>
      <tbody>
        {#each specialists as s}
          <tr class="hover:bg-base-300">
            <td class="font-medium">
              <a href="/gymnast/{s.gnz_id}" class="hover:link">{s.name}</a>
            </td>
            <td class="text-base-content/70 text-xs">{s.gnz_id}</td>
            <td>{s.club}</td>
            <td>
              <div class="flex flex-wrap gap-1 justify-end">
                {#each s.apparatus as a}
                  <button
                    type="button"
                    class="tooltip tooltip-top cursor-help"
                    data-tip={a.event || "Unknown competition"}
                    aria-label={`${a.app} ${a.best.toFixed(3)}, best at ${a.event || "unknown competition"}`}
                  >
                    <span class="badge badge-sm {appBadgeClass(a.app)}">{a.app} {a.best.toFixed(3)}</span>
                  </button>
                {/each}
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

  {#if notRanked.length > 0}
    <h2 class="text-2xl font-bold mt-8 mb-1">Not on the Ranking</h2>
    <p class="text-base-content/70 mb-4">
      Wellington athletes in this level who aren't on the ranking above, and why. Mark intent to track them for selection.
    </p>
    <table class="table table-zebra">
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col">GNZ ID</th>
          <th scope="col">Club</th>
          <th scope="col" class="w-10">Intent</th>
          {#each HEADER_LABELS[configKey] ?? ["Score 1", "Score 2", "Score 3"] as label}
            <th scope="col" class="text-right">{label}</th>
          {/each}
          <th scope="col" class="w-8"></th>
        </tr>
      </thead>
      <tbody>
        {#each notRanked as r}
          <tr class="hover:bg-base-300">
            <td class="font-medium">
              <a href="/gymnast/{r.gnz_id}" class="hover:link">{r.name}</a>
            </td>
            <td class="text-base-content/70 text-xs">{r.gnz_id}</td>
            <td>{r.club}</td>
            <td class="text-center w-10">
              {#if user?.role === "admin"}
                <input
                  type="checkbox"
                  class="checkbox checkbox-xs checkbox-primary"
                  aria-label={`Intent submitted for ${r.name}`}
                  bind:checked={r.intent_submitted}
                  onchange={() => {
                    const row = r;
                    notRanked = notRanked.filter((x) => x !== row);
                    toggleIntent(row.gnz_id, Number(year), row.intent_submitted)
                      .then(loadRankings)
                      .catch(() => loadRankings());
                  }}
                />
              {:else}
                <input type="checkbox" class="checkbox checkbox-xs" checked={r.intent_submitted} disabled aria-label={`Intent submitted for ${r.name}`} />
              {/if}
            </td>
            {#each (HEADER_LABELS[configKey] ?? ["Score 1", "Score 2", "Score 3"]) as _, i}
              <td class="text-right">
                {#if r.scores[i] != null}
                  <span class="dropdown dropdown-hover dropdown-right">
                    <button
                      type="button"
                      class="cursor-pointer font-mono border-b border-dotted border-base-content/40 hover:border-base-content/70 leading-tight"
                      aria-label={`Best score ${i + 1} for ${r.name}: ${r.scores[i]!.toFixed(3)}`}
                      aria-describedby={`wgtn-nr-score-${r.gnz_id}-${i}`}
                    >
                      {r.scores[i]!.toFixed(3)}
                    </button>
                    <span
                      id={`wgtn-nr-score-${r.gnz_id}-${i}`}
                      role="tooltip"
                      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2.5 text-xs min-w-44"
                    >
                      <span class="block font-medium text-xs truncate max-w-48 mb-1">{r.competition_names[i] || "Unknown competition"}</span>
                      <span>
                        <span class={catBadge(r.categories[i])}>
                          {(HEADER_LABELS[configKey] ?? [])[i] ?? CATEGORY_LABELS[r.categories[i]] ?? r.categories[i]}
                        </span>
                      </span>
                      {#if r.apparatus?.[i]?.length}
                        <span class="divider my-1"></span>
                        {#each r.apparatus[i] as pass}
                          <span class="flex justify-between leading-tight gap-4">
                            <span class="font-semibold">{pass.app}</span>
                            <span>{pass.total?.toFixed(3) ?? "DNS"}</span>
                          </span>
                        {/each}
                        <span class="divider my-0.5"></span>
                        <span class="flex justify-between font-semibold">
                          <span>AA</span>
                          <span>{r.scores[i]!.toFixed(3)}</span>
                        </span>
                      {/if}
                    </span>
                  </span>
                {:else}
                  <span class="text-base-content/40">—</span>
                {/if}
              </td>
            {/each}
            <td class="text-center w-8">
              <span class="dropdown dropdown-hover dropdown-left">
                <button
                  type="button"
                  class="cursor-help"
                  aria-label={`Why ${r.name} isn't on the ranking`}
                  aria-describedby={`wgtn-nr-why-${r.gnz_id}`}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    class="text-secondary size-5"
                    aria-hidden="true"
                  >
                    <path fill="currentColor" d="m12 23l-3-3H3V2h18v18h-6zm-.1-6q.525 0 .888-.363t.362-.887t-.363-.888t-.887-.362t-.888.363t-.362.887t.363.888t.887.362m-.9-3.85h1.85q0-.425.038-.725t.162-.575t.312-.512t.538-.588q.875-.875 1.238-1.463T15.5 7.95q0-1.325-.9-2.137T12.175 5q-1.375 0-2.337.675T8.5 7.55l1.65.65q.175-.675.7-1.087t1.225-.413q.675 0 1.125.363t.45.962q0 .425-.275.9t-.925 1.05q-.425.35-.688.688t-.437.712t-.25.788t-.075.987"/>
                  </svg>
                </button>
                <span
                  id={`wgtn-nr-why-${r.gnz_id}`}
                  role="tooltip"
                  class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs min-w-64 max-w-80 whitespace-normal text-left"
                >
                  <span class="block space-y-1">
                    {#each r.checks as c}
                      <span class="flex items-start gap-1.5 leading-snug">
                        <span class="shrink-0 flex items-center justify-center size-4 rounded-full {c.met ? 'bg-success text-success-content' : 'bg-error text-error-content'}" aria-hidden="true">
                          {#if c.met}
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-3" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
                          {:else}
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-3" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
                          {/if}
                        </span>
                        <span>
                          <span class="sr-only">{c.met ? "Met:" : "Missing:"}</span>
                          {c.label}
                          {#if c.detail}<span class="text-neutral-content/60">({c.detail})</span>{/if}
                        </span>
                      </span>
                    {/each}
                  </span>
                </span>
              </span>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>
