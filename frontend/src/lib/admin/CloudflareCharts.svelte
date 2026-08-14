<script lang="ts">
  import ChartJs from "$lib/charts/ChartJs.svelte";
  import type { CloudflareSummary } from "$lib/api";

  let {
    summary,
    chartColors,
  }: {
    summary: CloudflareSummary | null;
    chartColors: Record<string, string> | null;
  } = $props();

  function mixColor(resolved: string, alpha: number): string {
    const trimmed = resolved.trim();
    if (trimmed.endsWith(")")) return trimmed.replace(/\)$/, ` / ${alpha})`);
    return trimmed;
  }

  function fmtBytes(bytes: number): string {
    if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
    if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
    if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} KB`;
    return `${bytes} B`;
  }

  function palette(n: number): string[] {
    const c = chartColors;
    if (!c) return [];
    const base = [
      c.primary, c.secondary, c.accent, "#22c55e", "#ef4444", "#8b5cf6",
      "#ec4899", "#14b8a6", "#f97316", "#64748b",
    ];
    return base.slice(0, n);
  }

  const dailyChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.daily.length === 0) return null;
    return {
      labels: summary.daily.map((d) => d.date.slice(5)),
      datasets: [
        {
          label: "Requests",
          data: summary.daily.map((d) => d.requests),
          borderColor: c.primary,
          backgroundColor: mixColor(c.primary, 0.12),
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    };
  });

  const visitorsChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.daily.length === 0) return null;
    return {
      labels: summary.daily.map((d) => d.date.slice(5)),
      datasets: [
        {
          label: "Visitors",
          data: summary.daily.map((d) => d.unique_visitors),
          borderColor: c.secondary,
          backgroundColor: mixColor(c.secondary, 0.1),
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    };
  });

  const bandwidthChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.daily.length === 0) return null;
    return {
      labels: summary.daily.map((d) => d.date.slice(5)),
      datasets: [
        {
          label: "Bandwidth",
          data: summary.daily.map((d) => d.bytes),
          borderColor: c.accent,
          backgroundColor: mixColor(c.accent, 0.1),
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    };
  });

  const hourlyChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.hourly.length === 0) return null;
    return {
      labels: summary.hourly.map((h) => `${h.hour}:00`),
      datasets: [
        {
          label: "Requests",
          data: summary.hourly.map((h) => h.requests),
          backgroundColor: c.primary,
        },
      ],
    };
  });

  const topPathsChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.top_paths.length === 0) return null;
    const rows = summary.top_paths.slice().reverse();
    return {
      labels: rows.map((r) => r.name),
      datasets: [
        {
          label: "Requests",
          data: rows.map((r) => r.count),
          backgroundColor: c.accent,
        },
      ],
    };
  });

  const cacheStatusChart = $derived.by(() => {
    if (!chartColors || !summary || summary.cache_status.length === 0) return null;
    const rows = summary.cache_status.slice(0, 6);
    return {
      labels: rows.map((s) => s.name),
      datasets: [
        {
          label: "Requests",
          data: rows.map((s) => s.count),
          backgroundColor: palette(rows.length),
        },
      ],
    };
  });

  const deviceChart = $derived.by(() => {
    if (!chartColors || !summary || summary.device_type.length === 0) return null;
    const rows = summary.device_type.slice(0, 6);
    return {
      labels: rows.map((d) => d.name),
      datasets: [
        {
          label: "Requests",
          data: rows.map((d) => d.count),
          backgroundColor: palette(rows.length),
        },
      ],
    };
  });

  const statusChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.status_codes.length === 0) return null;
    return {
      labels: summary.status_codes.map((s) => String(s.code)),
      datasets: [
        {
          label: "Requests",
          data: summary.status_codes.map((s) => s.requests),
          backgroundColor: c.accent,
        },
      ],
    };
  });

  const countryChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !summary || summary.top_countries.length === 0) return null;
    const rows = summary.top_countries.slice().reverse();
    return {
      labels: rows.map((r) => r.country),
      datasets: [
        {
          label: "Requests",
          data: rows.map((r) => r.requests),
          backgroundColor: c.secondary,
        },
      ],
    };
  });
</script>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Cloudflare requests per day</h4>
    {#if dailyChart}
      <ChartJs
        type="line"
        data={dailyChart}
        heightClass="h-44"
        options={{
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: chartColors?.text, maxTicksLimit: 8, maxRotation: 0 } },
            y: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
          },
        }}
        label="Cloudflare requests per day"
        fallbackText={`Cloudflare requests per day: ${summary?.daily.map((d) => `${d.date}: ${d.requests}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data for this range.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Cloudflare status codes <span class="text-xs font-normal text-base-content/60">last 24 hours</span></h4>
    {#if statusChart}
      <ChartJs
        type="bar"
        data={statusChart}
        heightClass="h-44"
        options={{
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: chartColors?.text } },
            y: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
          },
        }}
        label="Cloudflare response status codes (last 24 hours)"
        fallbackText={`Status codes: ${summary?.status_codes.map((s) => `${s.code}: ${s.requests}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data yet.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Cloudflare top countries <span class="text-xs font-normal text-base-content/60">last 24 hours</span></h4>
    {#if countryChart}
      <ChartJs
        type="bar"
        data={countryChart}
        heightClass="h-44"
        options={{
          indexAxis: "y",
          plugins: { legend: { display: false } },
          scales: {
            x: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
            y: { grid: { display: false }, ticks: { color: chartColors?.text } },
          },
        }}
        label="Cloudflare top countries (last 24 hours)"
        fallbackText={`Top countries: ${summary?.top_countries.map((c) => `${c.country}: ${c.requests}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data yet.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Unique visitors per day</h4>
    {#if visitorsChart}
      <ChartJs
        type="line"
        data={visitorsChart}
        heightClass="h-44"
        options={{
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: chartColors?.text, maxTicksLimit: 8, maxRotation: 0 } },
            y: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
          },
        }}
        label="Unique visitors per day"
        fallbackText={`Unique visitors per day: ${summary?.daily.map((d) => `${d.date}: ${d.unique_visitors}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data for this range.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Bandwidth per day</h4>
    {#if bandwidthChart}
      <ChartJs
        type="line"
        data={bandwidthChart}
        heightClass="h-44"
        options={{
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: chartColors?.text, maxTicksLimit: 8, maxRotation: 0 } },
            y: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0, callback: (v: string | number) => fmtBytes(Number(v)) } },
          },
        }}
        label="Bandwidth per day"
        fallbackText={`Bandwidth per day: ${summary?.daily.map((d) => `${d.date}: ${fmtBytes(d.bytes)}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data for this range.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Hourly requests <span class="text-xs font-normal text-base-content/60">last 24 hours</span></h4>
    {#if hourlyChart}
      <ChartJs
        type="bar"
        data={hourlyChart}
        heightClass="h-44"
        options={{
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: chartColors?.text, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
            y: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
          },
        }}
        label="Cloudflare hourly requests (last 24 hours)"
        fallbackText={`Hourly requests: ${summary?.hourly.map((h) => `${h.hour}:00 — ${h.requests}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data yet.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Top paths <span class="text-xs font-normal text-base-content/60">last 24 hours</span></h4>
    {#if topPathsChart}
      <ChartJs
        type="bar"
        data={topPathsChart}
        heightClass="h-44"
        options={{
          indexAxis: "y",
          plugins: { legend: { display: false } },
          scales: {
            x: { beginAtZero: true, grid: { color: chartColors?.grid }, ticks: { color: chartColors?.text, precision: 0 } },
            y: { grid: { display: false }, ticks: { color: chartColors?.text } },
          },
        }}
        label="Cloudflare top paths (last 24 hours)"
        fallbackText={`Top paths: ${summary?.top_paths.map((p) => `${p.name}: ${p.count}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data yet.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Cache status <span class="text-xs font-normal text-base-content/60">last 24 hours</span></h4>
    {#if cacheStatusChart}
      <ChartJs
        type="doughnut"
        data={cacheStatusChart}
        heightClass="h-44"
        options={{
          plugins: { legend: { position: "right", labels: { color: chartColors?.text } } },
        }}
        label="Cloudflare cache status mix (last 24 hours)"
        fallbackText={`Cache status: ${summary?.cache_status.map((s) => `${s.name}: ${s.count}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data yet.</p>
    {/if}
  </div>
</div>

<div class="card bg-base-200 border border-base-300">
  <div class="card-body">
    <h4 class="card-title text-base">Device split <span class="text-xs font-normal text-base-content/60">last 24 hours</span></h4>
    {#if deviceChart}
      <ChartJs
        type="doughnut"
        data={deviceChart}
        heightClass="h-44"
        options={{
          plugins: { legend: { position: "right", labels: { color: chartColors?.text } } },
        }}
        label="Cloudflare device split (last 24 hours)"
        fallbackText={`Device split: ${summary?.device_type.map((d) => `${d.name}: ${d.count}`).join(", ")}`}
      />
    {:else}
      <p class="text-sm text-base-content/70">No data yet.</p>
    {/if}
  </div>
</div>
