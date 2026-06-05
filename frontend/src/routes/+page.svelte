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

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Upload Event</h1>

<p class="text-base-content/70 mb-6">
  Upload a Scoreholder JSON export to view, export, and analyse results.
</p>

<div
  class="card border-2 border-dashed border-base-content/30 hover:border-primary bg-base-200/50 hover:bg-base-200 cursor-pointer transition-all p-12 text-center"
  role="button"
  tabindex="0"
  ondrop={ondrop}
  ondragover={ondragover}
>
  {#if uploading}
    <div class="flex flex-col items-center gap-3">
      <span class="loading loading-spinner loading-lg text-primary"></span>
      <p class="text-base-content/70">Uploading and parsing...</p>
    </div>
  {:else}
    <div class="flex flex-col items-center gap-3">
      <span class="text-4xl">📄</span>
      <p class="text-base-content/70">Drop a Scoreholder JSON file here, or click to browse</p>
      <input type="file" accept=".json" onchange={onfileinput} hidden />
    </div>
  {/if}
</div>

{#if error}
  <div role="alert" class="alert alert-error mt-4">
    <span>{error}</span>
  </div>
{/if}

{#if result}
  <div class="card bg-base-200 border border-success/30 mt-6">
    <div class="card-body">
      <h2 class="card-title text-lg">{result.name}</h2>
      <p>{result.gymnast_count} gymnasts parsed</p>
      <div class="card-actions mt-2">
        <a href="/events/{result.id}" class="btn btn-primary btn-sm">View Results</a>
        <a href="/events" class="btn btn-ghost btn-sm">All Events</a>
      </div>
    </div>
  </div>
{/if}

{#if !uploading && !result}
  <p class="text-center text-base-content/50 mt-8">
    Already uploaded an event? <a href="/events" class="link link-primary">Browse events</a>
  </p>
{/if}</div>