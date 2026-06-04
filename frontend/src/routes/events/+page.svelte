<script lang="ts">
  import { onMount } from "svelte";
  import { listEvents } from "$lib/api";

  let events = $state<Array<{ id: number; name: string; start_date: string; gymnast_count: number }>>([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      events = await listEvents();
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Events — NZ Gymnastics Results</title>
</svelte:head>

<h1>Events</h1>

<a href="/">← Upload another</a>

{#if loading}
  <p>Loading...</p>
{:else if events.length === 0}
  <p>No events uploaded yet.</p>
{:else}
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Date</th>
        <th>Gymnasts</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each events as ev}
        <tr>
          <td>{ev.name}</td>
          <td>{ev.start_date}</td>
          <td>{ev.gymnast_count}</td>
          <td><a href="/events/{ev.id}">View</a></td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}