<script lang="ts">
  import { onMount } from "svelte";
  import { listEvents } from "$lib/api";

  let events = $state<
    Array<{
      id: number;
      name: string;
      start_date: string;
      gymnast_count: number;
    }>
  >([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      events = await listEvents();
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
    <div class="overflow-x-auto mt-4">
      <table class="table table-zebra table-pin-rows">
        <thead>
          <tr>
            <th>Name</th>
            <th>Date</th>
            <th>Discipline</th>
            <th class="text-right">Gymnasts</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each events as ev}
            <tr>
              <td class="font-medium">{ev.name}</td>
              <td>{ev.start_date}</td>
              <td>{ev.discipline}</td>
              <td class="text-right">{ev.gymnast_count}</td>
              <td
                ><a href="/events/{ev.id}" class="btn btn-ghost btn-xs">View</a
                ></td
              >
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
