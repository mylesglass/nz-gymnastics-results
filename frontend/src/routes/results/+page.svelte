<script lang="ts">
  import { onMount } from "svelte";
  import { listEvents, getAllWideResults } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";

  let yearOptions = $state<string[]>([]);
  let filterYear = $state("");
  let ready = $state(false);

  onMount(async () => {
    try {
      const events = await listEvents();
      const years = new Set<string>();
      for (const e of events) {
        if (e.year) years.add(String(e.year));
      }
      yearOptions = [...years].sort().reverse();
      if (yearOptions.length > 0) {
        filterYear = yearOptions[0];
      }
    } catch {
      // ignore
    }
    ready = true;
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

  function exportCSV(columns: string[], rows: Record<string, unknown>[], headerLabels: Record<string, string>) {
    const header = columns.map((c) => headerLabels[c] ?? c);
    const lines = [
      header.join(","),
      ...rows.map((r) =>
        columns
          .map((c) => {
            const v = r[c];
            const s = v == null ? "" : String(v);
            return s.includes(",") || s.includes('"') || s.includes("\n")
              ? `"${s.replace(/"/g, '""')}"`
              : s;
          })
          .join(","),
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

{#snippet download({columns, rows, headerLabels})}
  <button onclick={() => exportCSV(columns, rows, headerLabels)} class="btn btn-outline btn-sm ml-auto">
    Download CSV
  </button>
{/snippet}

{#snippet empty()}
  <div class="card bg-base-200 mt-4">
    <div class="card-body items-center text-center py-12">
      <p class="text-base-content/70">No results yet.</p>
      <a href="/upload" class="btn btn-primary btn-sm mt-2">Upload an event</a>
    </div>
  </div>
{/snippet}

{#snippet extraControls()}
  {#if yearOptions.length > 1}
    <select class="select select-bordered select-xs w-20" bind:value={filterYear}>
      <option value="">All years</option>
      {#each yearOptions as y}
        <option value={y}>{y}</option>
      {/each}
    </select>
  {/if}
{/snippet}

{#if ready}
  {#key filterYear}
    <WideResultsTable
      loadData={loadDataImpl}
      {extraControls}
      showEventFilter={true}
      extraHeadLabels={{ event_name: "Event" }}
      {download}
      {empty}
    />
  {/key}
{/if}
