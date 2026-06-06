<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { listEvents } from "$lib/api";

  let events = $state<Array<{ id: number; name: string; start_date: string; gymnast_count: number; year: number | null }>>([]);
  let loading = $state(true);
  let filterYear = $state("");

  let yearOptions = $state<string[]>([]);
  let filteredEvents = $derived(
    filterYear ? events.filter((e) => String(e.year ?? "") === filterYear) : events
  );

  onMount(async () => {
    try {
      events = await listEvents();
      const years = new Set<string>();
      for (const e of events) {
        if (e.year) years.add(String(e.year));
      }
      yearOptions = [...years].sort().reverse();
    } catch {
      // ignore
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Events — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Events</h1>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if events.length === 0}
    <div class="card bg-base-200 mt-4">
      <div class="card-body items-center text-center py-12">
        <p class="text-base-content/70">No events uploaded yet.</p>
        <a href="/" class="btn btn-primary btn-sm mt-2">Upload an event</a>
      </div>
    </div>
  {:else}
    {#if yearOptions.length > 1}
      <div class="flex flex-wrap items-center gap-2 mb-3">
        <select class="select select-bordered select-sm" bind:value={filterYear}>
          <option value="">All years</option>
          {#each yearOptions as y}
            <option value={y}>{y}</option>
          {/each}
        </select>
        <span class="text-xs text-base-content/50">
          {filteredEvents.length} of {events.length}
        </span>
      </div>
    {/if}

    <div class="overflow-x-auto mt-4">
      <table class="table table-zebra table-pin-rows">
        <thead>
          <tr>
            <th>Name</th>
            <th>Year</th>
            <th>Date</th>
            <th>Discipline</th>
            <th class="text-right">Gymnasts</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredEvents as ev}
            <tr
              class="cursor-pointer hover:bg-base-300"
              onclick={() => goto(`/events/${ev.id}`)}
            >
              <td class="font-medium">{ev.name}</td>
              <td>{ev.year ?? ""}</td>
              <td>{ev.start_date}</td>
              <td>
                {#if ev.discipline === "WAG"}
                  <span class="badge badge-primary badge-sm">WAG</span>
                {:else if ev.discipline === "MAG"}
                  <span class="badge badge-secondary badge-sm">MAG</span>
                {:else}
                  <div class="flex gap-1">
                    <span class="badge badge-primary badge-sm">WAG</span>
                    <span class="badge badge-secondary badge-sm">MAG</span>
                  </div>
                {/if}
              </td>
              <td class="text-right">{ev.gymnast_count}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>