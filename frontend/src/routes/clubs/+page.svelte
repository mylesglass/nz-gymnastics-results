<script lang="ts">
  import { onMount } from "svelte";
  import { listClubs } from "$lib/api";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_PALETTES } from "$lib/regions";

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
</script>

<svelte:head>
  <title>Clubs — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Clubs</h1>
  <p class="text-base-content/70 mb-6">
    {clubs.length} clubs across New Zealand
  </p>

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
      <div class="mb-8">
          <div class="flex items-center gap-2 mb-3">
            <RegionBadge region={region} colors={REGION_PALETTES[region] ?? []} />
            <span class="text-xs text-base-content/50">({regionClubs.length})</span>
          </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {#each regionClubs as club}
            <a
              href="/club/{encodeURIComponent(club.name)}"
              class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer"
            >
              <div class="card-body py-3 px-4 flex-row items-center justify-between">
                <span class="font-medium text-sm">
                  {club.name}
                  {#if club.is_region}
                    <span class="badge badge-ghost badge-xs ml-1">Provincial Team</span>
                  {/if}
                </span>
                <span class="text-xs text-base-content/50">{club.gymnast_count} gymnasts</span>
              </div>
            </a>
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
