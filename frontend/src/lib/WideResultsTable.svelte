<script lang="ts">
  import { onMount } from "svelte";
  import type { Snippet } from "svelte";
  import ScoreTooltip from "./ScoreTooltip.svelte";
  import MultiSelect from "./MultiSelect.svelte";

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
    showEventFilter = false,
    extraHeadLabels = {} as Record<string, string>,
    download,
    empty,
  }: {
    loadData: () => Promise<LoadDataResult>;
    showEventFilter?: boolean;
    extraHeadLabels?: Record<string, string>;
    download?: Snippet<[DownloadArgs]>;
    empty?: Snippet;
  } = $props();

  let loading = $state(true);
  let isScrolled = $state(false);
  let showDuplicateHeaders = $state(false);
  let activeTab = $state("wag");
  let columns = $state<string[]>([]);
  let rows = $state<Record<string, unknown>[]>([]);
  let allData = $state<Record<string, TabData>>({});
  let title = $state("");
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

  let theadEl: HTMLElement | undefined = $state();
  let mainScrollEl: HTMLElement | undefined = $state();
  let dupScrollEl: HTMLElement | undefined = $state();
  let columnWidths = $state<number[]>([]);

  const BASE_LABELS: Record<string, string> = {
    "gnz-id": "ID",
    name: "Name",
    club: "Club",
    step: "STEP",
    division: "Division",
    "round-type": "Round",
    "aa-score": "AA",
    "aa-rank": "Rank",
  };
  let HEADER_LABELS = $derived({ ...BASE_LABELS, ...extraHeadLabels });

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

  function thStyle(i: number): string {
    const w = columnWidths[i];
    return w ? `width:${w}px;min-width:${w}px` : "";
  }

  onMount(() => {
    const onScroll = () => {
      isScrolled = window.scrollY > 60;
    };
    window.addEventListener("scroll", onScroll, { passive: true });

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
      .catch(() => {
        allData = {};
      })
      .finally(() => {
        loading = false;
      });

    return () => window.removeEventListener("scroll", onScroll);
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
        const cmp = String(va).localeCompare(String(vb), undefined, {
          numeric: true,
          sensitivity: "base",
        });
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

{#if loading}
  <h1 class="text-3xl font-bold mb-2">{title || "Results"}</h1>
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if Object.keys(allData).length === 0}
  <h1 class="text-3xl font-bold mb-2">{title || "Results"}</h1>
  {#if empty}
    {@render empty()}
  {:else}
    <div role="alert" class="alert alert-error mt-4">
      <span>No data found</span>
    </div>
  {/if}
{:else}
  <div
    class="sticky px-2 top-0 z-40 bg-base-100 transition-shadow duration-50 {isScrolled
      ? 'shadow-sm'
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

      <label class="input input-bordered input-xs flex items-center gap-1 w-64">
        <span class="text-base-content/50 text-xs">🔍</span>
        <input
          type="text"
          class="grow text-xs w-12"
          placeholder="Search name or ID"
          bind:value={searchText}
        />
      </label>

      {#if showEventFilter && eventOptions.length > 1}
        <MultiSelect
          options={eventOptions}
          bind:selected={filterEvent}
          label="Event"
          placeholder="Event"
        />
      {/if}

      <MultiSelect
        options={stepOptions}
        bind:selected={filterStep}
        label={stepLabel}
        placeholder={stepLabel}
      />
      <MultiSelect
        options={clubOptions}
        bind:selected={filterClub}
        label="Club"
        placeholder="Club"
      />
      <MultiSelect
        options={divisionOptions}
        bind:selected={filterDivision}
        label="Div"
        placeholder="Div"
      />
      <MultiSelect
        options={roundOptions}
        bind:selected={filterRound}
        label="Round"
        placeholder="Round"
      />

      <span class="text-xs text-base-content/50 ml-1">
        Showing {filteredCount}{filteredCount < totalCount
          ? ` of ${totalCount}`
          : ""} results
      </span>

      {#if download}
        {@render download({
          columns,
          rows: filteredRows(),
          headerLabels: HEADER_LABELS,
        })}
      {/if}
    </div>

    {#if showDuplicateHeaders}
      <div
        class="border-t border-base-300 overflow-x-auto"
        bind:this={dupScrollEl}
      >
        <table class="table table-xs">
          <thead>
            <tr>
              {#each frontMeta as col, i}
                <th
                  onclick={() => toggleSort(col)}
                  class="cursor-pointer select-none hover:text-primary"
                  style={thStyle(i)}
                >
                  {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
                  {#if sortCol === col}{sortAsc ? " ▲" : " ▼"}{/if}
                </th>
              {/each}
              {#each apparatusPrefixes as prefix, i}
                <th
                  onclick={() => toggleSort(`${prefix}-total`)}
                  class="cursor-pointer select-none hover:text-primary text-center"
                  style={thStyle(frontMeta.length + i)}
                >
                  {appDisplayLabel(prefix)}
                  {#if sortCol === `${prefix}-total`}{sortAsc
                      ? " ▲"
                      : " ▼"}{/if}
                </th>
              {/each}
              {#each backMeta as col, i}
                <th
                  onclick={() => toggleSort(col)}
                  class="cursor-pointer select-none hover:text-primary"
                  style={thStyle(
                    frontMeta.length + apparatusPrefixes.length + i,
                  )}
                >
                  {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
                  {#if sortCol === col}{sortAsc ? " ▲" : " ▼"}{/if}
                </th>
              {/each}
            </tr>
          </thead>
        </table>
      </div>
    {/if}
  </div>

  <div class="overflow-x-auto" bind:this={mainScrollEl}>
    <table class="table table-zebra table-xs px-2">
      <thead bind:this={theadEl}>
        <tr>
          {#each frontMeta as col, i}
            <th
              onclick={() => toggleSort(col)}
              class="cursor-pointer select-none hover:text-primary"
              style="min-width:{columnWidths[i] || ''}px"
            >
              {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
              {#if sortCol === col}
                {sortAsc ? " ▲" : " ▼"}
              {/if}
            </th>
          {/each}
          {#each apparatusPrefixes as prefix, i}
            <th
              onclick={() => toggleSort(`${prefix}-total`)}
              class="cursor-pointer select-none hover:text-primary text-center"
              colspan="1"
              style="min-width:{columnWidths[frontMeta.length + i] || ''}px"
            >
              {appDisplayLabel(prefix)}
              {#if sortCol === `${prefix}-total`}
                {sortAsc ? " ▲" : " ▼"}
              {/if}
            </th>
          {/each}
          {#each backMeta as col, i}
            <th
              onclick={() => toggleSort(col)}
              class="cursor-pointer select-none hover:text-primary"
              style="min-width:{columnWidths[
                frontMeta.length + apparatusPrefixes.length + i
              ] || ''}px"
            >
              {col === "step" ? stepLabel : (HEADER_LABELS[col] ?? col)}
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
              <td class="whitespace-nowrap">
                {#if col === "name" && row["gnz-id"]}
                  <a href={`/gymnast/${row["gnz-id"]}`} class="link link-hover">{row[col] ?? ""}</a>
                {:else if col === "club" && row["club"]}
                  <a href={`/club/${encodeURIComponent(String(row["club"]))}`} class="link link-hover">{row[col] ?? ""}</a>
                {:else}
                  {row[col] ?? ""}
                {/if}
              </td>
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
