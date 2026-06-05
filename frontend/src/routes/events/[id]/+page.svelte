<script lang="ts">
  import { getWideResults, getExportUrl } from "$lib/api";
  import { page } from "$app/stores";
  import ScoreTooltip from "$lib/ScoreTooltip.svelte";

  let loading = $state(true);
  let eventName = $state("");
  let activeTab = $state("wag");
  let columns = $state<string[]>([]);
  let rows = $state<Record<string, unknown>[]>([]);
  let allData = $state<Record<string, { columns: string[]; rows: Record<string, unknown>[] }>>({});
  let sortCol = $state<string | null>(null);
  let sortAsc = $state(true);

  let metaColumns = $state<string[]>([]);
  let frontMeta = $state<string[]>([]);
  let backMeta = $state<string[]>([]);
  let apparatusPrefixes = $state<string[]>([]);

  let appCols = $state<Record<string, string[]>>({});

  let searchText = $state("");
  let filterStep = $state("");
  let filterClub = $state("");
  let filterDivision = $state("");
  let filterRound = $state("");

  let stepOptions = $state<string[]>([]);
  let clubOptions = $state<string[]>([]);
  let divisionOptions = $state<string[]>([]);
  let roundOptions = $state<string[]>([]);

  const HEADER_LABELS: Record<string, string> = {
    "gnz-id": "ID",
    name: "Name",
    club: "Club",
    step: "STEP",
    division: "Division",
    "round-type": "Round",
    "aa-score": "AA",
    "aa-rank": "Rank",
  };

  let stepLabel = $derived(activeTab === "mag" ? "Level" : "STEP");

  const TAIL_META = new Set(["aa-score", "aa-rank"]);

  function deriveColumnGroups(cols: string[]) {
    const appPrefixes: string[] = [];
    const appMap: Record<string, string[]> = {};
    for (const c of cols) {
      const m = c.match(/^([a-z]{2,3})(?:-\d+)?-total$/);
      if (m) {
        const pfx = m[1];
        if (!appMap[pfx]) {
          appMap[pfx] = [];
          appPrefixes.push(pfx);
        }
      }
    }
    for (const c of cols) {
      const m = c.match(/^([a-z]{2,3})-/);
      if (m && appMap[m[1]]) {
        appMap[m[1]].push(c);
      }
    }
    apparatusPrefixes = appPrefixes;
    appCols = appMap;
    const allMeta = cols.filter((c) => !Object.values(appMap).flat().includes(c));
    metaColumns = allMeta;
    frontMeta = allMeta.filter((c) => !TAIL_META.has(c));
    backMeta = ["aa-score", "aa-rank"].filter((c) => allMeta.includes(c));
  }

  function buildFilterOptions(rs: Record<string, unknown>[]) {
    const steps = new Set<string>();
    const clubs = new Set<string>();
    const divs = new Set<string>();
    const rounds = new Set<string>();
    for (const r of rs) {
      const s = r.step;
      if (s) steps.add(String(s));
      const c = r.club;
      if (c) clubs.add(String(c));
      const d = r.division;
      if (d) divs.add(String(d));
      const rt = r["round-type"];
      if (rt) rounds.add(String(rt));
    }
    stepOptions = [...steps].sort();
    clubOptions = [...clubs].sort();
    divisionOptions = [...divs].sort();
    roundOptions = [...rounds].sort();
  }

  function appDisplayLabel(prefix: string): string {
    const labels: Record<string, string> = {
      vt: "VT", ub: "UB", bb: "BB", fx: "FX",
      ph: "PH", sr: "SR", pb: "PB", hb: "HB",
    };
    return labels[prefix] ?? prefix.toUpperCase();
  }

  $effect(() => {
    const id = $page.params.id;
    if (!id) return;
    loading = true;
    getWideResults(Number(id)).then((r) => {
      eventName = r.event.name;
      allData = {};
      if (r.wag) allData.wag = r.wag;
      if (r.mag) allData.mag = r.mag;
      const keys = Object.keys(allData);
      if (keys.length > 0) {
        activeTab = keys[0];
        applyTab(keys[0]);
      }
    }).catch(() => {
      allData = {};
    }).finally(() => {
      loading = false;
    });
  });

  function applyTab(tab: string) {
    activeTab = tab;
    searchText = "";
    filterStep = "";
    filterClub = "";
    filterDivision = "";
    filterRound = "";
    const d = allData[tab];
    if (d) {
      columns = d.columns;
      rows = d.rows;
      deriveColumnGroups(d.columns);
      buildFilterOptions(d.rows);
    } else {
      columns = [];
      rows = [];
      metaColumns = [];
      frontMeta = [];
      backMeta = [];
      apparatusPrefixes = [];
      appCols = {};
      stepOptions = [];
      clubOptions = [];
      divisionOptions = [];
      roundOptions = [];
    }
    sortCol = null;
  }

  function filteredRows() {
    if (!rows) return [];
    let result = [...rows];
    const q = searchText.toLowerCase().trim();
    if (q) {
      const qn = q.replace(/^gs/i, "");
      result = result.filter((r) => {
        const name = String(r.name ?? "").toLowerCase();
        const gnz = String(r["gnz-id"] ?? "");
        return name.includes(q) || gnz.includes(qn);
      });
    }
    if (filterStep) result = result.filter((r) => String(r.step ?? "") === filterStep);
    if (filterClub) result = result.filter((r) => String(r.club ?? "") === filterClub);
    if (filterDivision) result = result.filter((r) => String(r.division ?? "") === filterDivision);
    if (filterRound) result = result.filter((r) => String(r["round-type"] ?? "") === filterRound);
    if (sortCol) {
      result.sort((a, b) => {
        const va = a[sortCol] ?? "";
        const vb = b[sortCol] ?? "";
        const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" });
        return sortAsc ? cmp : -cmp;
      });
    }
    return result;
  }

  let filteredCount = $derived(filteredRows().length);
  let totalCount = $derived(rows?.length ?? 0);

  function toggleSort(col: string) {
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
  }
