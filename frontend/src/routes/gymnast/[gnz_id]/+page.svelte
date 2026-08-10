<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { page } from "$app/stores";
  import { getAllWideResults, getMedals, type MedalCounts } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import MedalBadges from "$lib/MedalBadges.svelte";
  import SeasonBest from "$lib/SeasonBest.svelte";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_PALETTES } from "$lib/regions";

  let filterYear = $state<string | null>(null);
  let ready = $state(false);
  let gymnastFound = $state(false);
  let gymnastName = $state("");
  let medals = $state<MedalCounts | null>(null);
  let medalsLoading = $state(true);
  let tabs = $state<Record<string, { columns: string[]; rows: Record<string, unknown>[] }> | null>(null);
  let defaultYearApplied = false;

  function applyDefaultYear() {
    if (defaultYearApplied) return;
    if (get(selectedYear) !== null) {
      defaultYearApplied = true;
      return;
    }
    const opts = get(yearOptions);
    if (!opts.length) return;
    const current = String(new Date().getFullYear());
    const target = opts.includes(current) ? current : String(Math.max(...opts.map(Number)));
    selectedYear.set(target);
    defaultYearApplied = true;
  }

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    const unsubYears = yearOptions.subscribe(applyDefaultYear);
    applyDefaultYear();
    ready = true;
    return () => {
      unsub();
      unsubYears();
    };
  });

  function mostCommon(values: string[]): string {
    const counts = new Map<string, number>();
    for (const v of values) {
      const s = v.trim();
      if (!s) continue;
      counts.set(s, (counts.get(s) ?? 0) + 1);
    }
    let best = "";
    let bestCount = 0;
    for (const [k, c] of counts) {
      if (c > bestCount) {
        best = k;
        bestCount = c;
      }
    }
    return best;
  }

  let metaRows = $derived.by(() => {
    if (!tabs) return [];
    return [...(tabs.wag?.rows ?? []), ...(tabs.mag?.rows ?? [])];
  });
  let gnzId = $derived(String($page.params.gnz_id ?? metaRows[0]?.["gnz-id"] ?? ""));
  let club = $derived(mostCommon(metaRows.map((r) => String(r.club ?? ""))));
  let region = $derived(mostCommon(metaRows.map((r) => String(r.region ?? ""))));
  let steps = $derived([
    ...new Set(metaRows.map((r) => String(r.step ?? "")).filter((s) => s)),
  ]);

  $effect(() => {
    const gnzId = $page.params.gnz_id;
    if (!gnzId) return;
    medalsLoading = true;
    getMedals({
      gnz_id: gnzId,
      ...(filterYear ? { year: parseInt(filterYear) } : {}),
    })
      .then((r) => {
        const g = r.gymnasts[0];
        medals = g?.medals ?? null;
      })
      .catch(() => {
        medals = null;
      })
      .finally(() => (medalsLoading = false));
  });

  function loadDataImpl() {
    const gnzId = $page.params.gnz_id;
    if (!gnzId) return Promise.resolve({ title: "Gymnast", tabs: {} });
    const params: { gnz_id: string; year?: number } = { gnz_id: gnzId };
    if (filterYear) params.year = parseInt(filterYear);
    return getAllWideResults(params).then((r) => {
      const rowsExist = Boolean(r.wag?.rows?.length || r.mag?.rows?.length);
      gymnastFound = rowsExist || Boolean(r.name);
      const name = r.name || r.wag?.rows[0]?.name || r.mag?.rows[0]?.name;
      gymnastName = name || "";
      return {
        title: name || "Gymnast",
        tabs: {
          ...(r.wag ? { wag: r.wag } : {}),
          ...(r.mag ? { mag: r.mag } : {}),
        },
      };
    });
  }
</script>

<svelte:head>
  <title>Gymnast — NZ Gymnastics Results</title>
</svelte:head>

{#snippet download({columns, rows, headerLabels, pdfColumns, colFormat})}
  <ExportMenu {columns} {rows} {headerLabels} {pdfColumns} {colFormat} title={gymnastName ? `${gymnastName} Results` : "Gymnast Results"} filename={gymnastName ? `${gymnastName} Results` : `gymnast-${$page.params.gnz_id || "unknown"}`} />
{/snippet}

{#snippet controls()}
  {#if medalsLoading}
    <span class="loading loading-spinner loading-xs text-base-content/50" role="status" aria-label="Loading medals"></span>
  {:else}
    <MedalBadges medals={medals ?? { g: 0, s: 0, b: 0, total: 0 }} />
  {/if}
{/snippet}

{#snippet empty()}
  {#if gymnastFound}
    <div role="alert" class="alert alert-info mt-4">
      <span>There are no results for {filterYear} — try another year.</span>
    </div>
  {:else}
    <div role="alert" class="alert alert-error mt-4">
      <span>Gymnast not found</span>
    </div>
  {/if}
{/snippet}

{#snippet afterHeader()}
  {#if filterYear && tabs}
    <SeasonBest year={filterYear} {tabs} />
  {/if}
{/snippet}

{#snippet nameBadge()}
  {#if filterYear && region}
    <RegionBadge region={region} colors={REGION_PALETTES[region]} />
  {/if}
{/snippet}

{#snippet nameMeta()}
  {#if filterYear && metaRows.length}
    <div class="flex flex-col gap-0.5 text-sm text-base-content/70">
      {#if gnzId}
        <span>{gnzId}</span>
      {/if}
      {#if club}
        <a href={`/club/${encodeURIComponent(club)}`} class="link link-hover">{club}</a>
      {/if}
      {#each steps as s}
        <span>{s}</span>
      {/each}
    </div>
  {/if}
{/snippet}

{#if ready}
  <WideResultsTable
    loadData={loadDataImpl}
    loadKey={filterYear ?? ""}
    showEventFilter={true}
    extraHeadLabels={{ event_name: "Event" }}
    {download}
    {empty}
    {controls}
    {afterHeader}
    {nameBadge}
    {nameMeta}
    onData={(t) => (tabs = t)}
  />
{/if}
