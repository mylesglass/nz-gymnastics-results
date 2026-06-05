<script lang="ts">
  import { onMount } from "svelte";
  import { getAllWideResults } from "$lib/api";
  import ScoreTooltip from "$lib/ScoreTooltip.svelte";
  import MultiSelect from "$lib/MultiSelect.svelte";

  let loading = $state(true);
  let isScrolled = $state(false);
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
  let filterEvent = $state<string[]>([]);
  let filterStep = $state<string[]>([]);
  let filterClub = $state<string[]>([]);
  let filterDivision = $state<string[]>([]);
  let filterRound = $state<string[]>([]);

  let eventOptions = $state<string[]>([]);
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
    event_name: "Event",
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
    const events = new Set<string>();
    const steps = new Set<string>();
    const clubs = new Set<string>();
    const divs = new Set<string>();
    const rounds = new Set<string>();
    for (const r of rs) {
      const ev = r.event_name;
      if (ev) events.add(String(ev));
      const s = r.step;
      if (s) steps.add(String(s));
      const c = r.club;
      if (c) clubs.add(String(c));
      const d = r.division;
      if (d) divs.add(String(d));
      const rt = r["round-type"];
      if (rt) rounds.add(String(rt));
    }
    eventOptions = [...events].sort();
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

  onMount(() => {
    const onScroll = () => { isScrolled = window.scrollY > 60; };
    window.addEventListener("scroll", onScroll, { passive: true });

    getAllWideResults().then((r) => {
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

    return () => window.removeEventListener("scroll", onScroll);
  });

  function applyTab(tab: string) {
    activeTab = tab;
    searchText = "";
    filterEvent = [];
    filterStep = [];
    filterClub = [];
    filterDivision = [];
    filterRound = [];
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
      eventOptions = [];
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
    if (filterEvent.length) {
      const sel = new Set(filterEvent);
      result = result.filter((r) => sel.has(String(r.event_name ?? "")));
    }
    if (filterStep.length) {
      const sel = new Set(filterStep);
      result = result.filter((r) => sel.has(String(r.step ?? "")));
    }
    if (filterClub.length) {
      const sel = new Set(filterClub);
      result = result.filter((r) => sel.has(String(r.club ?? "")));
    }
    if (filterDivision.length) {
      const sel = new Set(filterDivision);
      result = result.filter((r) => sel.has(String(r.division ?? "")));
    }
    if (filterRound.length) {
      const sel = new Set(filterRound);
      result = result.filter((r) => sel.has(String(r["round-type"] ?? "")));
    }
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

  function exportCSV() {
    const colKeys = columns;
    const csvRows = filteredRows();
    const header = colKeys.map((c) => HEADER_LABELS[c] ?? c);
    const lines = [
      header.join(","),
      ...csvRows.map((r) =>
        colKeys
          .map((c) => {
            const v = r[c];
            const s = v == null ? "" : String(v);
            return s.includes(",") || s.includes('"') || s.includes("\n")
              ? `"${s.replace(/"/g, '""')}"`
              : s;
          })
          .join(",")
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "all-results.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<svelte:head>
  <title>All Results — NZ Gymnastics Results</title>
</svelte:head>

{#if loading}
  <h1 class="text-3xl font-bold mb-2">All Results</h1>
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if Object.keys(allData).length === 0}
  <h1 class="text-3xl font-bold mb-2">All Results</h1>
  <div class="card bg-base-200 mt-4">
    <div class="card-body items-center text-center py-12">
      <p class="text-base-content/70">No results yet.</p>
      <a href="/" class="btn btn-primary btn-sm mt-2">Upload an event</a>
    </div>
  </div>
{:else}
  <div class="sticky top-16 z-40 bg-base-100 transition-shadow duration-200 {isScrolled ? 'shadow-sm' : ''}">
    <h1 class="font-bold transition-all duration-200 {isScrolled ? 'text-lg mb-0 py-1' : 'text-3xl mb-2'}">All Results</h1>
    <div class="flex flex-wrap items-center {isScrolled ? 'gap-1 mb-2' : 'gap-3 mb-4'}">
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
      <button onclick={exportCSV} class="btn btn-outline btn-sm">
        Download CSV
      </button>
    </div>
  </div>

  <div class="flex flex-wrap items-center {isScrolled ? 'gap-1 mb-0' : 'gap-2 mb-3'}">
    <label class="input input-bordered input-sm flex items-center gap-1 w-44">
      <span class="text-base-content/50 text-xs">🔍</span>
      <input
        type="text"
        class="grow text-xs"
        placeholder="Search name or ID"
        bind:value={searchText}
      />
    </label>

    {#if eventOptions.length > 1}
      <MultiSelect options={eventOptions} bind:selected={filterEvent} label="Event" placeholder="Event (all)" />
    {/if}

    <MultiSelect options={stepOptions} bind:selected={filterStep} label={stepLabel} placeholder="{stepLabel} (all)" />

    <MultiSelect options={clubOptions} bind:selected={filterClub} label="Club" placeholder="Club (all)" />

    <MultiSelect options={divisionOptions} bind:selected={filterDivision} label="Division" placeholder="Division (all)" />

    <MultiSelect options={roundOptions} bind:selected={filterRound} label="Round" placeholder="Round (all)" />

    <span class="text-xs text-base-content/50 ml-1">
      {filteredCount}{filteredCount < totalCount ? ` of ${totalCount}` : ""}
    </span>
  </div>
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