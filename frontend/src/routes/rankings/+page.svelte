<script lang="ts">
  import { onMount } from "svelte";

  let message = $state("Loading...");
  let loading = $state(true);

  onMount(async () => {
    try {
      const res = await fetch("/api/rankings");
      if (!res.ok) {
        message = "Unable to load rankings — you may not have access.";
        return;
      }
      const data = await res.json();
      message = data.message || "Rankings — coming soon";
    } catch {
      message = "Failed to load rankings.";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Rankings — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-4xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Rankings</h1>
  <p class="text-base-content/70 mb-6">Cross-event rankings and comparisons.</p>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else}
    <div class="card bg-base-200">
      <div class="card-body items-center text-center py-16">
        <span class="text-6xl mb-4">🏗️</span>
        <h2 class="card-title text-xl mb-2">{message}</h2>
        <p class="text-base-content/50 max-w-md">
          This page will show rankings aggregated across all uploaded events,
          including head-to-head comparisons and performance trends.
        </p>
      </div>
    </div>
  {/if}
</div>
