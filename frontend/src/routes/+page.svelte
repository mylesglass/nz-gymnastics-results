<script lang="ts">
  import { onMount } from "svelte";
  import { checkAuthStatus, getStats } from "$lib/api";
  import { authConfigured, currentUser } from "$lib/auth";

  let authCfg = $state(false);
  let user = $state<{ username: string; role: string } | null>(null);
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
    const unsub1 = authConfigured.subscribe((v) => (authCfg = v));
    const unsub2 = currentUser.subscribe((v) => (user = v));
    getStats()
      .then((s) => (stats = s))
      .catch(() => {});
    return () => { unsub1(); unsub2(); };
  });
</script>

<svelte:head>
  <title>NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <div class="text-center mb-12 mt-4">
    <h1 class="text-4xl font-bold mb-3">NZ Gymnastics Results</h1>
    <p class="text-lg text-base-content/70 max-w-2xl mx-auto">
      Search, browse, and share New Zealand Artistic Gymnastics competition results.
    </p>
  </div>

  <div
    class="grid grid-cols-2 gap-4"
    class:md:grid-cols-4={!authCfg || user?.role !== "admin"}
    class:md:grid-cols-5={authCfg && user?.role === "admin"}
  >
    <a
      href="/events"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-1">📋</span>
        <h2 class="card-title text-base">Events</h2>
        <p class="text-xs text-base-content/70">Browse competitions by name, year, or discipline</p>
      </div>
    </a>
    <a
      href="/results"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-1">🏆</span>
        <h2 class="card-title text-base">Results</h2>
        <p class="text-xs text-base-content/70">View all scores across every event in one place</p>
      </div>
    </a>
    <a
      href="/gymnasts"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-1">🤸</span>
        <h2 class="card-title text-base">Gymnasts</h2>
        <p class="text-xs text-base-content/70">Look up gymnast profiles and history across events</p>
      </div>
    </a>
    <a
      href="/clubs"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-1">🏛️</span>
        <h2 class="card-title text-base">Clubs</h2>
        <p class="text-xs text-base-content/70">Explore clubs and their competition results</p>
      </div>
    </a>
    {#if authCfg && user?.role === "admin"}
      <a
        href="/upload"
        class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
      >
        <div class="card-body items-center text-center py-6">
          <span class="text-3xl mb-1">📄</span>
          <h2 class="card-title text-base">Upload</h2>
          <p class="text-xs text-base-content/70">Add a new Scoreholder JSON file</p>
        </div>
      </a>
    {/if}
  </div>

  {#if stats}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
      <a href="/events" class="stat bg-base-200 rounded-box hover:bg-base-300 transition-all cursor-pointer">
        <div class="stat-title text-base-content/60 text-xs">Events</div>
        <div class="stat-value text-2xl">{stats.total_events}</div>
      </a>
      <a href="/gymnasts" class="stat bg-base-200 rounded-box hover:bg-base-300 transition-all cursor-pointer">
        <div class="stat-title text-base-content/60 text-xs">Gymnasts</div>
        <div class="stat-value text-2xl">{stats.total_gymnasts.toLocaleString()}</div>
      </a>
      <a href="/results" class="stat bg-base-200 rounded-box hover:bg-base-300 transition-all cursor-pointer">
        <div class="stat-title text-base-content/60 text-xs">Scores</div>
        <div class="stat-value text-2xl">{stats.total_scores.toLocaleString()}</div>
      </a>
      <a href="/clubs" class="stat bg-base-200 rounded-box hover:bg-base-300 transition-all cursor-pointer">
        <div class="stat-title text-base-content/60 text-xs">Clubs</div>
        <div class="stat-value text-2xl">{stats.total_clubs}</div>
      </a>
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

  <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12 mb-8">
    <div class="card bg-base-200 border border-base-300">
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-2">🤸</span>
        <h3 class="card-title text-sm">WAG &amp; MAG</h3>
        <p class="text-xs text-base-content/70">
          Complete results for both disciplines with per-apparatus breakdowns, vault aggregation, and AA totals.
        </p>
      </div>
    </div>
    <div class="card bg-base-200 border border-base-300">
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-2">📥</span>
        <h3 class="card-title text-sm">Export &amp; Share</h3>
        <p class="text-xs text-base-content/70">
          Download CSV or XLSX with full per-pass vault detail, or share links to gymnast and club profile pages.
        </p>
      </div>
    </div>
    <div class="card bg-base-200 border border-base-300">
      <div class="card-body items-center text-center py-6">
        <span class="text-3xl mb-2">🔍</span>
        <h3 class="card-title text-sm">Smart Filtering</h3>
        <p class="text-xs text-base-content/70">
          Filter by year, level, club, region, division, or round type with column-header dropdowns.
        </p>
      </div>
    </div>
  </div>
</div>
