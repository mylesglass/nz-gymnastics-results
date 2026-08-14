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

<p class="text-sm text-base-content/70 mb-4">
  Page views and API requests made by logged-in users. Anonymous visitors are counted in the
  graphs but don't appear here.
</p>

<div class="flex flex-wrap items-end gap-2 mb-4">
  <div class="tabs tabs-box tabs-sm" role="group" aria-label="Time range">
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
  <div class="flex flex-wrap items-end gap-2 ml-auto">
    <label class="form-control w-40">
      <span class="label-text text-xs mb-1">Username</span>
      <input
        type="text"
        class="input input-bordered input-sm"
        bind:value={userFilter}
        placeholder="e.g. admin"
        oninput={debouncedApplyFilters}
      />
    </label>
    <label class="form-control w-36">
      <span class="label-text text-xs mb-1">Type</span>
      <select class="select select-bordered select-sm" bind:value={typeFilter} onchange={applyFilters}>
        <option value="">All</option>
        <option value="page">Page views</option>
        <option value="api">API requests</option>
      </select>
    </label>
    <button class="btn btn-outline btn-sm" onclick={load} disabled={loading}>Refresh</button>
    <label class="form-control flex-row items-center gap-2">
      <span class="label-text text-xs">Auto-refresh</span>
      <input type="checkbox" class="toggle toggle-sm" bind:checked={autoRefresh} aria-label="Auto-refresh" />
    </label>
  </div>
</div>

{#if error}
  <div role="alert" class="alert alert-error mb-4">
    <span>{error}</span>
  </div>
{:else if loading && items.length === 0}
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if items.length === 0}
  <div class="card bg-base-200 border border-base-300">
    <div class="card-body text-center">
      <p class="text-sm text-base-content/70">No activity recorded for this range.</p>
    </div>
  </div>
{:else}
  <div class="hidden md:block overflow-x-auto">
    <table class="table table-sm bg-base-200 border border-base-300">
      <thead>
        <tr>
          <th>Time</th>
          <th>User</th>
          <th>Type</th>
          <th>Method</th>
          <th>Path</th>
          <th>Status</th>
          <th>ms</th>
        </tr>
      </thead>
      <tbody>
        {#each items as item}
          <tr>
            <td class="text-xs whitespace-nowrap">{fmtTime(item.created_at)}</td>
            <td class="text-xs">
              {item.username}
              <span class="badge badge-ghost badge-xs ml-1">{item.role}</span>
            </td>
            <td>
              {#if item.type === "page"}
                <span class="badge badge-info badge-xs">page</span>
              {:else}
                <span class="badge badge-secondary badge-xs">api</span>
              {/if}
            </td>
            <td class="text-xs font-mono">{item.method ?? "—"}</td>
            <td class="text-xs font-mono break-all">
              {item.path}
              {#if item.query}
                <span class="text-base-content/50">?{item.query}</span>
              {/if}
            </td>
            <td class="text-xs">
              <span class={item.status_code !== null && item.status_code >= 400 ? "text-error" : "text-base-content/70"}>
                {item.status_code ?? "—"}
              </span>
            </td>
            <td class="text-xs text-base-content/70">{item.duration_ms !== null ? Math.round(item.duration_ms) : "—"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <div class="md:hidden space-y-2">
    {#each items as item}
      <div class="card bg-base-200 border border-base-300 p-3 text-xs">
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

  <div class="flex flex-wrap items-center justify-between gap-2 mt-3">
    <span role="status" class="text-sm text-base-content/70">
      Showing {offset + 1}–{offset + items.length} of {total.toLocaleString()}
    </span>
    <div class="flex gap-2">
      <button class="btn btn-sm" onclick={pagePrev} disabled={offset === 0}>Prev</button>
      <button class="btn btn-sm" onclick={pageNext} disabled={offset + PAGE_SIZE >= total}>Next</button>
    </div>
  </div>

  <div class="flex justify-end mt-4">
    <button class="btn btn-outline btn-error btn-sm" onclick={() => (showClear = true)}>
      {appliedUser ? `Clear log for ${appliedUser}` : "Clear log"}
    </button>
  </div>
{/if}

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
