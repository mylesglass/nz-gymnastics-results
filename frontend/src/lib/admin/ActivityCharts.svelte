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

  function fmtCompact(n: number): string {
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
    return `${n}`;
  }

  function fmtDateTick(iso: string): string {
    const parts = iso.split("-");
    if (parts.length !== 3) return iso.slice(5);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${Number(parts[2])} ${months[Number(parts[1]) - 1] ?? parts[1]}`;
  }

  function chartOptions(opts?: {
    yCallback?: (value: number | string) => string;
    legend?: boolean;
    horizontal?: boolean;
    stacked?: boolean;
  }) {
    const c = chartColors ?? { text: "#374151", grid: "#e5e7eb" };
    const axisTicks = { color: c.text, maxTicksLimit: 6, maxRotation: 0, font: { size: 10 } };
    const valTicks = {
      color: c.text,
      precision: 0,
      maxTicksLimit: 5,
      ...(opts?.yCallback ? { callback: opts.yCallback } : {}),
    };
    const stack = opts?.stacked ? { stacked: true } : {};
    return {
      interaction: { mode: "index" as const, intersect: false },
      ...(opts?.horizontal ? { indexAxis: "y" as const } : {}),
      plugins: {
        legend: { display: opts?.legend ?? true, position: "top" as const, labels: { color: c.text } },
        tooltip: { mode: "index" as const, intersect: false },
      },
      scales: opts?.horizontal
        ? {
            x: { beginAtZero: true, grid: { color: c.grid }, ticks: valTicks, ...stack },
            y: { grid: { display: false }, ticks: axisTicks, ...stack },
          }
        : {
            x: { grid: { display: false }, ticks: axisTicks, ...stack },
            y: { beginAtZero: true, grid: { color: c.grid }, ticks: valTicks, ...stack },
          },
    };
  }

  const totals = $derived(summary?.totals ?? null);

  const trafficOptions = $derived(chartOptions({ yCallback: (v) => fmtCompact(Number(v)) }));
  const hourOptions = $derived(chartOptions({ yCallback: (v) => fmtCompact(Number(v)), stacked: true }));
  const topPagesOptions = $derived(chartOptions({ yCallback: (v) => fmtCompact(Number(v)), legend: false, horizontal: true }));

  const trafficChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.daily_series.length === 0) return null;
    return {
      labels: summary.daily_series.map((p) => fmtDateTick(p.date)),
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

  const peakHour = $derived.by(() => {
    const hs = summary?.hourly_series ?? [];
    if (hs.length === 0) return null;
    let best = hs[0];
    for (const h of hs) {
      if (h.page_views + h.api_requests > best.page_views + best.api_requests) best = h;
    }
    return best;
  });

  const peakLabel = $derived.by(() => {
    if (!peakHour) return "—";
    const h = peakHour.hour;
    const hour12 = h % 12 === 0 ? 12 : h % 12;
    return `${hour12} ${h < 12 ? "AM" : "PM"}`;
  });

  const topPage = $derived(summary?.top_pages[0] ?? null);
</script>

<div class="space-y-3">
  <div class="card bg-base-200 border border-base-300">
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
      <div class="min-w-44">
        <span class="material-symbols-outlined text-primary" aria-hidden="true">visibility</span>
        <span class="block text-2xl font-bold leading-tight">{fmtCompact(totals?.page_views ?? 0)}</span>
        <span class="block text-sm font-semibold text-secondary leading-tight">{fmtCompact(totals?.api_requests ?? 0)} API</span>
        <span class="block text-xs text-base-content/70">Traffic over time</span>
      </div>
      <div class="flex-1 min-w-64">
        {#if trafficChart}
          <ChartJs
            type="line"
            data={trafficChart}
            heightClass="h-28"
            options={trafficOptions}
            label={`Page views and API requests per day over the last ${rangeDays || "all-time"} period`}
            fallbackText={`Daily page views and API requests: ${summary?.daily_series.map((p) => `${p.date}: ${p.page_views} page views, ${p.api_requests} API requests`).join("; ")}`}
          />
        {:else}
          <p class="text-sm text-base-content/70 py-4">No traffic data yet — it starts accumulating from when this dashboard is first used.</p>
        {/if}
      </div>
    </div>
  </div>

  <div class="card bg-base-200 border border-base-300">
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
      <div class="min-w-44">
        <span class="material-symbols-outlined text-primary" aria-hidden="true">schedule</span>
        <span class="block text-2xl font-bold leading-tight">{peakLabel}</span>
        <span class="block text-xs text-base-content/70">Peak hour</span>
        {#if peakHour}
          <span class="block text-xs text-base-content/60">{fmtCompact(peakHour.page_views + peakHour.api_requests)} requests</span>
        {/if}
      </div>
      <div class="flex-1 min-w-64">
        <ChartJs
          type="bar"
          data={hourChart ?? { labels: [], datasets: [] }}
          heightClass="h-28"
          options={hourOptions}
          label="Requests per hour of day"
          fallbackText={`Requests by hour of day: ${summary?.hourly_series.map((h) => `${h.hour}:00 — ${h.page_views} page views, ${h.api_requests} API requests`).join("; ")}`}
        />
      </div>
    </div>
  </div>

  <div class="card bg-base-200 border border-base-300">
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
      <div class="min-w-44">
        <span class="material-symbols-outlined text-primary" aria-hidden="true">link</span>
        <span class="block text-2xl font-bold leading-tight truncate max-w-44" title={topPage?.path}>{topPage?.path ?? "—"}</span>
        <span class="block text-xs text-base-content/70">
          Top page{#if topPage} · {fmtCompact(topPage.count)} views{/if}
        </span>
      </div>
      <div class="flex-1 min-w-64">
        {#if topPagesChart}
          <ChartJs
            type="bar"
            data={topPagesChart}
            heightClass="h-40"
            options={topPagesOptions}
            label="Most-viewed pages"
            fallbackText={`Most viewed pages: ${summary?.top_pages.map((p) => `${p.path} (${p.count})`).join(", ")}`}
          />
        {:else}
          <p class="text-sm text-base-content/70 py-4">No page views recorded in this range.</p>
        {/if}
      </div>
    </div>
  </div>

  <div class="card bg-base-200 border border-base-300">
    <div class="p-4">
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-primary" aria-hidden="true">group</span>
        <span class="text-sm font-semibold">Top users</span>
        <span class="text-xs text-base-content/70">({summary?.top_users.length ?? 0})</span>
      </div>
      {#if summary && summary.top_users.length > 0}
        <div class="overflow-x-auto">
          <table class="table table-xs table-zebra w-full">
            <thead>
              <tr>
                <th class="text-base-content/70">#</th>
                <th class="text-base-content/70">User</th>
                <th class="text-base-content/70">Role</th>
                <th class="text-base-content/70 text-right">Page views</th>
                <th class="text-base-content/70 text-right">API</th>
                <th class="text-base-content/70 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {#each summary.top_users as u, i}
                <tr>
                  <td class="text-base-content/50">{i + 1}</td>
                  <td class="font-medium">{u.username}</td>
                  <td><span class="badge badge-ghost badge-xs">{u.role}</span></td>
                  <td class="text-right font-mono">{u.page_views.toLocaleString()}</td>
                  <td class="text-right font-mono">{u.api_requests.toLocaleString()}</td>
                  <td class="text-right font-mono font-semibold">{(u.page_views + u.api_requests).toLocaleString()}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="text-sm text-base-content/70 py-4">No logged-in activity in this range.</p>
      {/if}
    </div>
  </div>
</div>