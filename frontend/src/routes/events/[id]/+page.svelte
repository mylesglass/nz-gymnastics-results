<script lang="ts">
  import { page } from "$app/stores";
  import { getWideResults, getExportUrl } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";

  function loadData() {
    const id = Number($page.params.id);
    return getWideResults(id).then((r) => ({
      title: r.event.name,
      tabs: {
        ...(r.wag ? { wag: r.wag } : {}),
        ...(r.mag ? { mag: r.mag } : {}),
      },
    }));
  }
</script>

<svelte:head>
  <title>Results — NZ Gymnastics Results</title>
</svelte:head>

{#snippet download()}
  <div class="dropdown dropdown-end ml-auto">
    <button class="btn btn-outline btn-sm">Download ▼</button>
    <ul class="dropdown-content menu bg-base-200 rounded-box z-50 p-2 shadow-md min-w-28">
      <li><a href={getExportUrl(Number($page.params.id), "csv")}>CSV</a></li>
      <li><a href={getExportUrl(Number($page.params.id), "xlsx")}>XLSX</a></li>
    </ul>
  </div>
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Event not found</span>
  </div>
{/snippet}

<WideResultsTable {loadData} {download} {empty} />
