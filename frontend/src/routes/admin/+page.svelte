<script lang="ts">
  import Dialog from "$lib/Dialog.svelte";
  import { refreshCache } from "$lib/api";
  import Overview from "$lib/admin/Overview.svelte";
  import Activity from "$lib/admin/Activity.svelte";
  import ActivityCharts from "$lib/admin/ActivityCharts.svelte";
  import ActivityLog from "$lib/admin/ActivityLog.svelte";
  import Upload from "$lib/admin/Upload.svelte";
  import Users from "$lib/admin/Users.svelte";
  import IdentityReview from "$lib/admin/IdentityReview.svelte";
  import type { ActivitySummary } from "$lib/api";

  type DialogKey = "upload" | "users" | "identity" | "log" | null;

  let openDialog = $state<DialogKey>(null);
  let chartData = $state<{
    summary: ActivitySummary | null;
    chartColors: Record<string, string> | null;
    rangeDays: number;
  } | null>(null);
  let identityCount = $state(0);

  let refreshToken = $state(0);
  let cacheToast = $state<string | null>(null);
  let cacheToastTimer: ReturnType<typeof setTimeout> | undefined;

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
        <div class="flex flex-wrap gap-3">
          <button
            class="w-24 h-24 flex flex-col items-center justify-center gap-0.5 rounded-box bg-primary text-primary-content border border-primary hover:bg-primary/90 transition-all cursor-pointer"
            onclick={runRefresh}
            aria-label="Refresh cache"
          >
            <span class="material-symbols-outlined" aria-hidden="true">refresh</span>
            <span class="text-sm font-bold leading-none">Refresh</span>
            <span class="text-[10px] text-primary-content/70 text-center leading-tight">cache</span>
          </button>
          <button
            class="w-24 h-24 flex flex-col items-center justify-center gap-0.5 rounded-box bg-primary text-primary-content border border-primary hover:bg-primary/90 transition-all cursor-pointer"
            onclick={() => (openDialog = "upload")}
            aria-label="Upload events"
          >
            <span class="material-symbols-outlined" aria-hidden="true">upload_file</span>
            <span class="text-sm font-bold leading-none">Upload</span>
            <span class="text-[10px] text-primary-content/70 text-center leading-tight">events</span>
          </button>
          <button
            class="w-24 h-24 flex flex-col items-center justify-center gap-0.5 rounded-box bg-primary text-primary-content border border-primary hover:bg-primary/90 transition-all cursor-pointer"
            onclick={() => (openDialog = "users")}
            aria-label="Manage users"
          >
            <span class="material-symbols-outlined" aria-hidden="true">group</span>
            <span class="text-sm font-bold leading-none">Users</span>
            <span class="text-[10px] text-primary-content/70 text-center leading-tight">accounts</span>
          </button>
          <button
            class="w-24 h-24 flex flex-col items-center justify-center gap-0.5 rounded-box bg-primary text-primary-content border border-primary hover:bg-primary/90 transition-all cursor-pointer"
            onclick={() => (openDialog = "identity")}
            aria-label="Review athlete identities"
          >
            <span class="material-symbols-outlined" aria-hidden="true">badge</span>
            <span class="text-sm font-bold leading-none">Identity</span>
            <span class="text-[10px] text-primary-content/70 text-center leading-tight flex items-center gap-1">
              review
              {#if identityCount > 0}
                <span class="badge badge-warning badge-xs">{identityCount}</span>
              {/if}
            </span>
          </button>
          <button
            class="w-24 h-24 flex flex-col items-center justify-center gap-0.5 rounded-box bg-primary text-primary-content border border-primary hover:bg-primary/90 transition-all cursor-pointer"
            onclick={() => (openDialog = "log")}
            aria-label="View logged-in activity log"
          >
            <span class="material-symbols-outlined" aria-hidden="true">history</span>
            <span class="text-sm font-bold leading-none">Logged-in</span>
            <span class="text-[10px] text-primary-content/70 text-center leading-tight">activity</span>
          </button>
        </div>
      </div>
    </div>
  </section>

  <section aria-labelledby="band-usage" id="activity">
    <h2 id="band-usage" class="text-xs font-semibold uppercase tracking-wider text-base-content/50 mb-2">Usage</h2>
    <Activity onData={(d) => (chartData = d)} />
  </section>

  <section aria-labelledby="band-graphs" id="activity-charts">
    <h2 id="band-graphs" class="text-xs font-semibold uppercase tracking-wider text-base-content/50 mb-2">Graphs</h2>
    {#if chartData}
      <ActivityCharts
        summary={chartData.summary}
        chartColors={chartData.chartColors}
        rangeDays={chartData.rangeDays}
      />
    {/if}
  </section>
</div>

{#if openDialog === "upload"}
  <Dialog title="Upload Event" onClose={() => (openDialog = null)} maxWidth="max-w-3xl">
    <Upload />
  </Dialog>
{:else if openDialog === "users"}
  <Dialog title="User Management" onClose={() => (openDialog = null)} maxWidth="max-w-3xl">
    <Users />
  </Dialog>
{:else if openDialog === "identity"}
  <Dialog title="Identity Review" onClose={() => (openDialog = null)} maxWidth="max-w-5xl">
    <IdentityReview onCount={(n) => (identityCount = n)} />
  </Dialog>
{:else if openDialog === "log"}
  <Dialog title="Logged-in activity" onClose={() => (openDialog = null)} maxWidth="max-w-4xl">
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
