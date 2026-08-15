<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { page } from "$app/stores";
  import { getAllWideResults, getMedals, type MedalCounts } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import MedalBadges from "$lib/MedalBadges.svelte";
  import SeasonBest from "$lib/SeasonBest.svelte";
  import RegionBadge from "$lib/RegionBadge.svelte";
  import { REGION_PALETTES } from "$lib/regions";
  import Seo from "$lib/Seo.svelte";

  let {
    data,
  }: {
    data: { name: string; slug: string };
  } = $props();

  let filterYear = $state<string | null>(null);
  let ready = $state(false);
  let gymnastFound = $state(Boolean(data.name));
  let gymnastName = $state(data.name);
  let medals = $state<MedalCounts | null>(null);
  let medalsLoading = $state(true);
  let tabs = $state<Record<string, { columns: string[]; rows: Record<string, unknown>[] }> | null>(null);
  let defaultYearApplied = false;

  let gymnastDescription = $derived(
    gymnastName
      ? `Results, scores, and medals for ${gymnastName} — a New Zealand artistic gymnast.`
      : "New Zealand artistic gymnast results."
  );

  function applyDefaultYear() {
    if (defaultYearApplied) return;
    if (get(selectedYear) !== null) {
      defaultYearApplied = true;
      return;
    }
    const opts = get(yearOptions);
    if (!opts.length) return;
    const current = String(new Date().getFullYear());
    const target = opts.includes(current) ? current : String(Math.max(...opts.map(Number)));
    selectedYear.set(target);
    defaultYearApplied = true;
  }

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    const unsubYears = yearOptions.subscribe((opts) => {
      if (!opts.length) return;
      applyDefaultYear();
      ready = true;
    });
    const fallback = setTimeout(() => {
      if (!ready) ready = true;
    }, 4000);
    applyDefaultYear();
    return () => {
      clearTimeout(fallback);
      unsub();
      unsubYears();
    };
  });

  function mostCommon(values: string[]): string {
    const counts = new Map<string, number>();
    for (const v of values) {
      const s = v.trim();
      if (!s) continue;
      counts.set(s, (counts.get(s) ?? 0) + 1);
    }
    let best = "";
    let bestCount = 0;
    for (const [k, c] of counts) {
      if (c > bestCount) {
        best = k;
        bestCount = c;
      }
    }
    return best;
  }

  let metaRows = $derived.by(() => {
    if (!tabs) return [];
    return [...(tabs.wag?.rows ?? []), ...(tabs.mag?.rows ?? [])];
  });
  let gnzId = $derived(String(metaRows[0]?.["gnz-id"] ?? ""));
  let club = $derived(mostCommon(metaRows.map((r) => String(r.club ?? ""))));
  let region = $derived(mostCommon(metaRows.map((r) => String(r.region ?? ""))));
  let steps = $derived([
    ...new Set(metaRows.map((r) => String(r.step ?? "")).filter((s) => s)),
  ]);

  // The route param is an athlete slug (a########## optionally followed by a
  // name suffix) or a legacy gnz_id. The slug portion is sent to the backend;
  // everything else is passed through as a gnz_id.
  function identityParams(): { slug?: string; gnz_id?: string } {
    const p = $page.params.slug;
    const m = p.match(/^(a[0-9a-f]{10})(?:-[a-z0-9-]+)?$/);
    if (m) return { slug: m[1] };
    return { gnz_id: p };
  }

  $effect(() => {
    const params = identityParams();
    if (!params.slug && !params.gnz_id) return;
    medalsLoading = true;
    getMedals({
      ...params,
      ...(filterYear ? { year: parseInt(filterYear) } : {}),
    })
      .then((r) => {
        const g = r.gymnasts[0];
        medals = g?.medals ?? null;
      })
      .catch(() => {
        medals = null;
      })
      .finally(() => (medalsLoading = false));
  });

  function loadDataImpl() {
    const params = identityParams();
    if (!params.slug && !params.gnz_id) return Promise.resolve({ title: "Gymnast", tabs: {} });
    const query: { slug?: string; gnz_id?: string; year?: number } = { ...params };
    if (filterYear) query.year = parseInt(filterYear);
    return getAllWideResults(query).then((r) => {
      const rowsExist = Boolean(r.wag?.rows?.length || r.mag?.rows?.length);
      gymnastFound = rowsExist || Boolean(r.name);
      const name = r.name || r.wag?.rows[0]?.name || r.mag?.rows[0]?.name;
      gymnastName = name || "";
      return {
        title: name || "Gymnast",
        tabs: {
          ...(r.wag ? { wag: r.wag } : {}),
          ...(r.mag ? { mag: r.mag } : {}),
        },
      };
    });
  }
</script>

<Seo
  title={gymnastName || "Gymnast"}
  path={`/gymnast/${$page.params.slug}`}
  origin={$page.url.origin}
  description={gymnastDescription}
  jsonLd={{
    "@context": "https://schema.org",
    "@type": "Person",
    name: gymnastName || undefined,
    url: `${$page.url.origin}/gymnast/${$page.params.slug}`,
  }}
/>

{#snippet download({columns, rows, headerLabels, pdfColumns, colFormat})}
  <ExportMenu {columns} {rows} {headerLabels} {pdfColumns} {colFormat} title={gymnastName ? `${gymnastName} Results` : "Gymnast Results"} filename={gymnastName ? `${gymnastName} Results` : `gymnast-${$page.params.slug || "unknown"}`} />
{/snippet}

{#snippet controls()}
  {#if medalsLoading}
    <span class="loading loading-spinner loading-xs text-base-content/50" role="status" aria-label="Loading medals"></span>
  {:else}
    <MedalBadges medals={medals ?? { g: 0, s: 0, b: 0, total: 0 }} />
  {/if}
{/snippet}

{#snippet empty()}
  {#if gymnastFound}
    <div role="alert" class="alert alert-info mt-4">
      <span>There are no results for {filterYear} — try another year.</span>
    </div>
  {:else}
    <div role="alert" class="alert alert-error mt-4">
      <span>Gymnast not found</span>
    </div>
  {/if}
{/snippet}

{#snippet afterHeader()}
  {#if filterYear && tabs}
    <SeasonBest year={filterYear} {tabs} />
  {/if}
{/snippet}

{#snippet nameBadge()}
  {#if filterYear && region}
    <RegionBadge region={region} colors={REGION_PALETTES[region]} />
  {/if}
{/snippet}

{#snippet nameMeta()}
  {#if filterYear && metaRows.length}
    <div class="flex flex-col gap-0.5 text-sm text-base-content/70">
      {#if gnzId}
        <span>{gnzId}</span>
      {/if}
      {#if club}
        <a href={`/club/${encodeURIComponent(club)}`} class="link link-hover">{club}</a>
      {/if}
      {#each steps as s}
        <span>{s}</span>
      {/each}
    </div>
  {/if}
{/snippet}

{#if ready}
  <WideResultsTable
    loadData={loadDataImpl}
    loadKey={filterYear ?? ""}
    showEventFilter={true}
    stickyCol="event_name"
    extraHeadLabels={{ event_name: "Event" }}
    initialTitle={gymnastName || "Gymnast"}
    {download}
    {empty}
    {controls}
    {afterHeader}
    {nameBadge}
    {nameMeta}
    onData={(t) => (tabs = t)}
  />
{/if}
