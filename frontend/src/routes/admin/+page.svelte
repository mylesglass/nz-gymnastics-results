<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import Dialog from "$lib/Dialog.svelte";
  import { getCloudflareSummary, refreshCache } from "$lib/api";
  import type { ActivitySummary, CloudflareSummary } from "$lib/api";
  import Overview from "$lib/admin/Overview.svelte";
  import Activity from "$lib/admin/Activity.svelte";
  import ActivityCharts from "$lib/admin/ActivityCharts.svelte";
  import CloudflareCharts from "$lib/admin/CloudflareCharts.svelte";
  import ActivityLog from "$lib/admin/ActivityLog.svelte";
  import Upload from "$lib/admin/Upload.svelte";
  import Users from "$lib/admin/Users.svelte";
  import IdentityReview from "$lib/admin/IdentityReview.svelte";
  import StatTile from "$lib/admin/StatTile.svelte";

  type DialogKey = "upload" | "users" | "identity" | "log" | null;

  const DIALOG_HASHES: Record<string, DialogKey> = {
    upload: "upload",
    users: "users",
    identity: "identity",
    log: "log",
  };

  let openDialog = $state<DialogKey>(null);

  $effect(() => {
    const key = $page.url.hash.replace("#", "");
    openDialog = DIALOG_HASHES[key] ?? null;
  });

  function openDialogKey(key: Exclude<DialogKey, null>) {
    goto(`/admin#${key}`, { replaceState: true });
  }

  function closeDialog() {
    openDialog = null;
    goto("/admin", { replaceState: true });
  }
  let chartData = $state<{
    summary: ActivitySummary | null;
    chartColors: Record<string, string> | null;
    rangeDays: number;
  } | null>(null);
  let identityCount = $state(0);

  let refreshToken = $state(0);
  let cacheToast = $state<string | null>(null);
  let cacheToastTimer: ReturnType<typeof setTimeout> | undefined;

  let cfData = $state<CloudflareSummary | null>(null);
  let cfLoading = $state(true);
  let cfError = $state<string | null>(null);
  let cfColors = $state<Record<string, string> | null>(null);

  // Cloudflare only supports 7/30-day windows; follow the shared Usage range
  // (clamping 90/all-time to the 30-day maximum the API retains).
  const cloudflareRange = $derived.by(() => {
    const rd = chartData?.rangeDays ?? 30;
    return rd === 0 || rd > 30 ? 30 : rd;
  });

  function cssVar(name: string, fallback: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  }

  function fmtBytes(bytes: number): string {
    if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
    if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
    if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} KB`;
    return `${bytes} B`;
  }

  async function loadCloudflare() {
    cfLoading = true;
    cfError = null;
    try {
      const s = await getCloudflareSummary(cloudflareRange);
      cfData = s;
      if (s.error) cfError = s.error;
    } catch (e) {
      cfError = String(e);
    } finally {
      cfLoading = false;
    }
  }

  async function runRefresh() {
    clearTimeout(cacheToastTimer);
    try {
      await refreshCache();
      refreshToken += 1;
      cacheToast = "Cache refreshed — all data is now fresh";
    } catch (e) {
      cacheToast = `Error: ${e}`;
    }
    cacheToastTimer = setTimeout(() => { cacheToast = null; }, 4000);
  }

  onMount(async () => {
    cfColors = {
      primary: cssVar("--color-primary", "#3b82f6"),
      secondary: cssVar("--color-secondary", "#22d3ee"),
      accent: cssVar("--color-accent", "#f59e0b"),
      text: cssVar("--color-base-content", "#374151"),
      grid: cssVar("--color-base-300", "#e5e7eb"),
    };
    await loadCloudflare();
  });

  let prevCfRange = cloudflareRange;
  $effect(() => {
    if (cloudflareRange === prevCfRange) return;
    prevCfRange = cloudflareRange;
    loadCloudflare();
  });

  const cfTotals = $derived(cfData?.totals ?? null);
</script>

<svelte:head>
  <title>Admin — NZ Gymnastics Results</title>
</svelte:head>

<div class="w-full space-y-6">
  <h1 class="text-3xl font-bold">Admin Dashboard</h1>

  <section aria-labelledby="band-site">
    <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
      <div>
        <h2 id="band-site" class="text-xs font-semibold uppercase tracking-wider text-base-content/50 mb-2">Site</h2>
        <Overview refreshToken={refreshToken} />
      </div>
      <div class="lg:text-right">
        <h2 id="band-manage" class="text-xs font-semibold uppercase tracking-wider text-base-content/50 mb-2">Manage</h2>
        <div class="flex flex-wrap items-center gap-2 bg-base-200/50 rounded-2xl p-3 lg:justify-end">
          <button class="btn btn-primary btn-sm gap-1" onclick={runRefresh}>
            <span class="material-symbols-outlined" aria-hidden="true">refresh</span>
            Refresh cache
          </button>
          <button class="btn btn-outline btn-sm gap-1" onclick={() => openDialogKey("upload")}>
            <span class="material-symbols-outlined" aria-hidden="true">upload_file</span>
            Upload
          </button>
          <button class="btn btn-outline btn-sm gap-1" onclick={() => openDialogKey("users")}>
            <span class="material-symbols-outlined" aria-hidden="true">group</span>
            Users
          </button>
          <button class="btn btn-outline btn-sm gap-1" onclick={() => openDialogKey("identity")}>
            <span class="material-symbols-outlined" aria-hidden="true">badge</span>
            Identity Review
            {#if identityCount > 0}
              <span class="badge badge-warning badge-sm">{identityCount}</span>
            {/if}
          </button>
          <button class="btn btn-outline btn-sm gap-1" onclick={() => openDialogKey("log")}>
            <span class="material-symbols-outlined" aria-hidden="true">history</span>
            Logged-in activity
          </button>
        </div>
      </div>
    </div>
  </section>

  <section aria-labelledby="band-server" id="activity">
    <h2 id="band-server" class="text-xs font-semibold uppercase tracking-wider text-base-content/50 mb-2">Server usage</h2>
    <Activity onData={(d) => (chartData = d)} />

    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
      {#if chartData}
        <ActivityCharts
          summary={chartData.summary}
          chartColors={chartData.chartColors}
          rangeDays={chartData.rangeDays}
        />
      {/if}
    </div>
  </section>

  <section aria-labelledby="band-cloudflare">
    <h2 id="band-cloudflare" class="text-xs font-semibold uppercase tracking-wider text-base-content/50 mb-2">Cloudflare</h2>
    {#if cfError}
      <div role="alert" class="alert alert-error">
        <span>{cfError}</span>
      </div>
    {:else if cfLoading && !cfData}
      <span class="loading loading-spinner loading-sm"></span>
    {:else if cfData && !cfData.configured}
      <p class="text-sm text-base-content/70">
        Cloudflare analytics aren't configured — set <code class="font-mono">CLOUDFLARE_ZONE_ID</code>
        and <code class="font-mono">CLOUDFLARE_API_TOKEN</code> on the backend to show edge traffic.
      </p>
    {:else if cfTotals}
      <div class="flex flex-wrap items-center gap-x-6 gap-y-4 bg-base-200/50 rounded-2xl p-4">
        <StatTile icon="http" label="Requests" value={cfTotals.requests.toLocaleString()} />
        <StatTile icon="data_usage" label="Bandwidth" value={fmtBytes(cfTotals.bytes)} />
        <StatTile icon="person" label="Unique visitors" value={cfTotals.unique_visitors.toLocaleString()} />
        <StatTile icon="security" label="Threats" value={cfTotals.threats.toLocaleString()} />
        <StatTile
          icon="cached"
          label="Cache hit"
          value={cfTotals.cache_hit_ratio !== null ? `${(cfTotals.cache_hit_ratio * 100).toFixed(0)}%` : "—"}
        />
      </div>
      <p class="text-xs text-base-content/60 mt-2">
        Status codes and top countries always cover the last 24 hours — Cloudflare's breakdown
        API only allows a one-day window. The other figures follow the range selected above.
      </p>
    {/if}

    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
      {#if cfData?.configured && !cfError}
        <CloudflareCharts summary={cfData} chartColors={cfColors} />
      {/if}
    </div>
  </section>
</div>

{#if openDialog === "upload"}
  <Dialog title="Upload Event" onClose={closeDialog} maxWidth="max-w-3xl">
    <Upload />
  </Dialog>
{:else if openDialog === "users"}
  <Dialog title="User Management" onClose={closeDialog} maxWidth="max-w-3xl">
    <Users />
  </Dialog>
{:else if openDialog === "identity"}
  <Dialog title="Identity Review" onClose={closeDialog} maxWidth="max-w-5xl">
    <IdentityReview onCount={(n) => (identityCount = n)} />
  </Dialog>
{:else if openDialog === "log"}
  <Dialog title="Logged-in activity" onClose={closeDialog} maxWidth="max-w-4xl">
    <ActivityLog />
  </Dialog>
{/if}

{#if cacheToast}
  <div class="toast toast-bottom toast-start z-50" role="status">
    <div class="alert alert-info text-sm">
      <span>{cacheToast}</span>
    </div>
  </div>
{/if}
