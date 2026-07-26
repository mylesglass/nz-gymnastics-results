<script lang="ts">
  import { onMount } from "svelte";
  import type { Snippet } from "svelte";
  import { debounce } from "$lib/utils/debounce";
  import ScoreTooltip from "./ScoreTooltip.svelte";
  import AATooltip from "./AATooltip.svelte";
  import { REGION_PALETTES } from "./regions";

  interface TabData {
    columns: string[];
    rows: Record<string, unknown>[];
  }

  interface LoadDataResult {
    title: string;
    tabs: Record<string, TabData>;
  }

  interface DownloadArgs {
    columns: string[];
    rows: Record<string, unknown>[];
    headerLabels: Record<string, string>;
  }

  let {
    loadData,
    loadKey = "",
    showEventFilter = false,
    extraHeadLabels = {} as Record<string, string>,
    download,
    empty,
    extraControls,
  }: {
    loadData: () => Promise<LoadDataResult>;
    loadKey?: string;
    showEventFilter?: boolean;
    extraHeadLabels?: Record<string, string>;
    download?: Snippet<[DownloadArgs]>;
    empty?: Snippet;
    extraControls?: Snippet;
  } = $props();

  let loading = $state(true);
  let isScrolled = $state(false);
  let showDuplicateHeaders = $state(false);
  let activeTab = $state("wag");
  let discTabsName = $state(`disc-tabs-${Math.random().toString(36).slice(2, 7)}`);
  let columns = $state<string[]>([]);
  let rows = $state<Record<string, unknown>[]>([]);
  let allData = $state<Record<string, TabData>>({});
  let title = $state("");
  let sortCol = $state<string | null>(null);
  let sortAsc = $state(true);
  let errorMessage = $state<string | null>(null);
  let errorRaw = $state<string | null>(null);
  let showErrorDetail = $state(false);

  let metaColumns = $state<string[]>([]);
  let frontMeta = $state<string[]>([]);
  let backMeta = $state<string[]>([]);
  let apparatusPrefixes = $state<string[]>([]);
  let appCols = $state<Record<string, string[]>>({});

  let rawSearchInput = $state("");
  let searchText = $state("");

  $effect(() => {
    const val = rawSearchInput;
    const timer = setTimeout(() => searchText = val, 200);
    return () => clearTimeout(timer);
  });
  let filterEvent = $state<string[]>([]);
  let filterStep = $state<string[]>([]);
  let filterClub = $state<string[]>([]);
  let filterRegion = $state<string[]>([]);
  let filterDivision = $state<string[]>([]);
  let filterRound = $state<string[]>([]);

  let eventOptions = $state<string[]>([]);
  let stepOptions = $state<string[]>([]);
  let clubOptions = $state<string[]>([]);
  let regionOptions = $state<string[]>([]);
  let divisionOptions = $state<string[]>([]);
  let roundOptions = $state<string[]>([]);

  let theadEl: HTMLElement | undefined = $state();
  let mainScrollEl: HTMLElement | undefined = $state();
  let dupScrollEl: HTMLElement | undefined = $state();
  let columnWidths = $state<number[]>([]);

  let openDropdown = $state<string | null>(null);
  let openDropdownX = $state(0);
  let openDropdownY = $state(0);

  const BASE_LABELS: Record<string, string> = {
    "gnz-id": "ID",
    name: "Name",
    club: "Club",
    region: "Region",
    step: "STEP",
    division: "Division",
    "round-type": "Round",
    "aa-score": "AA",
    "aa-rank": "Rank",
  };
  let HEADER_LABELS = $derived({ ...BASE_LABELS, ...extraHeadLabels });

  let stepLabel = $derived(activeTab === "mag" ? "Level" : "STEP");

  const TAIL_META = new Set(["aa-score", "aa-rank"]);

  const COL_MIN_CLASS: Record<string, string> = {
    "gnz-id": "min-w-2",
    step: "min-w-18",
    name: "min-w-36",
    club: "min-w-36",
    region: "min-w-24",
    division: "min-w-18",
    "round-type": "min-w-18",
    event_name: "min-w-36 max-w-56 truncate",
  };

  const FILTERABLE_COLS = new Set([
    "step",
    "club",
    "region",
    "division",
    "round-type",
    "event_name",
  ]);

  function filterStateFor(col: string): {
    selected: string[];
    options: string[];
    label: string;
  } {
    if (col === "event_name" && !showEventFilter) {
      return { selected: [], options: [], label: "Event" };
    }
    const map: Record<
      string,
      { selected: string[]; options: string[]; label: string }
    > = {
      step: { selected: filterStep, options: stepOptions, label: stepLabel },
      club: { selected: filterClub, options: clubOptions, label: "Club" },
      region: { selected: filterRegion, options: regionOptions, label: "Region" },
      division: {
        selected: filterDivision,
        options: divisionOptions,
        label: "Division",
      },
      "round-type": {
        selected: filterRound,
        options: roundOptions,
        label: "Round",
      },
      event_name: {
        selected: filterEvent,
        options: eventOptions,
        label: "Event",
      },
    };
    return map[col] ?? { selected: [], options: [], label: col };
  }

  function toggleFilterOption(col: string, value: string) {
    const state = filterStateFor(col);
    const arr = state.selected;
    const idx = arr.indexOf(value);
    if (idx >= 0) {
      arr.splice(idx, 1);
    } else {
      arr.push(value);
    }
  }

  function clearFilter(col: string) {
    filterStateFor(col).selected.length = 0;
  }

  function toggleDropdown(col: string, event: MouseEvent) {
    if (openDropdown === col) {
      openDropdown = null;
      return;
    }
    const btn = event.currentTarget as HTMLElement;
    const rect = btn.getBoundingClientRect();
    openDropdownX = rect.left;
    openDropdownY = rect.bottom + 2;
    openDropdown = col;
  }

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
    const allMeta = cols.filter(
      (c) => !Object.values(appMap).flat().includes(c),
    );
    metaColumns = allMeta;
    frontMeta = allMeta.filter((c) => !TAIL_META.has(c));
    backMeta = ["aa-score", "aa-rank"].filter((c) => allMeta.includes(c));
  }

  function buildFilterOptions(rs: Record<string, unknown>[]) {
    const events = new Set<string>();
    const steps = new Set<string>();
    const clubs = new Set<string>();
    const regions = new Set<string>();
    const divs = new Set<string>();
    const rounds = new Set<string>();
    for (const r of rs) {
      if (showEventFilter) {
        const ev = r.event_name;
        if (ev) events.add(String(ev));
      }
      const s = r.step;
      if (s) steps.add(String(s));
      const c = r.club;
      if (c) clubs.add(String(c));
      const reg = r.region;
      if (reg) regions.add(String(reg));
      const d = r.division;
      if (d) divs.add(String(d));
      const rt = r["round-type"];
      if (rt) rounds.add(String(rt));
    }
    eventOptions = [...events].sort();
    stepOptions = [...steps].sort();
    clubOptions = [...clubs].sort();
    regionOptions = [...regions].sort();
    divisionOptions = [...divs].sort();
    roundOptions = [...rounds].sort();
  }

  function appDisplayLabel(prefix: string): string {
    const labels: Record<string, string> = {
      vt: "VT",
      ub: "UB",
      bb: "BB",
      fx: "FX",
      ph: "PH",
      sr: "SR",
      pb: "PB",
      hb: "HB",
    };
    return labels[prefix] ?? prefix.toUpperCase();
  }

  function thStyle(i: number, _col?: string): string {
    const w = columnWidths[i];
    return w ? `width:${w}px;min-width:${w}px` : "";
  }

  onMount(() => {
    const onScroll = () => {
      isScrolled = window.scrollY > 60;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  });

  let loaded = $state(false);

  $effect(() => {
    void loadKey;
    loaded = false;
    errorMessage = null;
    errorRaw = null;
    loading = true;
    loadData()
      .then((r) => {
        title = r.title;
        allData = r.tabs;
        const keys = Object.keys(r.tabs);
        if (keys.length > 0) {
          activeTab = keys[0];
          applyTab(keys[0]);
        }
      })
      .catch((err) => {
        allData = {};
        const text = String(err);
        errorRaw = text;
        try {
          const parsed = JSON.parse(err instanceof Error ? err.message : text);
          if (parsed.detail) {
            errorMessage = parsed.detail;
          } else {
            errorMessage = text;
          }
        } catch {
          errorMessage = text;
        }
      })
      .finally(() => {
        loading = false;
        loaded = true;
      });
  });

  $effect(() => {
    const el = theadEl;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        showDuplicateHeaders = !entry.isIntersecting;
      },
      { threshold: 0, rootMargin: "-64px 0px 0px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  });

  $effect(() => {
    const main = mainScrollEl;
    const dup = dupScrollEl;
    if (!main || !dup) return;
    function onScroll() {
      dup.scrollLeft = main.scrollLeft;
    }
    main.addEventListener("scroll", onScroll, { passive: true });
    return () => main.removeEventListener("scroll", onScroll);
  });

  $effect(() => {
    columns;
    const el = theadEl;
    if (!el) return;
    const measure = () => {
      const ths = el.querySelectorAll("th");
      columnWidths = Array.from(ths).map(
        (th) => (th as HTMLElement).offsetWidth,
      );
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  });

  function applyTab(tab: string) {
    activeTab = tab;
    searchText = "";
    filterEvent = [];
    filterStep = [];
    filterClub = [];
    filterRegion = [];
    filterDivision = [];
    filterRound = [];
    const d = allData[tab];
    if (d) {
      columns = d.columns;
      rows = d.rows;
      deriveColumnGroups(d.columns);
      if (tab === "mag") {
        frontMeta = frontMeta.filter((c) => c !== "division");
      }
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
      regionOptions = [];
      divisionOptions = [];
      roundOptions = [];
    }
    sortCol = null;
  }

  let pageSize = $state(50);
  let currentPage = $state(1);

  let filteredRows = $derived.by(() => {
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
    if (filterRegion.length) {
      const sel = new Set(filterRegion);
      result = result.filter((r) => sel.has(String(r.region ?? "")));
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
        const cmp = String(va).localeCompare(String(vb), undefined, {
          numeric: true,
          sensitivity: "base",
        });
        return sortAsc ? cmp : -cmp;
      });
    }
    return result;
  });

  let totalPages = $derived(Math.max(1, Math.ceil(filteredRows.length / pageSize)));
  let visibleRows = $derived(filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize));

  let filteredCount = $derived(filteredRows.length);
  let totalCount = $derived(rows?.length ?? 0);

  $effect(() => {
    searchText + filterEvent.join(",") + filterStep.join(",") + filterClub.join(",") + filterRegion.join(",") + filterDivision.join(",") + filterRound.join(",");
    currentPage = 1;
  });

  function toggleSort(col: string) {
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
  }
</script>

{#if loading}
  <h1 class="text-3xl font-bold mb-2">{title || "Results"}</h1>
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if Object.keys(allData).length === 0}
  <h1 class="text-3xl font-bold mb-2">{title || "Results"}</h1>
  {#if errorMessage}
    <div class="alert alert-error mt-4">
      <div class="flex flex-col gap-2 w-full">
        <span>{errorMessage}</span>
        {#if errorRaw}
          <button
            class="btn btn-ghost btn-xs self-start"
            onclick={() => (showErrorDetail = !showErrorDetail)}
          >
            {showErrorDetail ? "Hide details" : "Show details"}
          </button>
          {#if showErrorDetail}
            <pre class="text-xs opacity-60 whitespace-pre-wrap max-h-48 overflow-y-auto bg-base-300 p-2 rounded">{errorRaw}</pre>
          {/if}
        {/if}
      </div>
    </div>
  {:else if empty}
    {@render empty()}
  {:else}
    <div role="alert" class="alert alert-error mt-4">
      <span>No data found</span>
    </div>
  {/if}
{:else}
  <div
    class="sticky px-2 top-0 z-40 bg-base-100 transition-shadow duration-50 {isScrolled
      ? ''
      : ''}"
  >
    <h1
      class="font-bold transition-all duration-50 ml-2 {isScrolled
        ? 'text-lg mb-0 py-1'
        : 'text-3xl mb-2 mt-2'}"
    >
      {title}
    </h1>

    <div class="flex flex-wrap items-center gap-1 pb-1">
      <div role="tablist" class="tabs tabs-box tabs-xs">
        {#each Object.keys(allData) as tab}
          <input
            type="radio"
            name={discTabsName}
            role="tab"
            class="tab {tab === 'wag' ? 'checked:bg-primary checked:text-primary-content' : 'checked:bg-secondary checked:text-secondary-content'}"
            aria-label={tab.toUpperCase()}
            checked={activeTab === tab}
            onchange={() => applyTab(tab)}
          />
        {/each}
      </div>
      {#if extraControls}
        {@render extraControls()}
      {/if}

      <label class="input input-bordered input-xs flex items-center gap-1 w-64">
        <span class="text-base-content/50 text-xs">🔍</span>
        <input
          type="text"
          class="grow text-xs w-12"
          placeholder="Search name or ID"
          bind:value={rawSearchInput}
        />
      </label>

      {#if totalPages > 1}
        <div class="join ml-1">
          <button class="btn btn-xs join-item" disabled={currentPage <= 1}
            onclick={() => { if (currentPage > 1) currentPage--; }}
          >«</button>
          <button class="btn btn-xs join-item no-animation">{currentPage}/{totalPages}</button>
          <button class="btn btn-xs join-item" disabled={currentPage >= totalPages}
            onclick={() => { if (currentPage < totalPages) currentPage++; }}
          >»</button>
        </div>
      {/if}

      <span class="text-xs text-base-content/50 ml-auto">
        Showing {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, filteredCount)} of {filteredCount} results
      </span>

      {#if download}
        {@render download({
          columns,
          rows: filteredRows,
          headerLabels: HEADER_LABELS,
        })}
      {/if}
    </div>

    {#if showDuplicateHeaders}
      <div
        class="border-t border-base-300 overflow-x-auto"
        bind:this={dupScrollEl}
      >
        <table class="table table-xs min-w-full">
          <thead>
            <tr>
              {#each frontMeta as col, i}
                <th class={COL_MIN_CLASS[col] ?? ""} style={thStyle(i, col)}>
                  <div class="flex items-center gap-0.5">
                    <button
                      onclick={() => toggleSort(col)}
                      class="hover:text-primary text-xs font-bold"
                    >
                      {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
                      {#if sortCol === col}<span class="text-accent">{sortAsc ? " ▲" : " ▼"}</span>{/if}
                    </button>
                    {#if FILTERABLE_COLS.has(col) && (col !== "event_name" || showEventFilter)}
                      <button
                        onclick={(e) => toggleDropdown(col, e)}
                        class="btn btn-ghost btn-xs px-0.5 min-h-0 h-5"
                        title="Filter"
                      >
                        <span
                          class="text-xs {filterStateFor(col).selected.length
                            ? 'text-primary'
                            : 'opacity-60'}">▾</span
                        >
                        {#if filterStateFor(col).selected.length}
                          <span class="badge badge-xs badge-accent"
                            >{filterStateFor(col).selected.length}</span
                          >
                        {/if}
                      </button>
                    {/if}
                  </div>
                </th>
              {/each}
              {#each apparatusPrefixes as prefix, i}
                <th
                  onclick={() => toggleSort(`${prefix}-total`)}
                  class="cursor-pointer select-none hover:text-primary text-left min-w-12 {COL_MIN_CLASS[
                    prefix
                  ] ?? ''}"
                  style={thStyle(frontMeta.length + i, prefix)}
                >
                  {appDisplayLabel(prefix)}
                  {#if sortCol === `${prefix}-total`}{sortAsc
                      ? " ▲"
                      : " ▼"}{/if}
                </th>
              {/each}
              {#each backMeta as col, i}
                <th
                  class={COL_MIN_CLASS[col] ?? ""}
                  style={thStyle(
                    frontMeta.length + apparatusPrefixes.length + i,
                    col,
                  )}
                >
                  <div class="flex items-center gap-0.5">
                    <button
                      onclick={() => toggleSort(col)}
                      class="hover:text-primary text-xs font-bold"
                    >
                      {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
                      {#if sortCol === col}<span class="text-accent">{sortAsc ? " ▲" : " ▼"}</span>{/if}
                    </button>
                    {#if FILTERABLE_COLS.has(col) && (col !== "event_name" || showEventFilter)}
                      <button
                        onclick={(e) => toggleDropdown(col, e)}
                        class="btn btn-ghost btn-xs px-0.5 min-h-0 h-5"
                        title="Filter"
                      >
                        <span
                          class="text-xs {filterStateFor(col).selected.length
                            ? 'text-primary'
                            : 'opacity-60'}">▾</span
                        >
                        {#if filterStateFor(col).selected.length}
                          <span class="badge badge-xs badge-accent"
                            >{filterStateFor(col).selected.length}</span
                          >
                        {/if}
                      </button>
                    {/if}
                  </div>
                </th>
              {/each}
            </tr>
          </thead>
        </table>
      </div>
    {/if}
  </div>

  <div class="overflow-x-auto pb-48" bind:this={mainScrollEl}>
    <table class="table table-zebra table-xs px-2 min-w-full">
      <thead bind:this={theadEl}>
        <tr>
          {#each frontMeta as col, i}
            <th
              class="cursor-pointer select-none hover:text-primary {COL_MIN_CLASS[
                col
              ] ?? ''}"
            >
              <div class="flex items-center gap-0.5">
                <button
                  onclick={() => toggleSort(col)}
                  class="hover:text-primary text-xs font-bold"
                >
                  {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
                  {#if sortCol === col}
                    <span class="text-accent">{sortAsc ? " ▲" : " ▼"}</span>
                  {/if}
                </button>
                {#if FILTERABLE_COLS.has(col) && (col !== "event_name" || showEventFilter)}
                  <button
                    onclick={(e) => toggleDropdown(col, e)}
                    class="btn btn-ghost btn-xs px-0.5 min-h-0 h-5"
                  >
                    <span
                      class="text-xs {filterStateFor(col).selected.length
                        ? 'text-primary'
                        : 'opacity-60'}">▾</span
                    >
                    {#if filterStateFor(col).selected.length}
                      <span class="badge badge-xs badge-accent"
                        >{filterStateFor(col).selected.length}</span
                      >
                    {/if}
                  </button>
                {/if}
              </div>
            </th>
          {/each}
          {#each apparatusPrefixes as prefix, i}
            <th
              onclick={() => toggleSort(`${prefix}-total`)}
              class="cursor-pointer select-none hover:text-primary text-left min-w-12 {COL_MIN_CLASS[
                prefix
              ] ?? ''}"
              colspan="1"
            >
              {appDisplayLabel(prefix)}
              {#if sortCol === `${prefix}-total`}
                <span class="text-accent">{sortAsc ? " ▲" : " ▼"}</span>
              {/if}
            </th>
          {/each}
          {#each backMeta as col, i}
            <th
              class="cursor-pointer select-none hover:text-primary {COL_MIN_CLASS[
                col
              ] ?? ''}"
            >
              <div class="flex items-center gap-0.5">
                <button
                  onclick={() => toggleSort(col)}
                  class="hover:text-primary text-xs font-bold"
                >
                  {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
                  {#if sortCol === col}
                    <span class="text-accent">{sortAsc ? " ▲" : " ▼"}</span>
                  {/if}
                </button>
                {#if FILTERABLE_COLS.has(col) && (col !== "event_name" || showEventFilter)}
                  <button
                    onclick={(e) => toggleDropdown(col, e)}
                    class="btn btn-ghost btn-xs px-0.5 min-h-0 h-5"
                  >
                    <span
                      class="text-xs {filterStateFor(col).selected.length
                        ? 'text-primary'
                        : 'opacity-60'}">▾</span
                    >
                    {#if filterStateFor(col).selected.length}
                      <span class="badge badge-xs badge-accent"
                        >{filterStateFor(col).selected.length}</span
                      >
                    {/if}
                  </button>
                {/if}
              </div>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each visibleRows as row}
          <tr class="hover:bg-primary/15 transition-colors">
            {#each frontMeta as col}
              <td class="whitespace-nowrap py-1.5 {COL_MIN_CLASS[col] ?? ''}">
                {#if col === "name" && row["gnz-id"]}
                  <a href={`/gymnast/${row["gnz-id"]}`} class="link link-hover"
                    >{row[col] ?? ""}</a
                  >
                {:else if col === "club" && row["club"]}
                  <a
                    href={`/club/${encodeURIComponent(String(row["club"]))}`}
                    class="link link-hover">{row[col] ?? ""}</a
                  >
                {:else if col === "region" && row[col]}
                  {@const pal = REGION_PALETTES[String(row[col])]}
                  {#if pal}
                    <span class="inline-flex items-center gap-1">
                      <span class="w-1.5 h-1.5 rounded-full shrink-0" style="background: {pal[0]}"></span>
                      <span class="w-1.5 h-1.5 rounded-full shrink-0" style="background: {pal[1]}"></span>
                      {row[col]}
                    </span>
                  {:else}
                    {row[col]}
                  {/if}
                {:else if col === "event_name"}
                  <span class="truncate block max-w-56">{row[col] ?? ""}</span>
                {:else}
                  {row[col] ?? ""}
                {/if}
              </td>
            {/each}
            {#each apparatusPrefixes as prefix, i}
              <td class="text-left min-w-12 whitespace-nowrap py-1.5 {COL_MIN_CLASS[prefix] ?? ''}">
                <ScoreTooltip {row} {prefix} isLast={i === apparatusPrefixes.length - 1} />
              </td>
            {/each}
            {#each backMeta as col}
              {#if col === "aa-score"}
                <td class="whitespace-nowrap py-1.5 {COL_MIN_CLASS[col] ?? ''}">
                  <AATooltip {row} prefixes={apparatusPrefixes} />
                </td>
              {:else}
                <td class="whitespace-nowrap py-1.5 {COL_MIN_CLASS[col] ?? ''}"
                  >{row[col] ?? ""}</td
                >
              {/if}
            {/each}
          </tr>
        {:else}
          <tr>
            <td colspan="100%" class="text-center py-8 text-base-content/60">
              No results found matching criteria.
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if totalPages > 1}
    <div class="flex items-center justify-between gap-2 mt-2">
      <div class="join">
        <button
          class="btn btn-sm join-item"
          disabled={currentPage <= 1}
          onclick={() => { if (currentPage > 1) currentPage--; }}
        >
          « Prev
        </button>
        <button class="btn btn-sm join-item no-animation">
          Page {currentPage} of {totalPages}
        </button>
        <button
          class="btn btn-sm join-item"
          disabled={currentPage >= totalPages}
          onclick={() => { if (currentPage < totalPages) currentPage++; }}
        >
          Next »
        </button>
      </div>
      <select
        class="select select-bordered select-sm"
        value={pageSize}
        onchange={(e) => {
          pageSize = Number((e.target as HTMLSelectElement).value);
          currentPage = 1;
        }}
      >
        <option value={25}>25 per page</option>
        <option value={50}>50 per page</option>
        <option value={100}>100 per page</option>
      </select>
    </div>
  {/if}

  {#if openDropdown}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="fixed inset-0 z-40" onclick={() => (openDropdown = null)}></div>
    <div
      class="fixed z-50 bg-base-100 border border-base-300 rounded-box shadow-xl p-2 min-w-44 max-h-60 overflow-y-auto"
      style="top:{openDropdownY}px; left:{openDropdownX}px"
    >
      <div class="flex justify-between px-1 pb-1 border-b border-base-200 mb-1">
        <span class="font-bold text-xs"
          >{filterStateFor(openDropdown).label}</span
        >
        {#if filterStateFor(openDropdown).selected.length}
          <button
            onclick={() => {
              clearFilter(openDropdown);
              openDropdown = null;
            }}
            class="text-xs link link-hover"
          >
            Clear
          </button>
        {/if}
      </div>
      {#each filterStateFor(openDropdown).options as opt}
        <label
          class="flex items-center gap-1.5 px-1 py-0.5 text-xs cursor-pointer hover:bg-base-200 rounded"
        >
          <input
            type="checkbox"
            checked={filterStateFor(openDropdown).selected.includes(opt)}
            onchange={() => toggleFilterOption(openDropdown, opt)}
            class="checkbox checkbox-xs"
          />
          {opt}
        </label>
      {/each}
    </div>
  {/if}
{/if}
