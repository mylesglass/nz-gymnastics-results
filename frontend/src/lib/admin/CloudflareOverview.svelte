<script lang="ts">
  import ChartJs from "$lib/charts/ChartJs.svelte";
  import type { CloudflareSummary } from "$lib/api";

  let {
    summary,
    chartColors,
    rangeDays,
  }: {
    summary: CloudflareSummary | null;
    chartColors: Record<string, string> | null;
    rangeDays: number;
  } = $props();

  const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const MONTHS_SHORT = MONTHS.map((m) => m.slice(0, 3));

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

  function fmtCompact(n: number): string {
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
    return `${n}`;
  }

  function fmtDate(iso: string): string {
    if (!iso) return "—";
    const parts = iso.slice(0, 10).split("-");
    if (parts.length !== 3) return iso;
    const month = Number(parts[1]);
    return `${Number(parts[2])} ${MONTHS[month - 1] ?? parts[1]}`;
  }

  function fmtTick(label: string): string {
    if (label.includes("T")) return label.slice(11, 16);
    const parts = label.slice(0, 10).split("-");
    if (parts.length !== 3) return label;
    const month = Number(parts[1]);
    return `${Number(parts[2])} ${MONTHS_SHORT[month - 1] ?? parts[1]}`;
  }

  const series = $derived(summary?.series ?? []);
  const totals = $derived(summary?.totals ?? null);

  const rangeLabel = $derived.by(() => {
    if (series.length === 0) return "";
    if (series.length === 1) return fmtDate(series[0].label);
    return `${fmtDate(series[0].label)} – ${fmtDate(series[series.length - 1].label)}`;
  });

  const retentionClamped = $derived((rangeDays === 0 || rangeDays > 30) && (summary?.days ?? 30) === 30);

  const hasVisitorSeries = $derived(series.some((p) => p.unique_visitors != null));

  const labels = $derived(series.map((p) => fmtTick(p.label)));

  const visitorsChart = $derived.by(() => {
    const c = chartColors;
    if (!c || !hasVisitorSeries) return null;
    return {
      labels,
      datasets: [
        {
          label: "Unique visitors",
          data: series.map((p) => p.unique_visitors ?? 0),
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

  const requestsChart = $derived.by(() => {
    const c = chartColors;
    if (!c || series.length === 0) return null;
    return {
      labels,
      datasets: [
        {
          label: "Requests",
          data: series.map((p) => p.requests),
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

  const cachedChart = $derived.by(() => {
    const c = chartColors;
    if (!c || series.length === 0) return null;
    return {
      labels,
      datasets: [
        {
          label: "Percent cached",
          data: series.map((p) => (p.cached_percent != null ? p.cached_percent * 100 : null)),
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

  const bytesChart = $derived.by(() => {
    const c = chartColors;
    if (!c || series.length === 0) return null;
    return {
      labels,
      datasets: [
        {
          label: "Data served",
          data: series.map((p) => p.bytes),
          borderColor: "#22c55e",
          backgroundColor: "rgba(34, 197, 94, 0.1)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    };
  });

  function chartOptions(yTickCallback?: (value: number | string) => string) {
    const c = chartColors ?? { text: "#374151", grid: "#e5e7eb" };
    return {
      interaction: { mode: "index" as const, intersect: false },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: c.text, maxTicksLimit: 6, maxRotation: 0, font: { size: 10 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: c.grid },
          ticks: {
            color: c.text,
            precision: 0,
            maxTicksLimit: 5,
            ...(yTickCallback ? { callback: yTickCallback } : {}),
          },
        },
      },
    };
  }

  const visitorsOptions = $derived(chartOptions());
  const requestsOptions = $derived(chartOptions((v) => fmtCompact(Number(v))));
  const cachedOptions = $derived(chartOptions((v) => `${Math.round(Number(v))}%`));
  const bytesOptions = $derived(chartOptions((v) => fmtBytes(Number(v))));
</script>

{#if series.length === 0}
  <p class="text-sm text-base-content/70">No data for this range.</p>
{:else}
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2 mb-3">
    <span class="text-sm font-medium text-base-content/70">{rangeLabel}</span>
    {#if retentionClamped}
      <span class="badge badge-outline badge-sm">showing last {summary?.days ?? 30} days (Cloudflare retention)</span>
    {/if}
  </div>

  <div class="space-y-3">
    <div class="card bg-base-200 border border-base-300">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
        <div class="min-w-44">
          <span class="material-symbols-outlined text-secondary" aria-hidden="true">group</span>
          <span class="block text-2xl font-bold leading-tight">
            {totals?.unique_visitors != null ? totals.unique_visitors.toLocaleString() : "—"}
          </span>
          <span class="block text-xs text-base-content/70">Unique visitors</span>
        </div>
        <div class="flex-1 min-w-64">
          {#if visitorsChart}
            <ChartJs
              type="line"
              data={visitorsChart}
              heightClass="h-28"
              options={visitorsOptions}
              label="Unique visitors over the selected range"
              fallbackText={`Unique visitors: ${series.map((p) => `${fmtTick(p.label)}: ${p.unique_visitors ?? 0}`).join(", ")}`}
            />
          {:else}
            <p class="text-xs text-base-content/60 py-4">
              Per-hour unique visitors aren't available for this API token — showing the daily total.
            </p>
          {/if}
        </div>
      </div>
    </div>

    <div class="card bg-base-200 border border-base-300">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
        <div class="min-w-44">
          <span class="material-symbols-outlined text-primary" aria-hidden="true">http</span>
          <span class="block text-2xl font-bold leading-tight">
            {totals?.requests != null ? totals.requests.toLocaleString() : "—"}
          </span>
          <span class="block text-xs text-base-content/70">Total requests</span>
        </div>
        <div class="flex-1 min-w-64">
          {#if requestsChart}
            <ChartJs
              type="line"
              data={requestsChart}
              heightClass="h-28"
              options={requestsOptions}
              label="Total requests over the selected range"
              fallbackText={`Total requests: ${series.map((p) => `${fmtTick(p.label)}: ${p.requests}`).join(", ")}`}
            />
          {/if}
        </div>
      </div>
    </div>

    <div class="card bg-base-200 border border-base-300">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
        <div class="min-w-44">
          <span class="material-symbols-outlined text-accent" aria-hidden="true">cached</span>
          <span class="block text-2xl font-bold leading-tight">
            {totals?.cache_hit_ratio != null ? `${(totals.cache_hit_ratio * 100).toFixed(1)}%` : "—"}
          </span>
          <span class="block text-xs text-base-content/70">Percent cached</span>
        </div>
        <div class="flex-1 min-w-64">
          {#if cachedChart}
            <ChartJs
              type="line"
              data={cachedChart}
              heightClass="h-28"
              options={cachedOptions}
              label="Percent of requests served from cache over the selected range"
              fallbackText={`Percent cached: ${series.map((p) => `${fmtTick(p.label)}: ${p.cached_percent != null ? (p.cached_percent * 100).toFixed(1) : "—"}%`).join(", ")}`}
            />
          {/if}
        </div>
      </div>
    </div>

    <div class="card bg-base-200 border border-base-300">
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 p-4">
        <div class="min-w-44">
          <span class="material-symbols-outlined text-success" aria-hidden="true">data_usage</span>
          <span class="block text-2xl font-bold leading-tight">{fmtBytes(totals?.bytes ?? 0)}</span>
          <span class="block text-xs text-base-content/70">Total data served</span>
        </div>
        <div class="flex-1 min-w-64">
          {#if bytesChart}
            <ChartJs
              type="line"
              data={bytesChart}
              heightClass="h-28"
              options={bytesOptions}
              label="Total data served over the selected range"
              fallbackText={`Total data served: ${series.map((p) => `${fmtTick(p.label)}: ${fmtBytes(p.bytes)}`).join(", ")}`}
            />
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}