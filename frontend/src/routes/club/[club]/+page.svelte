<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { getAllWideResults, getMedals, type MedalCounts } from "$lib/api";
  import { selectedYear } from "$lib/year";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import MedalBadges from "$lib/MedalBadges.svelte";
  import Seo from "$lib/Seo.svelte";

  let {
    data,
  }: {
    data: { name: string; region: string | null; gymnastCount: number };
  } = $props();

  let clubDescription = $derived(
    `Results and scores for ${data.name} — a New Zealand gymnastics club${data.region ? ` in the ${data.region} region` : ""}.`
  );

  let filterYear = $state<string | null>(null);
  let ready = $state(true);
  let medals = $state<MedalCounts | null>(null);
  let medalsLoading = $state(true);

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    ready = true;
    return unsub;
  });

  $effect(() => {
    const club = $page.params.club;
    if (!club) return;
    medalsLoading = true;
    getMedals({
      club,
      ...(filterYear ? { year: parseInt(filterYear) } : {}),
    })
      .then((r) => {
        const c = r.clubs[0];
        medals = c?.medals ?? null;
      })
      .catch(() => {
        medals = null;
      })
      .finally(() => (medalsLoading = false));
  });

  function loadDataImpl(opts?: { noCache?: boolean }) {
    const club = $page.params.club;
    if (!club) return Promise.resolve({ title: "Club", tabs: {} });
    const params: { club: string; year?: number } = { club };
    if (filterYear) params.year = parseInt(filterYear);
    return getAllWideResults(params, opts?.noCache).then((r) => ({
      title: club,
      tabs: {
        ...(r.wag ? { wag: r.wag } : {}),
        ...(r.mag ? { mag: r.mag } : {}),
      },
    }));
  }
</script>

<Seo
  title={data.name}
  path={`/club/${encodeURIComponent($page.params.club)}`}
  origin={$page.url.origin}
  description={clubDescription}
  jsonLd={{
    "@context": "https://schema.org",
    "@type": "SportsOrganization",
    name: data.name,
    url: `${$page.url.origin}/club/${encodeURIComponent($page.params.club)}`,
    ...(data.region ? { areaServed: data.region } : {}),
  }}
/>

{#snippet download({columns, rows, headerLabels, pdfColumns, colFormat})}
  <ExportMenu {columns} {rows} {headerLabels} {pdfColumns} {colFormat} title={$page.params.club ? `${$page.params.club} Results` : "Club Results"} filename={$page.params.club ? `${$page.params.club} Results` : "club-results"} />
{/snippet}

{#snippet controls()}
  {#if medalsLoading}
    <span class="loading loading-spinner loading-xs text-base-content/50" role="status" aria-label="Loading medals"></span>
  {:else}
    <MedalBadges medals={medals ?? { g: 0, s: 0, b: 0, total: 0 }} />
  {/if}
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Club not found</span>
  </div>
{/snippet}

{#if ready}
  <WideResultsTable
    loadData={loadDataImpl}
    loadKey={filterYear ?? ""}
    showEventFilter={true}
    extraHeadLabels={{ event_name: "Event" }}
    initialTitle={data.name}
    {download}
    {empty}
    {controls}
  />
{/if}
