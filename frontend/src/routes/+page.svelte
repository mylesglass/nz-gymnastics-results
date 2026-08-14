<script lang="ts">
  import { onMount } from "svelte";
  import { fly, fade } from "svelte/transition";
  import { page } from "$app/stores";
  import { getStats } from "$lib/api";
  import { currentUser, hasPermission, PERMISSIONS } from "$lib/auth";
  import Seo from "$lib/Seo.svelte";

  let {
    data,
  }: {
    data: {
      stats: {
        total_events: number;
        total_gymnasts: number;
        total_scores: number;
        total_clubs: number;
      } | null;
    };
  } = $props();

  let stats = $state(data.stats);
  let patchNotes = $state<{ date: string; entries: { title: string; items: string[] }[] }[]>([]);
  let motion = $state(true);
  let user = $state<{ username: string; role: string; permissions: string[] } | null>(null);

  let homeDescription = $derived(
    stats
      ? `Browse ${stats.total_events.toLocaleString()} events, ${stats.total_gymnasts.toLocaleString()} gymnast profiles, ${stats.total_clubs.toLocaleString()} clubs, and ${stats.total_scores.toLocaleString()} scores from New Zealand gymnastics competitions.`
      : "Search, browse, and share New Zealand Artistic Gymnastics competition results."
  );

  let canRankings = $derived(
    user && (hasPermission(user, PERMISSIONS.national) || hasPermission(user, PERMISSIONS.wellington))
  );

  function reveal(
    node: Element,
    params: { delay?: number; dist?: number } = {}
  ): ReturnType<typeof fly> {
    if (!motion) return fade(node, { duration: 0 });
    return fly(node, { y: params.dist ?? 12, duration: 400, delay: params.delay ?? 0 });
  }

  onMount(() => {
    const unsub = currentUser.subscribe((v) => (user = v));
    motion = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    getStats()
      .then((s) => (stats = s))
      .catch(() => {});
    if (user) {
      fetch("/patch_notes.json")
        .then((r) => (r.ok ? r.json() : []))
        .then((list: { date: string; entries: { title: string; items: string[] }[] }[]) => {
          patchNotes = list ?? [];
        })
        .catch(() => {});
    }
    return () => unsub();
  });
</script>

<Seo
  title="NZ Gymnastics Results"
  path="/"
  origin={$page.url.origin}
  description={homeDescription}
  jsonLd={{
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "NZ Gymnastics Results",
    url: `${$page.url.origin}/`,
    description: "Search, browse, and share New Zealand Artistic Gymnastics competition results.",
    inLanguage: "en",
  }}
/>

