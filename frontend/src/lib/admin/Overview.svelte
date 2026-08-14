<script lang="ts">
  import { onMount } from "svelte";
  import { getStats } from "$lib/api";
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

  onMount(loadStats);

  let prevToken = refreshToken;
  $effect(() => {
    if (refreshToken === prevToken) return;
    prevToken = refreshToken;
    loadStats();
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
  <div class="flex flex-wrap gap-3">
    <StatTile icon="event" label="Events" value={stats?.total_events != null ? stats.total_events.toLocaleString() : "—"} />
    <StatTile icon="groups" label="Gymnasts" value={(stats?.total_gymnasts ?? 0).toLocaleString()} />
    <StatTile icon="scoreboard" label="Scores" value={(stats?.total_scores ?? 0).toLocaleString()} />
    <StatTile icon="flag" label="Clubs" value={stats?.total_clubs != null ? stats.total_clubs.toLocaleString() : "—"} />
  </div>
{/if}
