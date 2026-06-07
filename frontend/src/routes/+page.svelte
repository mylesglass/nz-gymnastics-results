<script lang="ts">
  import { onMount } from "svelte";
  import { checkAuthStatus } from "$lib/api";
  import { authConfigured } from "$lib/auth";

  let authCfg = $state(false);

  onMount(() => {
    checkAuthStatus()
      .then((s) => authConfigured.set(s.configured))
      .catch(() => {});
    const unsub = authConfigured.subscribe((v) => (authCfg = v));
    return unsub;
  });
</script>

<svelte:head>
  <title>NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <div class="text-center mb-10 mt-4">
    <h1 class="text-4xl font-bold mb-3">NZ Gymnastics Results</h1>
    <p class="text-lg text-base-content/70 max-w-2xl mx-auto">
      A community tool for viewing, searching, and sharing New Zealand gymnastics
      competition results. Upload a Scoreholder JSON export to get started.
    </p>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <a
      href="/events"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
    >
      <div class="card-body items-center text-center py-8">
        <span class="text-4xl mb-2">📋</span>
        <h2 class="card-title">Events</h2>
        <p class="text-sm text-base-content/70">Browse uploaded events by name, year, or discipline</p>
      </div>
    </a>
    <a
      href="/results"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
    >
      <div class="card-body items-center text-center py-8">
        <span class="text-4xl mb-2">🏆</span>
        <h2 class="card-title">Results</h2>
        <p class="text-sm text-base-content/70">View all results across every event in one place</p>
      </div>
    </a>
    <a
      href={authCfg ? "/login" : "/upload"}
      class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
    >
      <div class="card-body items-center text-center py-8">
        <span class="text-4xl mb-2">📄</span>
        <h2 class="card-title">Upload</h2>
        <p class="text-sm text-base-content/70">
          {authCfg ? "Log in to upload a new competition" : "Upload a Scoreholder JSON file"}
        </p>
      </div>
    </a>
  </div>

  <div class="mt-12 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
    <div class="card bg-base-200/50">
      <div class="card-body">
        <h3 class="card-title text-base">How it works</h3>
        <ol class="list-decimal list-inside text-sm text-base-content/70 space-y-1">
          <li>Export a competition from Scoreholder as JSON</li>
          <li>Upload the file here — it's parsed automatically</li>
          <li>Browse results with WAG/MAG tabs, filterable columns, and per-apparatus tooltips</li>
          <li>Export to CSV or XLSX for offline use</li>
        </ol>
      </div>
    </div>
    <div class="card bg-base-200/50">
      <div class="card-body">
        <h3 class="card-title text-base">Features</h3>
        <ul class="list-disc list-inside text-sm text-base-content/70 space-y-1">
          <li>Per-gymnast results across all events</li>
          <li>Club overview pages</li>
          <li>Wide-format table with AA totals and tooltips</li>
          <li>Sortable columns and text search</li>
        </ul>
      </div>
    </div>
  </div>
</div>
