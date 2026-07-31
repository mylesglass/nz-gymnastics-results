<script lang="ts">
  import { onMount } from "svelte";
  import { listClubs } from "$lib/api";
  import { REGION_PALETTES, gradientBackground, gradientTextColor, textColor } from "$lib/regions";

  let clubs = $state<{ name: string; gymnast_count: number; region: string | null; is_region: boolean }[]>([]);
  let loading = $state(true);

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
    // Sort regions — "Other" last
    const sorted: Record<string, typeof clubs> = {};
    for (const k of Object.keys(g).sort((a, b) => (a === "Other" ? 1 : b === "Other" ? -1 : a.localeCompare(b)))) {
      sorted[k] = g[k];
    }
    return sorted;
  });

  function provTeam(regionClubs: typeof clubs) {
    return regionClubs.find((c) => c.is_region);
  }
</script>

<svelte:head>
  <title>Clubs — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  {#if loading}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
    {#each Object.entries(grouped) as [region, regionClubs]}
      {@const team = provTeam(regionClubs)}
      {@const palette = REGION_PALETTES[region] ?? []}
      {@const isOther = region === "Other"}
      {@const bg = gradientBackground(palette)}
      {@const fg = gradientTextColor(palette)}
      {@const pillBg = fg === "#fff" ? "rgba(0,0,0,0.35)" : "rgba(255,255,255,0.5)"}
      {@const pillBorder = fg === "#fff" ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.15)"}
      {@const headingColor = palette[1] ?? fg}
      {#if isOther}
        <div class="mb-8">
          <div class="flex items-center gap-2 mb-3">
            <h2 class="text-2xl font-bold">{region}</h2>
            <span class="text-xs text-base-content/50">({regionClubs.length} club(s))</span>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {#each regionClubs as club}
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
      {:else}
        <div class="mb-8">
          <div
            class="card rounded-box overflow-hidden"
            style="background: {bg}; color: {fg};"
          >
            <div class="card-body p-6 md:p-8">
              <div class="flex flex-wrap items-center gap-4 mb-6">
                <div class="flex-1">
                  <h2 class="text-3xl md:text-4xl font-bold" style="color: {headingColor}">{region}</h2>
                  <p class="mt-1 opacity-80" style="color: {headingColor}">{regionClubs.filter((c) => !c.is_region).length} club(s)</p>
                </div>
                {#if team}
                  <a
                    href="/club/{encodeURIComponent(team.name)}"
                    class="card hover:scale-[1.02] backdrop-blur-sm border transition-all cursor-pointer"
                    style="background: {pillBg}; border-color: {pillBorder};"
                  >
                    <div class="card-body py-3 px-4 flex-row items-center gap-3">
                      <span class="text-left">
                        <span class="block font-semibold text-sm" style="color: {fg}">{team.name}</span>
                        <span class="block text-xs" style="color: {fg}">{team.gymnast_count} gymnasts</span>
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
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {#each regionClubs.filter((c) => !c.is_region) as club}
                  <a
                    href="/club/{encodeURIComponent(club.name)}"
                    class="card hover:scale-[1.02] backdrop-blur-sm border transition-all cursor-pointer"
                    style="background: {pillBg}; border-color: {pillBorder}; color: {fg};"
                  >
                    <div class="card-body py-3 px-4 flex-row items-center justify-between">
                      <span class="font-medium text-sm" style="color: {fg}">{club.name}</span>
                      <span class="text-xs opacity-70">{club.gymnast_count} gymnasts</span>
                    </div>
                  </a>
                {/each}
              </div>
            </div>
          </div>
        </div>
      {/if}
    {/each}
  {/if}
</div>
