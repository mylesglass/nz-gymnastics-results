<script lang="ts">
  import ChartJs from "$lib/charts/ChartJs.svelte";
  import type { ActivitySummary } from "$lib/api";

  let {
    summary,
    chartColors,
    rangeDays,
  }: {
    summary: ActivitySummary | null;
    chartColors: Record<string, string> | null;
    rangeDays: number;
  } = $props();

  function mixColor(resolved: string, alpha: number): string {
    const trimmed = resolved.trim();
    if (trimmed.endsWith(")")) return trimmed.replace(/\)$/, ` / ${alpha})`);
    return trimmed;
  }

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
</script>

  <div class="card bg-base-200 border border-base-300">
    <div class="card-body">
      <h3 class="card-title text-base">Traffic over time</h3>
      {#if trafficChart}
        <ChartJs
          type="line"
          data={trafficChart}
          heightClass="h-44"
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
      <h3 class="card-title text-base">Hour of day</h3>
      <ChartJs
        type="bar"
        data={hourChart ?? { labels: [], datasets: [] }}
        heightClass="h-44"
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
      <h3 class="card-title text-base">Top pages</h3>
      {#if topPagesChart}
        <ChartJs
          type="bar"
          data={topPagesChart}
          heightClass="h-44"
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
      <h3 class="card-title text-base">Top users</h3>
      {#if topUsersChart}
        <ChartJs
          type="bar"
          data={topUsersChart}
          heightClass="h-44"
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
