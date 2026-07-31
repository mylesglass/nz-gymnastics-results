<script lang="ts">
  import { onMount } from "svelte";
  import { listClubs } from "$lib/api";
  import NZRegionMap from "$lib/NZRegionMap.svelte";
  import { REGION_PALETTES, gradientBackground, gradientTextColor, textColor } from "$lib/regions";

  let clubs = $state<{ name: string; gymnast_count: number; region: string | null; is_region: boolean }[]>([]);
  let loading = $state(true);
  let active = $state<string | null>(null);

  onMount(async () => {
    try {
      clubs = await listClubs();
    } catch {
      // ignore
    } finally {
      loading = false;
    }
  });

  let grouped = $derived.by(() => {
    const g: Record<string, typeof clubs> = {};
    for (const c of clubs) {
      const key = c.region || "Other";
      if (!g[key]) g[key] = [];
      g[key].push(c);
    }
    const sorted: Record<string, typeof clubs> = {};
    for (const k of Object.keys(g).sort((a, b) => (a === "Other" ? 1 : b === "Other" ? -1 : a.localeCompare(b)))) {
      sorted[k] = g[k];
    }
    return sorted;
  });

  const REGIONS = Object.keys(grouped).filter((r) => r !== "Other");

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
</script>

<svelte:head>
  <title>Clubs — NZ Gymnastics Results</title>
</svelte:head>

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
      <div class="card bg-base-200/60 border border-base-300 shadow-lg overflow-hidden w-full lg:sticky lg:top-4">
        <div class="card-body p-6">
          <NZRegionMap {active} onSelect={selectRegion} />
          <p class="text-center text-xs text-base-content/60 mt-3">
            {active ? `Showing ${active} — click again to clear` : "Click a region on the map to see its clubs"}
          </p>
        </div>
      </div>

      <!-- Region box on the right -->
      <div class="mt-6 lg:mt-0">
        {#if active && grouped[active]?.length}
          {@const regionClubs = grouped[active]}
          {@render RegionBox({ region: active, regionClubs, active, onselect: selectRegion })}
        {:else}
          <div class="card bg-base-200 border border-base-300">
            <div class="card-body items-center text-center text-base-content/50 py-16">
              <p class="text-sm">Select a region on the map</p>
            </div>
          </div>
        {/if}

        <!-- Other -->
        {#if (grouped["Other"] ?? []).length}
          {@const otherClubs = grouped["Other"]}
          <div class="mt-6">
            <div class="flex items-center gap-2 mb-3">
              <h2 class="text-2xl font-bold">Other</h2>
              <span class="text-xs text-base-content/50">({otherClubs.length} club(s))</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {#each otherClubs as club}
                <a
                  href="/club/{encodeURIComponent(club.name)}"
                  class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
                >
                  <div class="card-body py-3 px-4 flex-row items-center justify-between">
                    <span class="font-medium text-sm">{club.name}</span>
                    <span class="text-xs text-base-content/50">{club.gymnast_count} gymnasts</span>
                  </div>
                </a>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

{#snippet RegionBox({ region, regionClubs, active, onselect }: { region: string; regionClubs: typeof clubs; active: string | null; onselect: (r: string) => void })}
  {@const team = provTeam(regionClubs)}
  {@const palette = REGION_PALETTES[region] ?? []}
  {@const bg = gradientBackground(palette)}
  {@const fg = gradientTextColor(palette)}
  {@const headingColor = palette[1] ?? fg}
  {@const pillBg = fg === "#fff" ? "rgba(0,0,0,0.35)" : "rgba(255,255,255,0.5)"}
  {@const pillBorder = fg === "#fff" ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.15)"}
  {@const isActive = active === region}
  <div
    id="region-{slug(region)}"
    class="card rounded-box overflow-hidden transition-shadow cursor-pointer"
    role="button"
    tabindex="0"
    style="background: {bg}; color: {fg}; box-shadow: {isActive ? '0 0 0 3px rgba(255,255,255,0.6)' : 'none'};"
    onclick={() => onselect(region)}
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") onselect(region);
    }}
  >
    <div class="card-body p-5">
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <div class="flex-1 min-w-0">
          <h3 class="text-2xl font-bold leading-tight" style="color: {headingColor}">{region}</h3>
          <p class="text-sm opacity-80" style="color: {headingColor}">{regionClubs.filter((c) => !c.is_region).length} club(s)</p>
        </div>
        {#if team}
          <a
            href="/club/{encodeURIComponent(team.name)}"
            class="card hover:scale-[1.02] backdrop-blur-sm border transition-all cursor-pointer"
            style="background: {pillBg}; border-color: {pillBorder};"
            onclick={(e) => e.stopPropagation()}
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
      </div>
      <div class="grid grid-cols-1 gap-2">
        {#each regionClubs.filter((c) => !c.is_region) as club}
          <a
            href="/club/{encodeURIComponent(club.name)}"
            class="card hover:scale-[1.02] backdrop-blur-sm border transition-all cursor-pointer"
            style="background: {pillBg}; border-color: {pillBorder}; color: {fg};"
          >
            <div class="card-body py-2 px-3 flex-row items-center justify-between">
              <span class="font-medium text-sm" style="color: {fg}">{club.name}</span>
              <span class="text-xs opacity-70">{club.gymnast_count} gymnasts</span>
            </div>
          </a>
        {/each}
      </div>
    </div>
  </div>
{/snippet}
