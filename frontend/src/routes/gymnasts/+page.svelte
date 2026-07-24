<script lang="ts">
  import { onMount } from "svelte";
  import { listGymnasts } from "$lib/api";

  interface Gymnast {
    gnz_id: string;
    name: string;
    club: string | null;
    alt_ids: string[];
    alt_clubs: string[];
  }

  let gymnasts = $state<Gymnast[]>([]);
  let loading = $state(true);
  let search = $state("");

  let filtered = $derived(
    search
      ? gymnasts.filter(g => g.name.toLowerCase().includes(search.toLowerCase()))
      : gymnasts
  );

  onMount(async () => {
    try {
      gymnasts = await listGymnasts();
    } catch {
      // ignore
    } finally {
      loading = false;
    }
  });

  let grouped = $derived.by(() => {
    const g: Record<string, Gymnast[]> = {};
    for (const gr of filtered) {
      const letter = gr.name.charAt(0).toUpperCase();
      if (!/[A-Z]/.test(letter)) continue;
      if (!g[letter]) g[letter] = [];
      g[letter].push(gr);
    }
    const sorted: Record<string, Gymnast[]> = {};
    for (const k of Object.keys(g).sort()) {
      sorted[k] = g[k];
    }
    return sorted;
  });

  function displayIds(gr: Gymnast): string {
    const all = [gr.gnz_id, ...gr.alt_ids];
    return all.join(", ");
  }

  function displayClubs(gr: Gymnast): string {
    const all: string[] = [];
    if (gr.club) all.push(gr.club);
    all.push(...gr.alt_clubs);
    return all.join(", ");
  }
</script>

<svelte:head>
  <title>Gymnasts — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <div class="flex items-end justify-between mb-6 gap-4">
    <div>
      <h1 class="text-3xl font-bold">Gymnasts</h1>
      <p class="text-base-content/70 text-sm">
        {filtered.length} gymnast{filtered.length === 1 ? "" : "s"}
        {#if search}(filtered){/if}
      </p>
    </div>
    <input
      type="text"
      placeholder="Search gymnasts..."
      class="input input-bordered input-sm w-56"
      bind:value={search}
    />
  </div>

  {#if loading}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
    {#each Object.entries(grouped) as [letter, letterGymnasts]}
      <div class="mb-6">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-lg font-bold">{letter}</span>
          <span class="text-xs text-base-content/50">({letterGymnasts.length})</span>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-1">
          {#each letterGymnasts as gr}
            <a
              href="/gymnast/{gr.gnz_id}"
              class="flex items-center px-3 py-1.5 rounded hover:bg-base-200 transition-colors gap-1"
            >
              <span class="text-sm">{gr.name}</span>
              {#if gr.alt_ids.length > 0}
                <span class="text-warning text-xs">⚠</span>
              {/if}
              <span class="text-xs text-base-content/40">{displayIds(gr)}</span>
              <span class="ml-auto flex items-center gap-1 shrink-0">
                {#if gr.alt_clubs.length > 0}
                  <span class="text-xs text-base-content/40">{displayClubs(gr)}</span>
                {:else if gr.club}
                  <span class="text-xs text-base-content/50">{gr.club}</span>
                {/if}
              </span>
            </a>
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
