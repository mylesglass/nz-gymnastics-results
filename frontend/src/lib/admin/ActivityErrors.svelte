<script lang="ts">
  import { onMount } from "svelte";
  import { getActivityLogs } from "$lib/api";
  import type { ActivityLogItem } from "$lib/api";

  const PAGE_SIZE = 100;

  let {
    days,
    onClose,
  }: {
    days: number;
    onClose: () => void;
  } = $props();

  let items = $state<ActivityLogItem[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let offset = $state(0);

  async function load() {
    loading = true;
    error = null;
    try {
      const data = await getActivityLogs({
        errors: true,
        limit: PAGE_SIZE,
        offset,
        days: days || undefined,
      });
      items = data.items;
      total = data.total;
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }

  function pageNext() {
    if (offset + PAGE_SIZE >= total) return;
    offset += PAGE_SIZE;
    load();
  }

  function pagePrev() {
    if (offset === 0) return;
    offset = Math.max(0, offset - PAGE_SIZE);
    load();
  }

  function fmtTime(iso: string): string {
    return new Date(iso).toLocaleString();
  }

  onMount(load);
</script>

<p class="text-sm text-base-content/70 mb-4">
  API requests that returned an error status (4xx/5xx) from logged-in users in the selected range. Anonymous errors (bot probes, etc.) are counted in the tile but don't appear here.
</p>

{#if error}
  <div role="alert" class="alert alert-error mb-4">
    <span>{error}</span>
  </div>
{:else if loading && items.length === 0}
  <div class="flex justify-center py-10">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if items.length === 0}
  <div class="text-center py-10">
    <span class="material-symbols-outlined text-success text-3xl" aria-hidden="true">check_circle</span>
    <p class="text-sm text-base-content/70 mt-2">No errors recorded in this range.</p>
  </div>
{:else}
  <div class="max-h-96 overflow-y-auto space-y-2 pr-1" role="list">
    {#each items as item}
      <div class="border border-base-300 rounded-lg p-3 text-xs bg-base-100">
        <div class="flex items-center justify-between gap-2">
          <span class="font-medium">
            {item.username}
            <span class="badge badge-ghost badge-xs ml-1">{item.role}</span>
          </span>
          <span class="badge badge-error badge-xs">HTTP {item.status_code ?? "—"}</span>
        </div>
        <div class="text-base-content/70 mt-1">{fmtTime(item.created_at)}</div>
        <div class="font-mono break-all mt-1">
          {item.method ?? ""} {item.path}
          {#if item.query}
            <span class="text-base-content/50">?{item.query}</span>
          {/if}
        </div>
        <div class="text-base-content/70 mt-1">{item.duration_ms !== null ? `${Math.round(item.duration_ms)} ms` : "—"}</div>
      </div>
    {/each}
  </div>

  <div class="flex flex-wrap items-center justify-between gap-2 mt-3">
    <span role="status" class="text-sm text-base-content/70">
      Showing {offset + 1}–{offset + items.length} of {total.toLocaleString()}
    </span>
    <div class="flex gap-2">
      <button class="btn btn-sm" onclick={pagePrev} disabled={offset === 0}>Prev</button>
      <button class="btn btn-sm" onclick={pageNext} disabled={offset + PAGE_SIZE >= total}>Next</button>
    </div>
  </div>
{/if}

<div class="flex justify-end mt-4">
  <button class="btn btn-sm" onclick={onClose}>Close</button>
</div>