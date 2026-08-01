<script lang="ts">
  import { page } from "$app/stores";
  import { getWideResults } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";

  let eventName = $state("");

  function loadData() {
    const id = Number($page.params.id);
    return getWideResults(id).then((r) => {
      eventName = r.event.name;
      return {
        title: r.event.name,
        tabs: {
          ...(r.wag ? { wag: r.wag } : {}),
          ...(r.mag ? { mag: r.mag } : {}),
        },
      };
    });
  }
</script>

<svelte:head>
  <title>Results — NZ Gymnastics Results</title>
</svelte:head>

{#snippet download({columns, rows, headerLabels, pdfColumns, colFormat})}
  <ExportMenu {columns} {rows} {headerLabels} {pdfColumns} {colFormat} title={eventName || "Event Results"} filename={eventName ? `${eventName} Results` : `event-${$page.params.id}`} />
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Event not found</span>
  </div>
{/snippet}

<WideResultsTable {loadData} {download} {empty} eventId={Number($page.params.id)} />
