<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import Dialog from "$lib/Dialog.svelte";
  import { clearActivityLogs, getActivityLogs } from "$lib/api";
  import type { ActivityLogItem } from "$lib/api";
  import { debounce } from "$lib/utils/debounce";

  const PAGE_SIZE = 50;

  const RANGES = [
    { days: 7, label: "7 days" },
    { days: 30, label: "30 days" },
    { days: 90, label: "90 days" },
    { days: 0, label: "All time" },
  ];

  let items = $state<ActivityLogItem[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let offset = $state(0);

  let userFilter = $state("");
  let typeFilter = $state("");
  let appliedUser = $state("");
  let appliedType = $state("");

  let rangeDays = $state(30);

  let showClear = $state(false);
  let clearing = $state(false);
  let toast = $state<string | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  let autoRefresh = $state(true);
  let refreshInterval: ReturnType<typeof setInterval> | undefined;

  async function load() {
    loading = true;
    error = null;
    try {
      const data = await getActivityLogs({
        user: appliedUser || undefined,
        type: appliedType || undefined,
        limit: PAGE_SIZE,
        offset,
        days: rangeDays || undefined,
      });
      items = data.items;
      total = data.total;
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }

  function applyFilters() {
    offset = 0;
    appliedUser = userFilter.trim();
    appliedType = typeFilter;
    load();
  }

  const debouncedApplyFilters = debounce(applyFilters, 400);

  function setRange(days: number) {
    if (rangeDays === days) return;
    rangeDays = days;
    offset = 0;
    load();
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

  function showToast(msg: string) {
    clearTimeout(toastTimer);
    toast = msg;
    toastTimer = setTimeout(() => (toast = null), 4000);
  }

  async function runClear() {
    clearing = true;
    try {
      const res = await clearActivityLogs(appliedUser || undefined);
      showClear = false;
      showToast(
        `Cleared ${res.deleted} log entr${res.deleted === 1 ? "y" : "ies"}${appliedUser ? ` for ${appliedUser}` : ""}`
      );
      await load();
    } catch (e) {
      showToast(`Error: ${e}`);
    } finally {
      clearing = false;
    }
  }

  onMount(async () => {
    await load();
    refreshInterval = setInterval(() => {
      if (autoRefresh) load();
    }, 15000);
  });

  onDestroy(() => {
    clearInterval(refreshInterval);
  });
</script>

<div class="card bg-base-200 border border-base-300 h-full overflow-hidden flex flex-col">
  <div class="p-4 pb-0 flex-none">
    <h3 class="card-title text-base">Logged-in activity</h3>
    <p class="text-xs text-base-content/70 mb-2">
      Page views and API requests by logged-in users. Anonymous visitors are counted in the graphs but don't appear here.
    </p>

    <div class="tabs tabs-box tabs-sm mb-3" role="group" aria-label="Time range">
      {#each RANGES as r}
        <input
          type="radio"
          name="activity_log_range"
          class="tab checked:bg-secondary checked:text-secondary-content"
          aria-label={r.label}
          checked={rangeDays === r.days}
          onchange={() => setRange(r.days)}
        />
      {/each}
    </div>

    <div class="flex flex-wrap items-end gap-2 mb-3">
      <label class="form-control flex-1 min-w-32">
        <span class="label-text text-xs mb-1">Username</span>
        <input
          type="text"
          class="input input-bordered input-sm"
          bind:value={userFilter}
          placeholder="e.g. alice"
          oninput={debouncedApplyFilters}
        />
      </label>
      <label class="form-control w-28">
        <span class="label-text text-xs mb-1">Type</span>
        <select class="select select-bordered select-sm" bind:value={typeFilter} onchange={applyFilters}>
          <option value="">All</option>
          <option value="page">Page views</option>
          <option value="api">API requests</option>
        </select>
      </label>
      <label class="form-control flex-row items-center gap-2 pb-1">
        <span class="label-text text-xs">Auto-refresh</span>
        <input type="checkbox" class="toggle toggle-sm" bind:checked={autoRefresh} aria-label="Auto-refresh" />
      </label>
    </div>
  </div>

  {#if error}
    <div class="px-4 flex-none">
      <div role="alert" class="alert alert-error">
        <span>{error}</span>
      </div>
    </div>
  {:else if loading && items.length === 0}
    <div class="flex-1 flex items-center justify-center min-h-0">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if items.length === 0}
    <div class="flex-1 flex items-center justify-center min-h-0">
      <p class="text-sm text-base-content/70">No activity recorded for this range.</p>
    </div>
  {:else}
    <div class="flex-1 min-h-0 overflow-y-auto px-4 space-y-2" role="list">
      {#each items as item}
        <div class="border border-base-300 rounded-lg p-3 text-xs bg-base-100">
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium">
              {item.username}
              <span class="badge badge-ghost badge-xs ml-1">{item.role}</span>
            </span>
            <span>
              {#if item.type === "page"}
                <span class="badge badge-info badge-xs">page</span>
              {:else}
                <span class="badge badge-secondary badge-xs">api</span>
              {/if}
            </span>
          </div>
          <div class="text-base-content/70 mt-1">{fmtTime(item.created_at)}</div>
          <div class="font-mono break-all mt-1">
            {item.path}
            {#if item.query}
              <span class="text-base-content/50">?{item.query}</span>
            {/if}
          </div>
          <div class="flex gap-3 mt-1 text-base-content/70">
            <span>{item.method ?? "—"}</span>
            <span class={item.status_code !== null && item.status_code >= 400 ? "text-error" : ""}>{item.status_code ?? "—"}</span>
            <span>{item.duration_ms !== null ? `${Math.round(item.duration_ms)} ms` : "—"}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if items.length > 0}
    <div class="p-4 pt-2 flex-none">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
        <span role="status" class="text-xs text-base-content/70">
          Showing {offset + 1}–{offset + items.length} of {total.toLocaleString()}
        </span>
        <div class="flex gap-2">
          <button class="btn btn-sm" onclick={pagePrev} disabled={offset === 0}>Prev</button>
          <button class="btn btn-sm" onclick={pageNext} disabled={offset + PAGE_SIZE >= total}>Next</button>
        </div>
      </div>
      <div class="flex justify-end">
        <button class="btn btn-outline btn-error btn-sm" onclick={() => (showClear = true)}>
          {appliedUser ? `Clear log for ${appliedUser}` : "Clear log"}
        </button>
      </div>
    </div>
  {/if}
</div>

{#if showClear}
  <Dialog title="Clear activity log" onClose={() => (showClear = false)}>
    <p class="text-sm text-base-content/70 mb-4">
      {appliedUser
        ? `Delete all logged activity from "${appliedUser}"? This cannot be undone.`
        : "Delete all logged activity? This cannot be undone."}
    </p>
    <div class="flex justify-end gap-2">
      <button class="btn btn-sm" onclick={() => (showClear = false)}>Cancel</button>
      <button class="btn btn-error btn-sm" onclick={runClear} disabled={clearing}>
        {clearing ? "Clearing..." : "Delete"}
      </button>
    </div>
  </Dialog>
{/if}

{#if toast}
  <div class="toast toast-bottom toast-end z-50" role="status">
    <div class="alert alert-success text-sm">
      <span>{toast}</span>
    </div>
  </div>
{/if}