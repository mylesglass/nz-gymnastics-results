<script lang="ts">
  import { onMount } from "svelte";
  import { checkAuthStatus, getStats } from "$lib/api";
  import { authConfigured } from "$lib/auth";

  let authCfg = $state(false);
  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);

  onMount(() => {
    checkAuthStatus()
      .then((s) => authConfigured.set(s.configured))
      .catch(() => {});
    const unsub = authConfigured.subscribe((v) => (authCfg = v));
    getStats()
      .then((s) => (stats = s))
      .catch(() => {});
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

  {#if stats}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
      <a href="/events" class="stat bg-base-200 rounded-box hover:bg-base-300 transition-all cursor-pointer">
        <div class="stat-title text-base-content/60 text-xs">Events</div>
        <div class="stat-value text-2xl">{stats.total_events}</div>
      </a>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Gymnasts</div>
        <div class="stat-value text-2xl">{stats.total_gymnasts.toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Scores</div>
        <div class="stat-value text-2xl">{stats.total_scores.toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Clubs</div>
        <div class="stat-value text-2xl">{stats.total_clubs}</div>
      </div>
    </div>
  {:else}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
      {#each [1, 2, 3, 4] as _}
        <div class="stat bg-base-200 rounded-box animate-pulse">
          <div class="stat-title text-base-content/60 text-xs">&nbsp;</div>
          <div class="stat-value text-2xl">&nbsp;</div>
        </div>
      {/each}
    </div>
  {/if}
</div>
