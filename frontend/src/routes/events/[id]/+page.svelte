<script lang="ts">
  import { onMount } from "svelte";
  import { getResults, getExportUrl } from "$lib/api";
  import { page } from "$app/stores";

  let loading = $state(true);
  let data = $state<{ columns: string[]; rows: Record<string, unknown>[]; event: { name: string } } | null>(null);
  let sortCol = $state<string | null>(null);
  let sortAsc = $state(true);

  $effect(() => {
    const id = $page.params.id;
    if (!id) return;
    loading = true;
    getResults(Number(id)).then((r) => {
      data = r;
    }).catch(() => {
      data = null;
    }).finally(() => {
      loading = false;
    });
  });

  function sortedRows() {
    if (!data) return [];
    let rows = [...data.rows];
    if (sortCol) {
      rows.sort((a, b) => {
        const va = a[sortCol] ?? "";
        const vb = b[sortCol] ?? "";
        const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
        return sortAsc ? cmp : -cmp;
      });
    }
    return rows;
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

<h1>{data?.event?.name ?? "Results"}</h1>

<a href="/events">← All events</a>

<div class="exports">
  <a href={getExportUrl(Number($page.params.id), "csv")}>Download CSV</a>
  <a href={getExportUrl(Number($page.params.id), "xlsx")}>Download XLSX</a>
</div>

{#if loading}
  <p>Loading...</p>
{:else if !data}
  <p class="error">Event not found</p>
{:else}
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          {#each data.columns as col}
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
            {#each data.columns as col}
              <td>{row[col] ?? ""}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
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