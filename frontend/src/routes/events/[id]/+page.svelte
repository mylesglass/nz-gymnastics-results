<script lang="ts">
  import { page } from "$app/stores";
  import { getWideResults } from "$lib/api";
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
    const id = Number($page.params.id);
    a.href = url;
    a.download = `event-${id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<svelte:head>
  <title>Results — NZ Gymnastics Results</title>
</svelte:head>

{#snippet download({columns, rows, headerLabels})}
  <button onclick={() => exportCSV(columns, rows, headerLabels)} class="btn btn-primary btn-sm ml-auto">
    Download CSV
  </button>
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Event not found</span>
  </div>
{/snippet}

<WideResultsTable {loadData} {download} {empty} />