<div class="max-w-6xl mx-auto">
  <div in:reveal={{ dist: -10, delay: 0 }} class="text-center mb-12 mt-4">
    <h1 class="text-4xl font-bold mb-3">NZ Gymnastics Results <span class="badge badge-warning align-middle">Beta</span></h1>
    <p class="text-lg text-base-content/70 max-w-2xl mx-auto">
      Search, browse, and share New Zealand Artistic Gymnastics competition results.
    </p>
  </div>

  <div in:reveal={{ delay: 50 }} class="alert alert-warning max-w-2xl mx-auto mb-4" role="status">
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="shrink-0 w-6 h-6" aria-hidden="true">
      <path fill="currentColor" d="M2.725 21q-.275 0-.5-.137t-.35-.363t-.137-.488t.137-.512l9.25-16q.15-.25.388-.375T12 3t.488.125t.387.375l9.25 16q.15.25.138.513t-.138.487t-.35.363t-.5.137zm1.725-2h15.1L12 6zm8.263-1.287Q13 17.425 13 17t-.288-.712T12 16t-.712.288T11 17t.288.713T12 18t.713-.288m0-3Q13 14.425 13 14v-3q0-.425-.288-.712T12 10t-.712.288T11 11v3q0 .425.288.713T12 15t.713-.288M12 12.5"></path>
    </svg>
    <span>
      This site is in beta. Results are provided as-is and may contain errors or inaccuracies.
    </span>
  </div>

  <div in:reveal={{ delay: 70 }} class="alert alert-info max-w-2xl mx-auto mb-12" role="status">
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="shrink-0 w-6 h-6" aria-hidden="true">
      <path fill="currentColor" d="M12.713 16.713Q13 16.425 13 16v-4q0-.425-.288-.712T12 11t-.712.288T11 12v4q0 .425.288.713T12 17t.713-.288m0-8Q13 8.425 13 8t-.288-.712T12 7t-.712.288T11 8t.288.713T12 9t.713-.288M12 22q-2.075 0-3.9-.788t-3.175-2.137T2.788 15.9T2 12t.788-3.9t2.137-3.175T8.1 2.788T12 2t3.9.788t3.175 2.137T21.213 8.1T22 12t-.788 3.9t-2.137 3.175t-3.175 2.138T12 22m0-2q3.35 0 5.675-2.325T20 12t-2.325-5.675T12 4T6.325 6.325T4 12t2.325 5.675T12 20m0-8"></path>
    </svg>
    <span>
      This is an unofficial community-built project and is not affiliated with or endorsed by Gymnastics New Zealand.
    </span>
  </div>

  <div in:reveal={{ delay: 100 }} class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
    <div class="text-center">
      <span class="text-2xl mb-1 block" aria-hidden="true">🤸</span>
      <p class="font-semibold text-sm">WAG &amp; MAG</p>
      <p class="text-xs text-base-content/70">
        Complete results for both disciplines with per-apparatus breakdowns, vault aggregation, and AA totals.
      </p>
    </div>
    <div class="text-center">
      <span class="text-2xl mb-1 block" aria-hidden="true">📥</span>
      <p class="font-semibold text-sm">Export &amp; Share</p>
      <p class="text-xs text-base-content/70">
        Download CSV, XLSX, or PDF with one click, or share links to gymnast and club profile pages.
      </p>
    </div>
    <div class="text-center">
      <span class="text-2xl mb-1 block" aria-hidden="true">🔍</span>
      <p class="font-semibold text-sm">Smart Filtering</p>
      <p class="text-xs text-base-content/70">
        Filter by year, level, club, region, division, or round type.
      </p>
    </div>
  </div>

  <div
    in:reveal={{ dist: 14, delay: 200 }}
    class="grid grid-cols-2 gap-4 mb-8 {canRankings ? 'md:grid-cols-5' : 'md:grid-cols-4'}"
  >
    <a
      href="/events"
      class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div class="card-body items-center text-center py-6">
        {#if stats}
          <span class="badge badge-primary badge-sm absolute top-3 right-3">{stats.total_events}</span>
        {/if}
        <span class="text-3xl mb-1" aria-hidden="true">📋</span>
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
        <span class="text-3xl mb-1" aria-hidden="true">🏆</span>
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
        <span class="text-3xl mb-1" aria-hidden="true">🤸</span>
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
        <span class="text-3xl mb-1" aria-hidden="true">🏛️</span>
        <h2 class="card-title text-base">Clubs</h2>
        <p class="text-xs text-base-content/70">Explore clubs and their competition results</p>
      </div>
    </a>
    {#if canRankings}
      <a
        href={hasPermission(user, PERMISSIONS.national) ? "/rankings" : "/wellington-ranking"}
        class="card bg-base-200 hover:bg-base-300 border border-base-300 hover:border-base-content/20 hover:-translate-y-1 hover:shadow-lg transition-all cursor-pointer group"
      >
        <div class="card-body items-center text-center py-6">
          <span class="text-3xl mb-1" aria-hidden="true">🏅</span>
          <h2 class="card-title text-base">Rankings</h2>
          <p class="text-xs text-base-content/70">National and apparatus rankings by level</p>
        </div>
      </a>
    {/if}
  </div>

  {#if user}
    <div in:reveal={{ delay: 300 }} class="card bg-base-200 border border-base-300 mt-12 mb-8">
      <div class="card-body p-6">
        <h2 class="text-xl font-bold mb-5">What's new</h2>
        {#if patchNotes.length}
          <div class="space-y-5 max-h-96 overflow-y-auto pr-2 -mr-2" tabindex="0" role="region" aria-label="Patch notes">
            {#each patchNotes as group}
              <div>
                <h3 class="text-sm font-semibold text-base-content mb-2">{group.date}</h3>
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
          <p class="text-xs text-base-content/70">Patch notes unavailable.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>
