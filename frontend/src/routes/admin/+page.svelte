<script lang="ts">
  import { onMount } from "svelte";
  import { getStats } from "$lib/api";

  let stats = $state<{
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      stats = await getStats();
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Admin — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-4xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Admin Dashboard</h1>
  <p class="text-base-content/70 mb-6">Server overview and management.</p>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if error}
    <div role="alert" class="alert alert-error">
      <span>{error}</span>
    </div>
  {:else}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Events</div>
        <div class="stat-value text-2xl">{stats?.total_events ?? "—"}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Gymnasts</div>
        <div class="stat-value text-2xl">{(stats?.total_gymnasts ?? 0).toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Scores</div>
        <div class="stat-value text-2xl">{(stats?.total_scores ?? 0).toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box">
        <div class="stat-title text-base-content/60 text-xs">Clubs</div>
        <div class="stat-value text-2xl">{stats?.total_clubs ?? "—"}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <a href="/admin/users" class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer">
        <div class="card-body">
          <h2 class="card-title">👥 User Management</h2>
          <p class="text-sm text-base-content/70">Create, update, and delete user accounts</p>
        </div>
      </a>
      <a href="/upload" class="card bg-base-200 hover:bg-base-300 border border-base-300 transition-all cursor-pointer">
        <div class="card-body">
          <h2 class="card-title">📄 Upload Event</h2>
          <p class="text-sm text-base-content/70">Upload a Scoreholder JSON file</p>
        </div>
      </a>
    </div>
  {/if}
</div>
