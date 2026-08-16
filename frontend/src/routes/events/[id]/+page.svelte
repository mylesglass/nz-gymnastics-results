<script lang="ts">
  import { page } from "$app/stores";
  import { getWideResults } from "$lib/api";
  import WideResultsTable from "$lib/WideResultsTable.svelte";
  import ExportMenu from "$lib/ExportMenu.svelte";
  import Seo from "$lib/Seo.svelte";
  import type { EventDetailData } from "./+page.server";

  let {
    data,
  }: {
    data: { event: EventDetailData };
  } = $props();

  let eventName = $state(data.event.name);

  let eventDescription = $derived(
    `Full results for ${data.event.name} (${data.event.year ?? ""}) — ${data.event.discipline} gymnastics, ${data.event.gymnast_count} gymnasts${data.event.host_club ? `, hosted by ${data.event.host_club}` : ""}.`
  );

  let sportsEventLd = $derived({
    "@context": "https://schema.org",
    "@type": "SportsEvent",
    name: data.event.name,
    startDate: data.event.start_date,
    ...(data.event.end_date ? { endDate: data.event.end_date } : {}),
    inLanguage: "en",
    sport: "Artistic Gymnastics",
    about: { "@type": "Thing", name: `${data.event.discipline} Artistic Gymnastics` },
    ...(data.event.host_club
      ? { location: { "@type": "Place", name: data.event.host_club } }
      : {}),
  });

  function loadData(opts?: { noCache?: boolean }) {
    const id = Number($page.params.id);
    return getWideResults(id, opts?.noCache).then((r) => {
      eventName = r.event.name;
      return {
        title: r.event.name,
        tabs: {
          ...(r.wag ? { wag: r.wag } : {}),
          ...(r.mag ? { mag: r.mag } : {}),
        },
      };
    });
  }
</script>

<Seo
  title={data.event.name}
  path={`/events/${data.event.id}`}
  origin={$page.url.origin}
  description={eventDescription}
  jsonLd={sportsEventLd}
/>

{#snippet download({columns, rows, headerLabels, pdfColumns, colFormat})}
  <ExportMenu {columns} {rows} {headerLabels} {pdfColumns} {colFormat} title={eventName || "Event Results"} filename={eventName ? `${eventName} Results` : `event-${$page.params.id}`} />
{/snippet}

{#snippet empty()}
  <div role="alert" class="alert alert-error mt-4">
    <span>Event not found</span>
  </div>
{/snippet}

<WideResultsTable {loadData} {download} {empty} eventId={Number($page.params.id)} initialTitle={data.event.name} />
