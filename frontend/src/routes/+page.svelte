<script lang="ts">
  import { onMount } from "svelte";
  import { uploadFile, checkAuthStatus } from "$lib/api";
  import { goto } from "$app/navigation";
  import { isLoggedIn, authConfigured } from "$lib/auth";

  let uploading = $state(false);
  let result = $state<{
    id: number;
    name: string;
    gymnast_count: number;
    score_count?: number;
    club_count?: number;
  } | null>(null);
  let errorMessage = $state<string | null>(null);
  let errorDetails = $state<string[]>([]);
  let errorRaw = $state<string | null>(null);
  let showErrorDetail = $state(false);
  let loggedIn = $state(false);

  onMount(() => {
    checkAuthStatus()
      .then((s) => authConfigured.set(s.configured))
      .catch(() => {});
    const unsub = isLoggedIn.subscribe((v) => (loggedIn = v));
    return unsub;
  });

  async function handleFile(file: File) {
    if (!file.name.endsWith(".json")) {
      errorMessage = "Please select a .json file";
      errorDetails = [];
      errorRaw = null;
      return;
    }
    uploading = true;
    errorMessage = null;
    errorDetails = [];
    errorRaw = null;
    result = null;
    try {
      const ev = await uploadFile(file);
      result = ev;
    } catch (err) {
      const text = String(err);
      errorRaw = text;
      try {
        const parsed = JSON.parse(text);
        if (parsed.errors && Array.isArray(parsed.errors)) {
          errorDetails = parsed.errors;
          errorMessage = parsed.message || "Upload failed";
        } else if (parsed.detail) {
          errorMessage = parsed.detail;
        } else {
          errorMessage = text;
        }
      } catch {
        const msg = err instanceof Error ? err.message : text;
        errorMessage = msg || text;
      }
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

{#if !loggedIn}
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
    <a
      href="/events"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
    >
      <div class="card-body items-center text-center py-8">
        <span class="text-4xl mb-2">📋</span>
        <h2 class="card-title">Events</h2>
        <p class="text-sm text-base-content/70">Browse uploaded events</p>
      </div>
    </a>
    <a
      href="/results"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
    >
      <div class="card-body items-center text-center py-8">
        <span class="text-4xl mb-2">🏆</span>
        <h2 class="card-title">Results</h2>
        <p class="text-sm text-base-content/70">View all results across events</p>
      </div>
    </a>
    <a
      href="/login"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
    >
      <div class="card-body items-center text-center py-8">
        <span class="text-4xl mb-2">🔐</span>
        <h2 class="card-title">Login</h2>
        <p class="text-sm text-base-content/70">Upload new events</p>
      </div>
    </a>
  </div>
{:else}
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

  {#if errorMessage}
    <div class="alert alert-error mt-4">
      <div class="flex flex-col gap-2 w-full">
        <span>{errorMessage}</span>
        {#if errorDetails.length > 0}
          <ul class="list-disc list-inside text-sm opacity-80">
            {#each errorDetails as detail}
              <li>{detail}</li>
            {/each}
          </ul>
        {/if}
        {#if errorRaw}
          <button
            class="btn btn-ghost btn-xs self-start"
            onclick={() => (showErrorDetail = !showErrorDetail)}
          >
            {showErrorDetail ? "Hide details" : "Show details"}
          </button>
          {#if showErrorDetail}
            <pre class="text-xs opacity-60 whitespace-pre-wrap max-h-48 overflow-y-auto bg-base-300 p-2 rounded">{errorRaw}</pre>
          {/if}
        {/if}
      </div>
    </div>
  {/if}

  {#if result}
    <div class="card bg-base-200 border border-success/30 mt-6">
      <div class="card-body">
        <h2 class="card-title text-lg">{result.name}</h2>
        <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <span><strong>{result.gymnast_count}</strong> gymnasts</span>
          {#if result.score_count != null}
            <span><strong>{result.score_count}</strong> scores</span>
          {/if}
          {#if result.club_count != null}
            <span><strong>{result.club_count}</strong> clubs</span>
          {/if}
        </div>
        <div class="card-actions mt-2">
          <a href="/events/{result.id}" class="btn btn-primary btn-sm">View Results</a>
          <a href="/events" class="btn btn-ghost btn-sm">All Events</a>
        </div>
      </div>
    </div>
  {/if}

  <p class="text-center text-base-content/50 mt-8">
    Already uploaded an event? <a href="/events" class="link link-primary">Browse events</a>
  </p>
{/if}</div>
