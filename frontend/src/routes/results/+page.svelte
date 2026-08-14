<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { getAllWideResults } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import Seo from "$lib/Seo.svelte";

  let {
    data,
  }: {
    data: { totalScores: number | null };
  } = $props();

  let resultsDescription = $derived(
    data.totalScores
      ? `View all ${data.totalScores.toLocaleString()} gymnastics scores across every event in one place — WAG & MAG, per-apparatus breakdowns and all-around totals.`
      : "View all gymnastics scores across every New Zealand event in one place — WAG & MAG."
  );

  let filterYear = $state<string | null>(null);
  let ready = $state(true);

  onMount(async () => {
    const unsub1 = selectedYear.subscribe((v) => {
      filterYear = v;
    });
    const unsub2 = yearOptions.subscribe((v) => {
      if (v.length > 0) {
        selectedYear.update((cur) => cur ?? v[0]);
      }
    });
    ready = true;
    return () => { unsub1(); unsub2(); };
  });

  function loadDataImpl() {
    const params = filterYear ? { year: parseInt(filterYear) } : undefined;
    return getAllWideResults(params).then((r) => ({
      title: "All Results",
      tabs: {
        ...(r.wag ? { wag: r.wag } : {}),
        ...(r.mag ? { mag: r.mag } : {}),
      },
    }));
  }
</script>

<Seo
  title="All Results"
  path="/results"
  origin={$page.url.origin}
  description={resultsDescription}
/>

{#snippet download({columns, rows, headerLabels, pdfColumns, colFormat})}
  <ExportMenu {columns} {rows} {headerLabels} {pdfColumns} {colFormat} title={filterYear ? `All Results ${filterYear}` : "All Results"} filename={filterYear ? `All Results ${filterYear}` : "All Results"} />
{/snippet}

{#snippet empty()}
  <div class="card bg-base-200 mt-4">
    <div class="card-body items-center text-center py-12">
      <p class="text-base-content/70">No results yet.</p>
      <a href="/admin#upload" class="btn btn-primary btn-sm mt-2">Upload an event</a>
    </div>
  </div>
{/snippet}

{#if ready}
  <WideResultsTable
    loadData={loadDataImpl}
    loadKey={filterYear ?? ""}
    showEventFilter={true}
    extraHeadLabels={{ event_name: "Event" }}
    initialTitle="All Results"
    {download}
    {empty}
  />
{/if}
