<script lang="ts">
  import { page } from "$app/stores";
  import { getAllWideResults } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";

  function loadData() {
    const club = $page.params.club;
    if (!club) return Promise.resolve({ title: "Club", tabs: {} });
    return getAllWideResults({ club }).then((r) => ({
      title: club,
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
    a.download = `${$page.params.club || "club"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<svelte:head>
  <title>Club — NZ Gymnastics Results</title>
</svelte:head>

{#snippet download({columns, rows, headerLabels})}
  <button onclick={() => exportCSV(columns, rows, headerLabels)} class="btn btn-outline btn-sm ml-auto">
    Download CSV
  </button>
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Club not found</span>
  </div>
{/snippet}

<WideResultsTable
  {loadData}
  showEventFilter={true}
  extraHeadLabels={{ event_name: "Event" }}
  {download}
  {empty}
/>
