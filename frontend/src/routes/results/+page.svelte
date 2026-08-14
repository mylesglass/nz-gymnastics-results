<script lang="ts">
  import { onMount } from "svelte";
  import { getAllWideResults } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";

  let filterYear = $state<string | null>(null);
  let ready = $state(false);

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

<svelte:head>
  <title>All Results — NZ Gymnastics Results</title>
</svelte:head>

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
    {download}
    {empty}
  />
{/if}
