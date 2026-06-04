<script lang="ts">
  import { uploadFile } from "$lib/api";
  let uploading = $state(false);
  let result = $state<{ id: number; name: string } | null>(null);
  let error = $state<string | null>(null);

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (!file || !file.name.endsWith(".json")) {
      error = "Please drop a .json file";
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

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }
</script>

<svelte:head>
  <title>NZ Gymnastics Results</title>
</svelte:head>

<h1>NZ Gymnastics Results</h1>

<div
  class="drop-zone"
  role="button"
  tabindex="0"
  on:drop={handleDrop}
  on:dragover={handleDragOver}
>
  {#if uploading}
    <p>Uploading and parsing...</p>
  {:else}
    <p>Drop a Scoreholder JSON file here</p>
  {/if}
</div>

{#if error}
  <p class="error">{error}</p>
{/if}

{#if result}
  <p class="success">
    Parsed <strong>{result.name}</strong>
    (<a href="/events/{result.id}">view results</a>)
  </p>
{/if}

<style>
  .drop-zone {
    border: 2px dashed #ccc;
    border-radius: 8px;
    padding: 3rem;
    text-align: center;
    cursor: pointer;
    margin: 2rem 0;
  }
  .drop-zone:hover {
    border-color: #666;
  }
  .error {
    color: #c33;
  }
  .success {
    color: #3a3;
  }
</style>