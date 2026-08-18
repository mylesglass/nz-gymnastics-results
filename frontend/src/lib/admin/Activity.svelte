<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import StatTile from "$lib/admin/StatTile.svelte";
  import { getActivitySummary } from "$lib/api";
  import type { ActivitySummary } from "$lib/api";

  const RANGES = [
    { days: 1, label: "24 hours" },
    { days: 7, label: "7 days" },
    { days: 30, label: "30 days" },
    { days: 90, label: "90 days" },
    { days: 0, label: "All time" },
  ];

  let {
    onData,
    onErrorsClick,
  }: {
    onData?: (data: { summary: ActivitySummary | null; chartColors: Record<string, string> | null; rangeDays: number }) => void;
    onErrorsClick?: () => void;
  } = $props();

  let rangeDays = $state(30);

  let summary = $state<ActivitySummary | null>(null);
  let summaryLoading = $state(true);
  let summaryError = $state<string | null>(null);

  let chartColors = $state<Record<string, string> | null>(null);

  let autoRefresh = $state(true);
  let refreshInterval: ReturnType<typeof setInterval> | undefined;

  function cssVar(name: string, fallback: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
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
    onData?.({ summary, chartColors, rangeDays });
  }

  function setRange(days: number) {
    if (rangeDays === days) return;
    rangeDays = days;
    loadSummary();
  }

  onMount(async () => {
    chartColors = {
      primary: cssVar("--color-primary", "#3b82f6"),
      secondary: cssVar("--color-secondary", "#22d3ee"),
      accent: cssVar("--color-accent", "#f59e0b"),
      text: cssVar("--color-base-content", "#374151"),
      grid: cssVar("--color-base-300", "#e5e7eb"),
    };
    await loadSummary();
    refreshInterval = setInterval(() => {
      if (autoRefresh) loadSummary();
    }, 15000);
  });

  onDestroy(() => {
    clearInterval(refreshInterval);
  });

  const totals = $derived(summary?.totals ?? null);
  const rangeDaysCount = $derived(rangeDays === 0 ? null : rangeDays);
</script>

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
  <div class="flex flex-wrap items-center gap-2 ml-auto">
    <button class="btn btn-outline btn-sm" onclick={loadSummary} disabled={summaryLoading}>Refresh</button>
    <label class="form-control flex-row items-center gap-2">
      <span class="label-text text-xs">Auto-refresh</span>
      <input type="checkbox" class="toggle toggle-sm" bind:checked={autoRefresh} aria-label="Auto-refresh" />
    </label>
  </div>
</div>

{#if summaryError}
  <div role="alert" class="alert alert-error mb-4">
    <span>{summaryError}</span>
  </div>
{:else if summaryLoading && !summary}
  <div class="flex justify-center py-8">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if totals}
  <div class="flex flex-wrap items-center gap-x-6 gap-y-4 bg-base-200/50 rounded-2xl p-4">
    <StatTile
      icon="visibility"
      label="Page views"
      value={totals.page_views.toLocaleString()}
      sub={`anon ${totals.anon_page_views.toLocaleString()} · logged-in ${totals.auth_page_views.toLocaleString()}`}
    />
    <StatTile
      icon="api"
      label="API requests"
      value={totals.api_requests.toLocaleString()}
      sub={`anon ${totals.anon_api_requests.toLocaleString()} · logged-in ${totals.auth_api_requests.toLocaleString()}`}
    />
    <StatTile
      icon="error"
      label="Errors"
      value={totals.errors.toLocaleString()}
      sub={totals.auth_errors > 0 ? `${totals.auth_errors} logged-in · ${totals.anon_errors} anonymous` : `${totals.anon_errors} anonymous`}
      valueClass="text-lg text-error"
      onclick={onErrorsClick}
      buttonClass="text-error"
      iconClass="text-error"
    />
    <StatTile
      icon="timer"
      label="Avg response"
      value={totals.avg_duration_ms !== null ? `${Math.round(totals.avg_duration_ms)} ms` : "—"}
      sub="API requests"
    />
    <StatTile
      icon="calendar_month"
      label="Active days"
      value={String(totals.active_days)}
      sub={rangeDaysCount !== null ? `of ${rangeDaysCount} in range` : "since records began"}
    />
  </div>
{/if}
