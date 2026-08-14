<script lang="ts">
  import { fade } from "svelte/transition";
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { listClubs } from "$lib/api";
  import NZRegionMap from "$lib/NZRegionMap.svelte";
  import { REGION_PALETTES, REGION_ORDER, gradientBackground, gradientTextColor, headingColor, textColor } from "$lib/regions";
  import Seo from "$lib/Seo.svelte";
  import type { ClubData } from "./+page.server";

  type Club = { name: string; gymnast_count: number; region: string | null; is_region: boolean };

  let {
    data,
  }: {
    data: { clubs: ClubData[] };
  } = $props();

  let clubs = $state<Club[]>(data.clubs);
  let loading = $state(data.clubs.length === 0);
  let active = $state<string | null>(null);

  let clubsDescription = $derived(
    data.clubs.length
      ? `Explore ${data.clubs.length} New Zealand gymnastics clubs by region — results, gymnast counts, and competition history.`
      : "Explore New Zealand gymnastics clubs by region."
  );

  onMount(() => {
    listClubs()
      .then((c) => (clubs = c))
      .catch(() => {})
      .finally(() => (loading = false));
  });

  let grouped = $derived.by(() => {
    const g: Record<string, typeof clubs> = {};
    for (const c of clubs) {
      const key = c.region || "Other";
      if (!g[key]) g[key] = [];
      g[key].push(c);
    }
    const rank = new Map(REGION_ORDER.map((r, i) => [r, i]));
    const sorted: Record<string, typeof clubs> = {};
    for (const k of Object.keys(g).sort((a, b) => {
      if (a === "Other") return 1;
      if (b === "Other") return -1;
      const ra = rank.get(a) ?? Number.MAX_SAFE_INTEGER;
      const rb = rank.get(b) ?? Number.MAX_SAFE_INTEGER;
      return ra - rb || a.localeCompare(b);
    })) {
      sorted[k] = g[k];
    }
    return sorted;
  });

  let REGIONS = $derived(Object.keys(grouped).filter((r) => r !== "Other"));

  function provTeam(regionClubs: typeof clubs) {
    return regionClubs.find((c) => c.is_region);
  }

  function slug(name: string): string {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  function selectRegion(name: string) {
    if (active === name) {
      active = null;
      return;
    }
    active = name;
  }

  let mobileOpen = $state<string | null>(null);

  function toggleMobile(name: string) {
    mobileOpen = mobileOpen === name ? null : name;
  }

  let desktopCardEl: HTMLElement | undefined = $state();

  $effect(() => {
    if (active && desktopCardEl) {
      desktopCardEl.focus({ preventScroll: true });
    }
  });
</script>

<Seo
  title="Clubs"
  path="/clubs"
  origin={$page.url.origin}
  description={clubsDescription}
/>

<div class="max-w-7xl mx-auto px-4">
  {#if loading}    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each [1, 2, 3, 4, 5, 6] as _}
        <div class="card bg-base-200 animate-pulse">
          <div class="card-body">
            <div class="h-4 bg-base-300 rounded w-3/4 mb-2"></div>
            <div class="h-3 bg-base-300 rounded w-1/2"></div>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8 lg:items-start">
      <!-- Map on the left -->
      <div class="card bg-base-200/60 border border-base-300 shadow-lg overflow-hidden w-full hidden lg:block lg:sticky lg:top-4">
        <div class="card-body p-6">
          <div class="overflow-hidden rounded-box" style="aspect-ratio: 525 / 692.3">
            <NZRegionMap {active} onSelect={selectRegion} />
          </div>
          <p class="text-center text-xs text-base-content/70 mt-3" role="status" aria-live="polite">
            {active ? `Showing ${active} — click again to clear` : "Click a region on the map to see its clubs"}
          </p>
        </div>
      </div>

      <!-- Region box on the right -->
      <div class="mt-6 lg:mt-0 hidden lg:block" role="status" aria-live="polite">
        {#if active && grouped[active]?.length}
          {#key active}
            <div in:fade={{ duration: 250 }}>
              <div tabindex="-1" bind:this={desktopCardEl} class="outline-none">
                {@render RegionCard({ region: active, regionClubs: grouped[active], oncardclick: selectRegion })}
              </div>
            </div>
          {/key}
        {:else}
          <div class="card bg-base-200 border border-base-300">
            <div class="card-body items-center text-center text-base-content/70 py-16">
              <p class="text-sm">Select a region on the map</p>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <!-- Mobile region list -->
    <div class="lg:hidden mt-4 mb-8">
      <div class="flex items-baseline gap-2 mb-3">
        <h2 class="text-xl font-bold">Regions</h2>
        <span class="text-xs text-base-content/70">Tap a region to expand its clubs</span>
      </div>
      <div class="space-y-3">
        {#each REGIONS as region}
          {@render RegionCard({ region, regionClubs: grouped[region], expandable: true, open: mobileOpen === region, oncardclick: toggleMobile })}
        {/each}
      </div>
    </div>

    <!-- Other -->
    {#if (grouped["Other"] ?? []).length}
      {@const otherClubs = grouped["Other"]}
      <div class="mt-8 mb-8">
        <div class="flex items-center gap-2 mb-3">
          <h2 class="text-2xl font-bold">Other</h2>
          <span class="text-xs text-base-content/70">({otherClubs.length} club(s))</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {#each otherClubs as club}
            <a
              href="/club/{encodeURIComponent(club.name)}"
              class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
            >
              <div class="card-body py-3 px-4 flex-row items-center justify-between gap-2">
                <span class="font-medium text-sm truncate">{club.name}</span>
                <span class="flex items-center gap-2 shrink-0">
                  <span class="text-xs text-base-content/70">{club.gymnast_count} gymnasts</span>
                </span>
              </div>
            </a>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>

{#snippet RegionCard({ region, regionClubs, expandable = false, open = true, oncardclick }: { region: string; regionClubs: typeof clubs; expandable?: boolean; open?: boolean; oncardclick: (r: string) => void })}
  {@const team = provTeam(regionClubs)}
  {@const palette = REGION_PALETTES[region] ?? []}
  {@const bg = gradientBackground(palette)}
  {@const fg = gradientTextColor(palette)}
  {@const headingCol = headingColor(palette)}
  {@const regionColor = palette[0] ?? fg}
  {@const hoverBg = `color-mix(in srgb, ${regionColor} 25%, transparent)`}
  {@const pillBg = fg === "#fff" ? "rgba(0,0,0,0.35)" : "rgba(255,255,255,0.5)"}
  {@const pillBorder = fg === "#fff" ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.15)"}
  <div
    id="region-{slug(region)}"
    class="card rounded-box overflow-hidden transition-shadow"
    style="background: {bg}; color: {fg};"
  >
    <div
      class="card-body p-5"
      role={expandable ? "button" : undefined}
      tabindex={expandable ? 0 : undefined}
      aria-expanded={expandable ? open : undefined}
      aria-controls={expandable ? `region-panel-${slug(region)}` : undefined}
      onclick={expandable ? () => oncardclick(region) : undefined}
      onkeydown={expandable ? (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          oncardclick(region);
        }
      } : undefined}
    >
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="text-2xl font-bold leading-tight" style="color: {headingCol}">{region}</h3>
          </div>
          <p class="text-sm opacity-80" style="color: {headingCol}">{regionClubs.filter((c) => !c.is_region).length} club(s)</p>
        </div>
        {#if team}
          <a
            href="/club/{encodeURIComponent(team.name)}"
            class="card backdrop-blur-sm border transition-colors cursor-pointer"
            style="--bg: {pillBg}; --hover-bg: {hoverBg}; border-color: {pillBorder};"
          >
            <div class="card-body py-2 px-3 flex-row items-center gap-2">
              <span class="text-left">
                <span class="block font-semibold text-xs" style="color: {fg}">{team.name}</span>
                <span class="block text-[10px] opacity-80" style="color: {fg}">{team.gymnast_count} gymnasts</span>
              </span>
              <span
                class="badge badge-sm ml-1 shrink-0 font-semibold"
                style="background: {palette[0] ?? fg}; color: {textColor(palette[0] ?? fg)};"
                >Provincial Team</span
              >
            </div>
          </a>
        {/if}
        {#if expandable}
          <span
            class="transition-transform duration-200 shrink-0"
            class:rotate-180={open}
            aria-hidden="true"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="fill-current">
              <path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
            </svg>
          </span>
        {/if}
      </div>
      {#if open}
        <div id="region-panel-{slug(region)}" class="grid grid-cols-1 gap-2">
          {#each regionClubs.filter((c) => !c.is_region) as club}
            <a
              href="/club/{encodeURIComponent(club.name)}"
              class="card backdrop-blur-sm border transition-colors cursor-pointer"
              style="--bg: {pillBg}; --hover-bg: {hoverBg}; border-color: {pillBorder}; color: {fg};"
            >
              <div class="card-body py-2 px-3 flex-row items-center justify-between gap-2">
                <span class="font-medium text-sm truncate" style="color: {fg}">{club.name}</span>
                <span class="flex items-center gap-2 shrink-0">
                  <span class="text-xs opacity-70">{club.gymnast_count} gymnasts</span>
                </span>
              </div>
            </a>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/snippet}

<style>
  .card[style*="--hover-bg"] {
    background: var(--bg);
  }
  .card[style*="--hover-bg"]:hover {
    background: var(--hover-bg);
  }
</style>
