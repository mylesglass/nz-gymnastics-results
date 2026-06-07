<script lang="ts">
  import { getAllWideResults } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";

  function loadData() {
    return getAllWideResults().then((r) => ({
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

<WideResultsTable
  {loadData}
  showEventFilter={true}
  extraHeadLabels={{ event_name: "Event" }}
  {download}
  {empty}
/>
