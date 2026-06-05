<script lang="ts">
  import { page } from "$app/stores";
  import { getAllWideResults } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";

  function loadData() {
    const gnzId = $page.params.gnz_id;
    if (!gnzId) return Promise.resolve({ title: "Gymnast", tabs: {} });
    return getAllWideResults({ gnz_id: gnzId }).then((r) => {
      const name = r.wag?.rows[0]?.name || r.mag?.rows[0]?.name || gnzId;
      return {
        title: name,
        tabs: {
          ...(r.wag ? { wag: r.wag } : {}),
          ...(r.mag ? { mag: r.mag } : {}),
        },
      };
    });
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
    a.download = `${$page.params.gnz_id || "gymnast"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<svelte:head>
  <title>Gymnast — NZ Gymnastics Results</title>
</svelte:head>

{#snippet download({columns, rows, headerLabels})}
  <button onclick={() => exportCSV(columns, rows, headerLabels)} class="btn btn-outline btn-sm ml-auto">
    Download CSV
  </button>
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Gymnast not found</span>
  </div>
{/snippet}

<WideResultsTable
  {loadData}
  showEventFilter={true}
  extraHeadLabels={{ event_name: "Event" }}
  {download}
  {empty}
/>
