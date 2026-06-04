<script lang="ts">
  import { uploadFile } from "$lib/api";
  import { goto } from "$app/navigation";

  let uploading = $state(false);
  let result = $state<{ id: number; name: string; gymnast_count: number } | null>(null);
  let error = $state<string | null>(null);

  async function handleFile(file: File) {
    if (!file.name.endsWith(".json")) {
      error = "Please select a .json file";
      return;
    }
    uploading = true;
    error = null;
    result = null;
    try {
      const ev = await uploadFile(file);
      result = ev;
    } catch (err) {
      error = String(err);
    } finally {
      uploading = false;
    }
  }

  function ondrop(e: DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file) handleFile(file);
  }

  function ondragover(e: DragEvent) {
    e.preventDefault();
  }

  function onfileinput(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) handleFile(file);
  }
</script>

<svelte:head>
  <title>NZ Gymnastics Results</title>
</svelte:head>

<h1>NZ Gymnastics Results</h1>

<p>Upload a Scoreholder JSON export to view, export, and analyse results.</p>

<div
  class="drop-zone"
  role="button"
  tabindex="0"
  ondrop={ondrop}
  ondragover={ondragover}
>
  {#if uploading}
    <p>Uploading and parsing...</p>
  {:else}
    <p>Drop a Scoreholder JSON file here, or click to browse</p>
    <input type="file" accept=".json" onchange={onfileinput} hidden />
  {/if}
</div>

{#if error}
  <p class="error">{error}</p>
{/if}

{#if result}
  <div class="result-card">
    <h2>{result.name}</h2>
    <p>{result.gymnast_count} gymnasts parsed</p>
    <div class="actions">
      <a href="/events/{result.id}">View Results</a>
      <a href="/events">All Events</a>
    </div>
  </div>
{/if}

{#if !uploading && !result}
  <div class="info">
    <p>Already uploaded an event? <a href="/events">Browse events</a></p>
  </div>
{/if}

<style>
  .drop-zone {
    border: 2px dashed #aaa;
    border-radius: 8px;
    padding: 3rem;
    text-align: center;
    cursor: pointer;
    margin: 2rem 0;
    transition: border-color 0.2s, background 0.2s;
  }
  .drop-zone:hover {
    border-color: #3b82f6;
    background: #f8faff;
  }
  .error {
    color: #dc2626;
  }
  .result-card {
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 8px;
    padding: 1.5rem;
    margin: 1rem 0;
  }
  .result-card h2 {
    margin: 0 0 0.5rem;
  }
  .actions {
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
  }
  .actions a {
    padding: 0.5rem 1rem;
    background: #3b82f6;
    color: #fff;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 500;
  }
  .actions a:hover {
    background: #2563eb;
  }
  .info {
    text-align: center;
    margin-top: 2rem;
    color: #666;
  }
</style>