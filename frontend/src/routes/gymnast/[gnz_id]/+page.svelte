<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { getAllWideResults, getMedals, type MedalCounts } from "$lib/api";
  import { selectedYear } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import MedalBadges from "$lib/MedalBadges.svelte";

  let filterYear = $state<string | null>(null);
  let ready = $state(false);
  let gymnastFound = $state(false);
  let gymnastName = $state("");
  let medals = $state<MedalCounts | null>(null);
  let medalsLoading = $state(true);

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    ready = true;
    return unsub;
  });

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

{#if ready}
  <WideResultsTable
    loadData={loadDataImpl}
    loadKey={filterYear ?? ""}
    showEventFilter={true}
    extraHeadLabels={{ event_name: "Event" }}
    {download}
    {empty}
    {controls}
  />
{/if}
