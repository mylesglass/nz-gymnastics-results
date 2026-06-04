<script lang="ts">
  import { onMount } from "svelte";
  import { getResults, getExportUrl } from "$lib/api";

  let { params } = $props();
  let loading = $state(true);
  let data = $state<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null);

  onMount(async () => {
    try {
      data = await getResults(Number(params.id));
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Results — NZ Gymnastics Results</title>
</svelte:head>

<h1>Results</h1>

<a href="/events">← All events</a>

<div class="exports">
  <a href={getExportUrl(Number(params.id), "csv")}>Download CSV</a>
  <a href={getExportUrl(Number(params.id), "xlsx")}>Download XLSX</a>
</div>

{#if loading}
  <p>Loading...</p>
{:else if data}
  <table>
    <thead>
      <tr>
        {#each data.columns as col}
          <th>{col}</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each data.rows as row}
        <tr>
          {#each data.columns as col}
            <td>{row[col] ?? ""}</td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .exports {
    margin: 1rem 0;
    display: flex;
    gap: 1rem;
  }
  table {
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th, td {
    border: 1px solid #ccc;
    padding: 4px 8px;
    text-align: center;
  }
  th {
    background: #f5f5f5;
    font-weight: 600;
  }
</style>