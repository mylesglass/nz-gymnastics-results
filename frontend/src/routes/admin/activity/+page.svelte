<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import Dialog from "$lib/Dialog.svelte";
  import ChartJs from "$lib/charts/ChartJs.svelte";
  import { clearActivityLogs, getActivityLogs, getActivitySummary } from "$lib/api";
  import type { ActivityLogItem, ActivitySummary } from "$lib/api";
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

  let summary = $state<ActivitySummary | null>(null);
  let summaryLoading = $state(true);
  let summaryError = $state<string | null>(null);

  let chartColors = $state<Record<string, string> | null>(null);

  let showClear = $state(false);
  let clearing = $state(false);
  let toast = $state<string | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  let autoRefresh = $state(true);
  let refreshInterval: ReturnType<typeof setInterval> | undefined;

  function cssVar(name: string, fallback: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  }

  function mixColor(resolved: string, alpha: number): string {
    const trimmed = resolved.trim();
    if (trimmed.endsWith(")")) return trimmed.replace(/\)$/, ` / ${alpha})`);
    return trimmed;
  }

  async function loadSummary() {
    summaryLoading = true;
    summaryError = null;
    try {
      summary = await getActivitySummary(rangeDays);
    } catch (e) {
      summaryError = String(e);
    } finally {
      summaryLoading = false;
    }
  }

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

  async function loadAll() {
    await Promise.all([loadSummary(), load()]);
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
    loadAll();
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
      await loadAll();
    } catch (e) {
      showToast(`Error: ${e}`);
    } finally {
      clearing = false;
    }
  }

  onMount(async () => {
    chartColors = {
      primary: cssVar("--color-primary", "#3b82f6"),
      secondary: cssVar("--color-secondary", "#22d3ee"),
      accent: cssVar("--color-accent", "#f59e0b"),
      text: cssVar("--color-base-content", "#374151"),
      grid: cssVar("--color-base-300", "#e5e7eb"),
    };
    await loadAll();
    refreshInterval = setInterval(() => {
      if (autoRefresh) loadAll();
    }, 15000);
  });

  onDestroy(() => {
    clearInterval(refreshInterval);
  });

  const totals = $derived(summary?.totals ?? null);
  const errorRate = $derived.by(() => {
    const t = totals;
    if (!t) return null;
    const total = t.page_views + t.api_requests;
    return total > 0 ? (t.errors / total) * 100 : 0;
  });

  const trafficChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.daily_series.length === 0) return null;
    return {
      labels: summary.daily_series.map((p) => p.date.slice(5)),
      datasets: [
        {
          label: "Page views",
          data: summary.daily_series.map((p) => p.page_views),
          borderColor: c.primary,
          backgroundColor: mixColor(c.primary, 0.12),
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
        },
        {
          label: "API requests",
          data: summary.daily_series.map((p) => p.api_requests),
          borderColor: c.secondary,
          backgroundColor: mixColor(c.secondary, 0.08),
          fill: false,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    };
  });

  const hourChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary) return null;
    const pv = Array(24).fill(0);
    const ap = Array(24).fill(0);
    for (const h of summary.hourly_series) {
      pv[h.hour] = h.page_views;
      ap[h.hour] = h.api_requests;
    }
    return {
      labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
      datasets: [
        { label: "Page views", data: pv, backgroundColor: c.primary },
        { label: "API requests", data: ap, backgroundColor: c.secondary },
      ],
    };
  });

  const topPagesChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.top_pages.length === 0) return null;
    const rows = summary.top_pages.slice(0, 10).slice().reverse();
    return {
      labels: rows.map((r) => r.path),
      datasets: [
        {
          label: "Views",
          data: rows.map((r) => r.count),
          backgroundColor: c.accent,
        },
      ],
    };
  });

  const topUsersChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.top_users.length === 0) return null;
    const rows = summary.top_users.slice().reverse();
    return {
      labels: rows.map((u) => u.username),
      datasets: [
        {
          label: "Requests",
          data: rows.map((u) => u.page_views + u.api_requests),
          backgroundColor: c.primary,
        },
      ],
    };
  });

  const rangeDaysCount = $derived(rangeDays === 0 ? null : rangeDays);
</script>

