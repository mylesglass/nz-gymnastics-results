<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import Dialog from "$lib/Dialog.svelte";
  import { clearActivityLogs, getActivityLogs } from "$lib/api";
  import type { ActivityLogItem } from "$lib/api";
  import { debounce } from "$lib/utils/debounce";

  const PAGE_SIZE = 50;

  let items = $state<ActivityLogItem[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let offset = $state(0);

  let userFilter = $state("");
  let typeFilter = $state("");
  let appliedUser = $state("");
  let appliedType = $state("");

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

<svelte:head>
  <title>Activity Log — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <a href="/admin" class="link text-sm">← Back to Admin</a>
  <div class="flex items-center gap-3 mt-2 mb-1">
    <h1 class="text-3xl font-bold">Activity Log</h1>
    <span class="badge badge-outline">{total.toLocaleString()}</span>
  </div>
  <p class="text-base-content/70 mb-4">
    Pages visited and API requests made by logged-in users. Anonymous traffic is not recorded.
  </p>

  <div class="flex flex-wrap items-end gap-2 mb-4">
    <label class="form-control w-48">
      <span class="label-text text-xs mb-1">Username</span>
      <input
        type="text"
        class="input input-bordered input-sm"
        bind:value={userFilter}
        placeholder="e.g. admin"
        oninput={debouncedApplyFilters}
      />
    </label>
    <label class="form-control w-44">
      <span class="label-text text-xs mb-1">Type</span>
      <select class="select select-bordered select-sm" bind:value={typeFilter} onchange={applyFilters}>
        <option value="">All</option>
        <option value="page">Page views</option>
        <option value="api">API requests</option>
      </select>
    </label>
    <button class="btn btn-outline btn-sm" onclick={applyFilters} disabled={loading}>Refresh</button>
    <label class="form-control flex-row items-center gap-2 ml-auto">
      <span class="label-text text-xs">Auto-refresh</span>
      <input type="checkbox" class="toggle toggle-sm" bind:checked={autoRefresh} aria-label="Auto-refresh" />
    </label>
  </div>

  {#if error}
    <div role="alert" class="alert alert-error mb-4">
      <span>{error}</span>
    </div>
  {:else if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if items.length === 0}
    <div class="card bg-base-200 border border-base-300">
      <div class="card-body text-center">
        <p class="text-sm text-base-content/70">No activity recorded yet.</p>
      </div>
    </div>
  {:else}
    <div class="overflow-x-auto">
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

    <div class="flex items-center justify-between mt-3">
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
