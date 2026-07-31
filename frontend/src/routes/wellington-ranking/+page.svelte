<script lang="ts">
  import { onMount } from "svelte";
  import { getWellingtonRankings, getRankingSteps, getIntents, toggleIntent, type WellingtonRankingRow, type ApparatusSpecialistRow } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import { currentUser } from "$lib/auth";


  const CSV_HEADERS: Record<string, string> = {
    rank: "Rank", name: "Name", gnz_id: "GNZ ID", club: "Club",
    region: "Region",
    score1: "Score 1", comp1: "Competition 1", cat1: "Category 1",
    score2: "Score 2", comp2: "Competition 2", cat2: "Category 2",
    score3: "Score 3", comp3: "Competition 3", cat3: "Category 3",
    total: "Total", average: "Average",
  };

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
  };

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
  };

  let loading = $state(true);
  let error = $state("");

  let discipline = $state("WAG");
  let year = $state<string | null>(null);
  let steps = $state<string[]>([]);
  let selectedStep = $state("");
  let rankings = $state<WellingtonRankingRow[]>([]);
  let specialists = $state<ApparatusSpecialistRow[]>([]);
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
  const EXCLUDE_WORDS = ["international"];

  async function loadSteps() {
    if (!year) return;
    try {
      const data = await getRankingSteps(Number(year), discipline);
      steps = data.steps
        .filter(
          (s) =>
            !EXCLUDE_STEPS.includes(s) &&
            !EXCLUDE_WORDS.some((w) => s.toLowerCase().includes(w)),
        )
        .sort((a, b) => {
          const na = parseInt(a.match(/\d+/)?.[0] ?? "999", 10);
          const nb = parseInt(b.match(/\d+/)?.[0] ?? "999", 10);
          return na - nb;
        });
      if (steps.length > 0 && !steps.includes(selectedStep)) {
        selectedStep = steps[0];
      }
    } catch {
      steps = [];
    }
  }

  let loadingRankings = $state(false);

  function exportCSV() {
    const rows = rankings.map((r) => {
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
    });
    const keys = ["rank", "name", "gnz_id", "club", "region",
      "score1", "comp1", "cat1",
      "score2", "comp2", "cat2",
      "score3", "comp3", "cat3",
      "total", "average"];
    const header = keys.map((k) => CSV_HEADERS[k]).join(",");
    const csv = header + "\n" + rows.map((r) => keys.map((k) => `"${String(r[k]).replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
    a.download = `wellington-ranking-${year}-${selectedStep}-${discipline}.csv`;
    a.click();
  }

  let fetchToken = 0;

  async function loadRankings() {
    if (!year || !selectedStep) return;
    const token = ++fetchToken;
    loadingRankings = true;
    error = "";
    try {
      const [data, intentIds] = await Promise.all([
        getWellingtonRankings(Number(year), selectedStep, discipline, gnzQualifierMode, wgtnQualifierMode, intentFilterMode),
        getIntents(Number(year)),
      ]);
      if (token !== fetchToken) return;
      rankings = data.rankings;
      specialists = data.apparatus_specialists ?? [];
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

  let gnzQualifierMode = $state(true);
  let wgtnQualifierMode = $state(true);
  let intentFilterMode = $state(true);
  let user = $state<{ role: string } | null>(null);
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
    <div class="card bg-base-200 border border-base-300 border-t-4 border-t-info mb-6">
      <div class="card-body py-4">
        <div class="flex items-start gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="size-6 shrink-0 mt-0.5 fill-info">
            <path fill="currentColor" d="M11 17h2v-6h-2zm1.713-8.287Q13 8.425 13 8t-.288-.712T12 7t-.712.288T11 8t.288.713T12 9t.713-.288M12 22q-2.075 0-3.9-.788t-3.175-2.137T2.788 15.9T2 12t.788-3.9t2.137-3.175T8.1 2.788T12 2t3.9.788t3.175 2.137T21.213 8.1T22 12t-.788 3.9t-2.137 3.175t-3.175 2.138T12 22"/>
          </svg>
          <div class="min-w-0">
            <h3 class="card-title text-sm mb-1">{info.title}</h3>

            <div class="text-xs text-base-content/70 space-y-1.5">
              <div>
                <span class="font-semibold text-base-content/90">Regional events:</span>
                {info.regional.join(", ")}
              </div>
              {#if info.club.length > 0}
                <div>
                  <span class="font-semibold text-base-content/90">Club endorsed events:</span>
                  {info.club.join(", ")}
                </div>
              {/if}
              <div>{info.selection}</div>
              <div>
                <span class="font-semibold text-base-content/90">GNZ:</span>
                {#if gnzScore !== null}{gnzScore.toFixed(3)} — {/if}
                {configKey === "wag_step_5_6" ? "Reach score at two separate events (one outside Wellington)." : "Reach score on one occasion (any province)."}
              </div>
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
    <div role="tablist" class="tabs tabs-box">
      <button role="tab" class="tab tab-sm {discipline === 'WAG' ? 'bg-primary text-primary-content rounded-lg' : ''}" onclick={() => switchDisc('WAG')}>WAG</button>
      <button role="tab" class="tab tab-sm {discipline === 'MAG' ? 'bg-secondary text-secondary-content rounded-lg' : ''}" onclick={() => switchDisc('MAG')}>MAG</button>
    </div>

    {#if steps.length > 0}
      <select class="select select-bordered select-sm" bind:value={selectedStep}>
        {#each steps as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      <label class="label cursor-pointer gap-1">
        <input type="checkbox" class="checkbox checkbox-xs" bind:checked={gnzQualifierMode} />
        <span class="label-text text-xs">GNZ Qualifier</span>
      </label>
      {#if wgtnScore !== null}
        <label class="label cursor-pointer gap-1">
          <input type="checkbox" class="checkbox checkbox-xs" bind:checked={wgtnQualifierMode} />
          <span class="label-text text-xs">Wellington Qualifier</span>
        </label>
      {/if}
      <label class="label cursor-pointer gap-1">
        <input type="checkbox" class="checkbox checkbox-xs" bind:checked={intentFilterMode} />
        <span class="label-text text-xs">Intent</span>
      </label>

      <button onclick={exportCSV} class="btn btn-primary btn-sm ml-auto" disabled={rankings.length === 0}>
        Export CSV
      </button>
    {:else if year}
      <span class="text-sm text-base-content/50">No STEP levels available</span>
    {/if}

    {#if !year}
      <span class="text-sm text-base-content/50">Select a year from the nav</span>
    {/if}
  </div>

  {#if rankings.length === 0 && loadingRankings}
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
    <div class="transition-opacity duration-200" class:opacity-50={loadingRankings && rankings.length > 0}>
      <table class="table table-zebra">
        <thead>
          <tr>
            <th class="w-12">Rank</th>
            <th class="w-12"></th>
            <th>Name</th>
            <th>GNZ ID</th>
            <th>Club</th>
            <th class="w-10"></th>
            {#each HEADER_LABELS[configKey] ?? ["Score 1", "Score 2", "Score 3"] as label}
              <th class="text-right">{label}</th>
            {/each}
            <th class="text-right">Average</th>
            <th class="w-8"></th>
          </tr>
        </thead>
        <tbody>
          {#each rankings as r, i}
            <tr class="hover:bg-base-300" class:border-l-4={configKey === 'wag_step_5_6' && i < 4} class:border-l-primary={configKey === 'wag_step_5_6' && i < 4}>
              <td class="font-bold text-lg">{r.rank}</td>
              <td class="text-center w-12">
                {#if (configKey === 'wag_step_5_6' || STEP7_CONFIGS.has(configKey)) && i < 4}
                  <span class="badge badge-xs" style="background:#FFC72C;color:#000000;border:none">1</span>
                {:else if STEP7_CONFIGS.has(configKey) && i < 8}
                  <span class="badge badge-xs" style="background:#000000;color:#FFC72C;border:none">2</span>
                {/if}
              </td>
              <td class="font-medium">
                <a href="/gymnast/{r.gnz_id}" class="hover:link">{r.name}</a>
              </td>
              <td class="text-base-content/60 text-xs">{r.gnz_id}</td>
              <td>{r.club}</td>
              <td class="text-center w-10">
                {#if user?.role === "admin"}
                  <input
                    type="checkbox"
                    class="checkbox checkbox-xs checkbox-primary"
                    bind:checked={r.intent_submitted}
                    onchange={() => {
                      toggleIntent(r.gnz_id, Number(year), r.intent_submitted).then(loadRankings).catch(() => {
                        r.intent_submitted = !r.intent_submitted;
                      });
                    }}
                  />
                {:else}
                  <input type="checkbox" class="checkbox checkbox-xs" checked={r.intent_submitted} disabled />
                {/if}
              </td>
              {#each r.scores as score, i}
                <td class="text-right">
                  <span class="group/tip relative inline-block">
                    <span
                      class="cursor-pointer font-mono border-b border-dotted border-base-content/30 hover:border-base-content/60 leading-tight"
                    >
                      {score.toFixed(3)}
                    </span>
                    <span
                      class="invisible group-hover/tip:visible opacity-0 group-hover/tip:opacity-100 transition-opacity absolute left-full top-1/2 -translate-y-1/2 ml-1 z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2.5 text-xs pointer-events-none min-w-44"
                    >
                      <div class="font-medium text-xs truncate max-w-48 mb-1">{r.competitions[i] || "Unknown competition"}</div>
                      <div>
                        <span class={catBadge(r.categories[i])}>
                          {(HEADER_LABELS[configKey] ?? [])[i] ?? CATEGORY_LABELS[r.categories[i]] ?? r.categories[i]}
                        </span>
                      </div>
                      {#if r.apparatus?.[i]?.length}
                        <div class="divider my-1"></div>
                        {#each r.apparatus[i] as pass}
                          <div class="flex justify-between leading-tight gap-4">
                            <span class="font-semibold">{pass.app}</span>
                            <span>{pass.total?.toFixed(3) ?? "DNS"}</span>
                          </div>
                        {/each}
                        <div class="divider my-0.5"></div>
                        <div class="flex justify-between font-semibold">
                          <span>AA</span>
                          <span>{score.toFixed(3)}</span>
                        </div>
                      {/if}
                    </span>
                  </span>
                </td>
              {/each}
              <td class="text-right font-bold">{r.average.toFixed(3)}</td>
              <td class="text-center w-8">
                {#if r.warnings?.length}
                  <span class="group/warn relative inline-block cursor-help">
                    <span class="text-warning">⚠</span>
                    <span
                      class="invisible group-hover/warn:visible opacity-0 group-hover/warn:opacity-100 transition-opacity absolute right-full top-1/2 -translate-y-1/2 mr-2 z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-2.5 text-xs pointer-events-none min-w-48 whitespace-normal"
                    >
                      {#each r.warnings as w}
                        <div>{w}</div>
                      {/each}
                    </span>
                  </span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if specialists.length > 0}
    <h2 class="text-2xl font-bold mt-8 mb-1">Apparatus Specialists</h2>
    <p class="text-base-content/70 mb-4">
      STEP 8–10 athletes who submitted intent and reached 11.000 on two apparatus, but did not qualify via the All Around path.
      Best score per apparatus across the season is shown.
    </p>
    <div class="overflow-x-auto">
      <table class="table table-zebra">
        <thead>
          <tr>
            <th>Name</th>
            <th>GNZ ID</th>
            <th>Club</th>
            <th class="text-right">Apparatus</th>
          </tr>
        </thead>
        <tbody>
          {#each specialists as s}
            <tr class="hover:bg-base-300">
              <td class="font-medium">
                <a href="/gymnast/{s.gnz_id}" class="hover:link">{s.name}</a>
              </td>
              <td class="text-base-content/60 text-xs">{s.gnz_id}</td>
              <td>{s.club}</td>
              <td>
                <div class="flex flex-wrap gap-1 justify-end">
                  {#each s.apparatus as a}
                    <span class="badge badge-outline badge-sm font-mono" style="border-color:#FFC72C;color:#000000">{a.app} {a.best.toFixed(3)}</span>
                  {/each}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