</script>

<svelte:head>
  <title>Results — NZ Gymnastics Results</title>
</svelte:head>

<h1 class="text-3xl font-bold mb-2">{eventName || "Results"}</h1>

{#if loading}
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if Object.keys(allData).length === 0}
  <div role="alert" class="alert alert-error mt-4">
    <span>Event not found</span>
  </div>
{:else}
  <div class="flex flex-wrap items-center gap-3 mb-4">
    <div role="tablist" class="tabs tabs-boxed">
      {#each Object.keys(allData) as tab}
        <button
          role="tab"
          class="tab {activeTab === tab ? 'tab-active font-bold' : ''}"
          onclick={() => applyTab(tab)}
        >
          {tab.toUpperCase()}
        </button>
      {/each}
    </div>

    <div class="flex gap-2 ml-auto">
      <a href={getExportUrl(Number($page.params.id), "csv")} class="btn btn-outline btn-sm">
        Download CSV
      </a>
      <a href={getExportUrl(Number($page.params.id), "xlsx")} class="btn btn-outline btn-sm">
        Download XLSX
      </a>
    </div>
  </div>

  <div class="flex flex-wrap items-center gap-2 mb-3">
    <label class="input input-bordered input-sm flex items-center gap-1 w-44">
      <span class="text-base-content/50 text-xs">🔍</span>
      <input
        type="text"
        class="grow text-xs"
        placeholder="Search name or ID"
        bind:value={searchText}
      />
    </label>

    <select class="select select-bordered select-sm" bind:value={filterStep}>
      <option value="">{stepLabel} (all)</option>
      {#each stepOptions as opt}
        <option value={opt}>{opt}</option>
      {/each}
    </select>

    <select class="select select-bordered select-sm max-w-40" bind:value={filterClub}>
      <option value="">Club (all)</option>
      {#each clubOptions as opt}
        <option value={opt}>{opt}</option>
      {/each}
    </select>

    <select class="select select-bordered select-sm" bind:value={filterDivision}>
      <option value="">Division (all)</option>
      {#each divisionOptions as opt}
        <option value={opt}>{opt}</option>
      {/each}
    </select>

    <select class="select select-bordered select-sm" bind:value={filterRound}>
      <option value="">Round (all)</option>
      {#each roundOptions as opt}
        <option value={opt}>{opt}</option>
      {/each}
    </select>

    <span class="text-xs text-base-content/50 ml-1">
      {filteredCount}{filteredCount < totalCount ? ` of ${totalCount}` : ""}
    </span>
  </div>

  <div class="overflow-x-auto">
    <table class="table table-zebra table-pin-rows table-xs">
      <thead>
        <tr>
          {#each frontMeta as col}
            <th onclick={() => toggleSort(col)} class="cursor-pointer select-none hover:text-primary">
              {col === "step" ? stepLabel : HEADER_LABELS[col] ?? col}
              {#if sortCol === col}
                {sortAsc ? " ▲" : " ▼"}
              {/if}
            </th>
          {/each}
          {#each apparatusPrefixes as prefix}
            <th onclick={() => toggleSort(`${prefix}-total`)} class="cursor-pointer select-none hover:text-primary text-center" colspan="1">
              {appDisplayLabel(prefix)}
              {#if sortCol === `${prefix}-total`}
                {sortAsc ? " ▲" : " ▼"}
              {/if}
            </th>
          {/each}
          {#each backMeta as col}
            <th onclick={() => toggleSort(col)} class="cursor-pointer select-none hover:text-primary">
              {col === "step" ? stepLabel : HEADER_LABELS[col] ?? col}
              {#if sortCol === col}
                {sortAsc ? " ▲" : " ▼"}
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each filteredRows() as row}
          <tr>
            {#each frontMeta as col}
              <td class="whitespace-nowrap">{row[col] ?? ""}</td>
            {/each}
            {#each apparatusPrefixes as prefix}
              <td class="text-center">
                <ScoreTooltip {row} {prefix} />
              </td>
            {/each}
            {#each backMeta as col}
              <td class="whitespace-nowrap">{row[col] ?? ""}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}