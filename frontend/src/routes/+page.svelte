<script lang="ts">
  import { onMount } from "svelte";
  import { fly, fade } from "svelte/transition";
  import { getStats } from "$lib/api";

  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);
  let patchNotes = $state<{ date: string; entries: { title: string; items: string[] }[] }[]>([]);
  let motion = $state(true);

  onMount(() => {
    motion = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    getStats()
      .then((s) => (stats = s))
      .catch(() => {});
    fetch("/patch_notes.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((list: { date: string; entries: { title: string; items: string[] }[] }[]) => {
        patchNotes = list ?? [];
      })
      .catch(() => {});
  });

  function reveal(
    node: Element,
    params: { delay?: number; dist?: number } = {}
  ): ReturnType<typeof fly> {
    if (!motion) return fade(node, { duration: 0 });
    return fly(node, { y: params.dist ?? 12, duration: 400, delay: params.delay ?? 0 });
  }
</script>

<svelte:head>
  <title>NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <div in:fly={{ y: -10, duration: 450 }} class="text-center mb-12 mt-4">
    <h1 class="text-4xl font-bold mb-3">NZ Gymnastics Results</h1>
    <p class="text-lg text-base-content/70 max-w-2xl mx-auto">
      Search, browse, and share New Zealand Artistic Gymnastics competition results.
    </p>
  </div>

  <div in:reveal={{ delay: 100 }} class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
    <div class="text-center">
      <span class="text-2xl mb-1 block">🤸</span>
      <h3 class="font-semibold text-sm">WAG &amp; MAG</h3>
      <p class="text-xs text-base-content/70">
        Complete results for both disciplines with per-apparatus breakdowns, vault aggregation, and AA totals.
      </p>
    </div>
    <div class="text-center">
      <span class="text-2xl mb-1 block">📥</span>
      <h3 class="font-semibold text-sm">Export &amp; Share</h3>
      <p class="text-xs text-base-content/70">
        Download CSV, XLSX, or PDF with one click, or share links to gymnast and club profile pages.
      </p>
    </div>
    <div class="text-center">
      <span class="text-2xl mb-1 block">🔍</span>
      <h3 class="font-semibold text-sm">Smart Filtering</h3>
      <p class="text-xs text-base-content/70">
        Filter by year, level, club, region, division, or round type with column-header dropdowns.
      </p>
    </div>
  </div>

  <div in:fly={{ y: 14, duration: 450, delay: 200 }} class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
    <a
      href="/events"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div class="card-body items-center text-center py-6">
        {#if stats}
          <span class="badge badge-primary badge-sm absolute top-3 right-3">{stats.total_events}</span>
        {/if}
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
        {#if stats}
          <span class="badge badge-accent badge-sm absolute top-3 right-3">{stats.total_scores.toLocaleString()}</span>
        {/if}
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
        {#if stats}
          <span class="badge badge-secondary badge-sm absolute top-3 right-3">{stats.total_gymnasts.toLocaleString()}</span>
        {/if}
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
        {#if stats}
          <span class="badge badge-info badge-sm absolute top-3 right-3">{stats.total_clubs}</span>
        {/if}
        <span class="text-3xl mb-1">🏛️</span>
        <h2 class="card-title text-base">Clubs</h2>
        <p class="text-xs text-base-content/70">Explore clubs and their competition results</p>
      </div>
    </a>
  </div>

  <div in:reveal={{ delay: 300 }} class="card bg-base-200 border border-base-300 mt-12 mb-8">
    <div class="card-body p-6">
      <h2 class="text-xl font-bold mb-5">What's new</h2>
      {#if patchNotes.length}
        <div class="space-y-5 max-h-96 overflow-y-auto pr-2 -mr-2">
          {#each patchNotes as group}
            <div>
              <h3 class="text-sm font-semibold text-primary mb-2">{group.date}</h3>
              <ul class="space-y-3 text-sm text-base-content/80">
                {#each group.entries as entry}
                  <li class="border-l-2 border-base-300 pl-4">
                    <p class="font-medium text-base-content">{entry.title}</p>
                    <ul class="text-xs text-base-content/70 space-y-1 list-disc list-inside mt-1">
                      {#each entry.items as item}
                        <li>{item}</li>
                      {/each}
                    </ul>
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      {:else}
        <p class="text-xs text-base-content/50">Patch notes unavailable.</p>
      {/if}
    </div>
  </div>
</div>
