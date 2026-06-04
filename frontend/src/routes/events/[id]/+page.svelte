<script lang="ts">
  import { onMount } from "svelte";
  import { getWideResults, getExportUrl } from "$lib/api";
  import { page } from "$app/stores";

  let loading = $state(true);
  let eventName = $state("");
  let eventDisc = $state("");
  let activeTab = $state("wag");
  let columns = $state<string[]>([]);
  let rows = $state<Record<string, unknown>[]>([]);
  let allData = $state<Record<string, { columns: string[]; rows: Record<string, unknown>[] }>>({});
  let sortCol = $state<string | null>(null);
  let sortAsc = $state(true);

  $effect(() => {
    const id = $page.params.id;
    if (!id) return;
    loading = true;
    getWideResults(Number(id)).then((r) => {
      eventName = r.event.name;
      eventDisc = r.event.discipline;
      allData = {};
      if (r.wag) allData.wag = r.wag;
      if (r.mag) allData.mag = r.mag;
      const keys = Object.keys(allData);
      if (keys.length > 0) {
        activeTab = keys[0];
        applyTab(keys[0]);
      }
    }).catch(() => {
      allData = {};
    }).finally(() => {
      loading = false;
    });
  });

  function applyTab(tab: string) {
    activeTab = tab;
    const d = allData[tab];
    if (d) {
      columns = d.columns;
      rows = d.rows;
    } else {
      columns = [];
      rows = [];
    }
    sortCol = null;
  }

  function sortedRows() {
    if (!rows) return [];
    let result = [...rows];
    if (sortCol) {
      result.sort((a, b) => {
        const va = a[sortCol] ?? "";
        const vb = b[sortCol] ?? "";
        const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" });
        return sortAsc ? cmp : -cmp;
      });
    }
    return result;
  }

  function toggleSort(col: string) {
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
  }
</script>

<svelte:head>
  <title>Results — NZ Gymnastics Results</title>
</svelte:head>

<h1>{eventName || "Results"}</h1>

<a href="/events">← All events</a>

<div class="exports">
  <a href={getExportUrl(Number($page.params.id), "csv")}>Download CSV</a>
  <a href={getExportUrl(Number($page.params.id), "xlsx")}>Download XLSX</a>
</div>

{#if loading}
  <p>Loading...</p>
{:else if Object.keys(allData).length === 0}
  <p class="error">Event not found</p>
{:else}
  <div class="tabs">
    {#each Object.keys(allData) as tab}
      <button
        class="tab"
        class:active={activeTab === tab}
        onclick={() => applyTab(tab)}
      >
        {tab.toUpperCase()}
      </button>
    {/each}
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          {#each columns as col}
            <th onclick={() => toggleSort(col)}>
              {col}
              {#if sortCol === col}
                {sortAsc ? " ▲" : " ▼"}
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each sortedRows() as row}
          <tr>
            {#each columns as col}
              <td>{row[col] ?? ""}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .tabs {
    display: flex;
    gap: 0;
    margin: 1rem 0;
  }
  .tab {
    padding: 0.5rem 1.25rem;
    border: 1px solid #d1d5db;
    background: #f9fafb;
    cursor: pointer;
    font-weight: 500;
    font-size: 0.9rem;
  }
  .tab:first-child {
    border-radius: 6px 0 0 6px;
  }
  .tab:last-child {
    border-radius: 0 6px 6px 0;
  }
  .tab.active {
    background: #3b82f6;
    color: #fff;
    border-color: #3b82f6;
  }
  .exports {
    margin: 1rem 0;
    display: flex;
    gap: 1rem;
  }
  .exports a {
    padding: 0.4rem 0.8rem;
    background: #3b82f6;
    color: #fff;
    border-radius: 6px;
    text-decoration: none;
    font-size: 0.9rem;
  }
  .exports a:hover {
    background: #2563eb;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    border-collapse: collapse;
    font-size: 0.85rem;
    margin-top: 0.5rem;
  }
  th, td {
    border: 1px solid #d1d5db;
    padding: 4px 8px;
    text-align: center;
    white-space: nowrap;
  }
  th {
    background: #f3f4f6;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
  }
  th:hover {
    background: #e5e7eb;
  }
  tr:hover {
    background: #f9fafb;
  }
  .error {
    color: #dc2626;
  }
</style>