<svelte:head>
  <title>Activity — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-7xl mx-auto">
  <a href="/admin" class="link text-sm">← Back to Admin</a>
  <div class="flex flex-wrap items-center gap-3 mt-2 mb-1">
    <h1 class="text-3xl font-bold">Activity</h1>
    <span class="badge badge-outline">{total.toLocaleString()}</span>
  </div>
  <p class="text-base-content/70 mb-4">
    Usage across the whole site — page views and API requests from anonymous visitors and
    logged-in users. Bot traffic is excluded. The detailed log below covers logged-in users.
  </p>

  <div class="flex flex-wrap items-center gap-3 mb-4">
    <div class="tabs tabs-box tabs-sm" role="group" aria-label="Time range">
      {#each RANGES as r}
        <input
          type="radio"
          name="activity_range"
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
      <button class="btn btn-outline btn-sm" onclick={loadAll} disabled={loading || summaryLoading}>Refresh</button>
      <label class="form-control flex-row items-center gap-2">
        <span class="label-text text-xs">Auto-refresh</span>
        <input type="checkbox" class="toggle toggle-sm" bind:checked={autoRefresh} aria-label="Auto-refresh" />
      </label>
    </div>
  </div>

  <!-- Stats -->
  {#if summaryError}
    <div role="alert" class="alert alert-error mb-4">
      <span>{summaryError}</span>
    </div>
  {:else if summaryLoading && !summary}
    <div class="flex justify-center py-8">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if totals}
    <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3 mb-6">
      <div class="stat bg-base-200 rounded-box py-3">
        <div class="stat-title text-base-content/70 text-xs">Page views</div>
        <div class="stat-value text-2xl">{totals.page_views.toLocaleString()}</div>
        <div class="stat-desc text-[11px]">anon {totals.anon_page_views.toLocaleString()} · logged-in {totals.auth_page_views.toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box py-3">
        <div class="stat-title text-base-content/70 text-xs">API requests</div>
        <div class="stat-value text-2xl">{totals.api_requests.toLocaleString()}</div>
        <div class="stat-desc text-[11px]">anon {totals.anon_api_requests.toLocaleString()} · logged-in {totals.auth_api_requests.toLocaleString()}</div>
      </div>
      <div class="stat bg-base-200 rounded-box py-3">
        <div class="stat-title text-base-content/70 text-xs">Errors</div>
        <div class="stat-value text-2xl text-error">{totals.errors.toLocaleString()}</div>
        <div class="stat-desc text-[11px]">
          {errorRate !== null ? `${errorRate.toFixed(1)}% of requests` : "no requests"}
        </div>
      </div>
      <div class="stat bg-base-200 rounded-box py-3">
        <div class="stat-title text-base-content/70 text-xs">Avg response</div>
        <div class="stat-value text-2xl">{totals.avg_duration_ms !== null ? `${Math.round(totals.avg_duration_ms)} ms` : "—"}</div>
        <div class="stat-desc text-[11px]">API requests</div>
      </div>
      <div class="stat bg-base-200 rounded-box py-3">
        <div class="stat-title text-base-content/70 text-xs">Active days</div>
        <div class="stat-value text-2xl">{totals.active_days}</div>
        <div class="stat-desc text-[11px]">{rangeDaysCount !== null ? `of ${rangeDaysCount} in range` : "since records began"}</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div class="card bg-base-200 border border-base-300">
        <div class="card-body">
          <h2 class="card-title text-base">Traffic over time</h2>
          {#if trafficChart}
            <ChartJs
              type="line"
              data={trafficChart}
              options={{
                interaction: { mode: "index", intersect: false },
                plugins: {
                  legend: { position: "top", labels: { color: chartColors?.text } },
                  tooltip: { mode: "index", intersect: false },
                },
                scales: {
                  x: { grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, maxTicksLimit: 8, maxRotation: 0 } },
                  y: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
                },
              }}
              label={`Page views and API requests per day over the last ${rangeDays || "all-time"} period`}
              fallbackText={`Daily page views and API requests: ${summary?.daily_series.map((p) => `${p.date}: ${p.page_views} page views, ${p.api_requests} API requests`).join("; ")}`}
            />
          {:else}
            <p class="text-sm text-base-content/70">No traffic data yet — it starts accumulating from when this dashboard is first used.</p>
          {/if}
        </div>
      </div>

      <div class="card bg-base-200 border border-base-300">
        <div class="card-body">
          <h2 class="card-title text-base">Hour of day</h2>
          <ChartJs
            type="bar"
            data={hourChart ?? { labels: [], datasets: [] }}
            options={{
              plugins: { legend: { position: "top", labels: { color: chartColors?.text } } },
              scales: {
                x: { stacked: true, grid: { display: false }, ticks: { color: chartColors?.text, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
                y: { stacked: true, beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
              },
            }}
            label="Requests per hour of day"
            fallbackText={`Requests by hour of day: ${summary?.hourly_series.map((h) => `${h.hour}:00 — ${h.page_views} page views, ${h.api_requests} API requests`).join("; ")}`}
          />
        </div>
      </div>

      <div class="card bg-base-200 border border-base-300">
        <div class="card-body">
          <h2 class="card-title text-base">Top pages</h2>
          {#if topPagesChart}
            <ChartJs
              type="bar"
              data={topPagesChart}
              options={{
                indexAxis: "y",
                plugins: { legend: { display: false } },
                scales: {
                  x: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
                  y: { grid: { display: false }, ticks: { color: chartColors?.text } },
                },
              }}
              label="Most-viewed pages"
              fallbackText={`Most viewed pages: ${summary?.top_pages.map((p) => `${p.path} (${p.count})`).join(", ")}`}
            />
          {:else}
            <p class="text-sm text-base-content/70">No page views recorded in this range.</p>
          {/if}
        </div>
      </div>

      <div class="card bg-base-200 border border-base-300">
        <div class="card-body">
          <h2 class="card-title text-base">Top users</h2>
          {#if topUsersChart}
            <ChartJs
              type="bar"
              data={topUsersChart}
              options={{
                indexAxis: "y",
                plugins: { legend: { display: false } },
                scales: {
                  x: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
                  y: { grid: { display: false }, ticks: { color: chartColors?.text } },
                },
              }}
              label="Most active logged-in users"
              fallbackText={`Most active users: ${summary?.top_users.map((u) => `${u.username} (${u.page_views + u.api_requests})`).join(", ")}`}
            />
          {:else}
            <p class="text-sm text-base-content/70">No logged-in activity in this range.</p>
          {/if}
        </div>
      </div>
    </div>
  {/if}

  <!-- Detail log -->
  <div class="flex items-center justify-between mb-2">
    <h2 class="text-lg font-semibold">Logged-in activity</h2>
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
