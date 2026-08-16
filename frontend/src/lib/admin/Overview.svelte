<script lang="ts">
  import { onMount } from "svelte";
  import { getStats, getRebuildStatus } from "$lib/api";
  import type { RebuildStatus } from "$lib/api";
  import StatTile from "$lib/admin/StatTile.svelte";

  let {
    refreshToken = 0,
  }: {
    refreshToken?: number;
  } = $props();

  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);
  let rebuild = $state<RebuildStatus | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function loadStats() {
    try {
      stats = await getStats();
      error = null;
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }

  async function loadRebuild() {
    try {
      rebuild = await getRebuildStatus();
    } catch {
      rebuild = null;
    }
  }

  onMount(() => {
    loadStats();
    loadRebuild();
  });

  let prevToken = refreshToken;
  $effect(() => {
    if (refreshToken === prevToken) return;
    prevToken = refreshToken;
    loadStats();
    loadRebuild();
  });
</script>

{#if loading}
  <div class="flex justify-center py-10">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if error}
  <div role="alert" class="alert alert-error">
    <span>{error}</span>
  </div>
{:else}
  <div class="flex flex-wrap items-center gap-x-6 gap-y-4 bg-base-200/50 rounded-2xl p-4">
    <StatTile icon="event" label="Events" value={stats?.total_events != null ? stats.total_events.toLocaleString() : "—"} />
    <StatTile icon="groups" label="Gymnasts" value={(stats?.total_gymnasts ?? 0).toLocaleString()} />
    <StatTile icon="scoreboard" label="Scores" value={(stats?.total_scores ?? 0).toLocaleString()} />
    <StatTile icon="flag" label="Clubs" value={stats?.total_clubs != null ? stats.total_clubs.toLocaleString() : "—"} />
    {#if rebuild}
      <div class="w-full text-xs opacity-70 flex items-center gap-2">
        <span class="material-symbols-outlined" aria-hidden="true">bolt</span>
        <span>
          Prebuilt data:
          {#if rebuild.building}
            rebuilding…
          {:else if rebuild.needs_rebuild}
            <span class="text-warning">pending rebuild</span>
          {:else if rebuild.ready}
            ready{rebuild.last_rebuild_at ? ` · ${rebuild.last_rebuild_at}` : ""}
          {:else}
            not built
          {/if}
        </span>
      </div>
    {/if}
  </div>
{/if}
