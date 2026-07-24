<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { getAllWideResults } from "$lib/api";
  import { selectedYear } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";

  let filterYear = $state<string | null>(null);
  let ready = $state(false);

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    ready = true;
    return unsub;
  });

  function loadDataImpl() {
    const club = $page.params.club;
    if (!club) return Promise.resolve({ title: "Club", tabs: {} });
    const params: { club: string; year?: number } = { club };
    if (filterYear) params.year = parseInt(filterYear);
    return getAllWideResults(params).then((r) => ({
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
