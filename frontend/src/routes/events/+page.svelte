<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { listEvents, deleteEvent, renameEvent } from "$lib/api";

  let events = $state<Array<{ id: number; name: string; start_date: string; gymnast_count: number; year: number | null }>>([]);
  let loading = $state(true);
  let filterYear = $state("");
  let searchQuery = $state("");

  let yearOptions = $state<string[]>([]);
  let filteredEvents = $derived(
    events.filter((e) => {
      if (filterYear && String(e.year ?? "") !== filterYear) return false;
      if (
        searchQuery &&
        !e.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
        return false;
      return true;
    })
  );

  let renameTarget = $state<{ id: number; name: string } | null>(null);
  let renameName = $state("");
  let renaming = $state(false);

  let deleteTarget = $state<{ id: number; name: string } | null>(null);
  let deleting = $state(false);

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

  function startRename(ev: { id: number; name: string }) {
    renameTarget = ev;
    renameName = ev.name;
  }

  async function submitRename() {
    if (!renameTarget || !renameName.trim()) return;
    renaming = true;
    try {
      const updated = await renameEvent(renameTarget.id, renameName.trim());
      events = events.map((e) => (e.id === updated.id ? updated : e));
      renameTarget = null;
    } catch {
      // ignore
    } finally {
      renaming = false;
    }
  }

  function cancelRename() {
    renameTarget = null;
  }

  function startDelete(ev: { id: number; name: string }) {
    deleteTarget = ev;
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    deleting = true;
    try {
      await deleteEvent(deleteTarget.id);
      events = events.filter((e) => e.id !== deleteTarget!.id);
      deleteTarget = null;
    } catch {
      // ignore
    } finally {
      deleting = false;
    }
  }

  function cancelDelete() {
    deleteTarget = null;
  }
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
        <input
          type="search"
          placeholder="Search events..."
          class="input input-bordered input-sm"
          bind:value={searchQuery}
        />
        <span class="text-xs text-base-content/50">
          {filteredEvents.length} of {events.length}
        </span>
      </div>
    {:else if searchQuery || yearOptions.length > 0}
      <div class="flex flex-wrap items-center gap-2 mb-3">
        <input
          type="search"
          placeholder="Search events..."
          class="input input-bordered input-sm"
          bind:value={searchQuery}
        />
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
            <th class="w-20"></th>
          </tr>
        </thead>
        <tbody>
          {#each filteredEvents as ev}
            <tr>
              <td
                class="font-medium cursor-pointer hover:link"
                onclick={() => goto(`/events/${ev.id}`)}
              >
                {ev.name}
              </td>
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
              <td>
                <div class="flex gap-1">
                  <button
                    class="btn btn-ghost btn-xs"
                    title="Rename"
                    onclick={() => startRename(ev)}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      class="size-4"
                    >
                      <path d="m5.433 13.917 1.262-3.155A4 4 0 0 1 7.58 9.42l6.92-6.918a2.121 2.121 0 0 1 3 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 0 1-.65-.65Z" />
                      <path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0 0 10 3H4.75A2.75 2.75 0 0 0 2 5.75v9.5A2.75 2.75 0 0 0 4.75 18h9.5A2.75 2.75 0 0 0 17 15.25V10a.75.75 0 0 0-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5Z" />
                    </svg>
                  </button>
                  <button
                    class="btn btn-ghost btn-xs text-error"
                    title="Delete"
                    onclick={() => startDelete(ev)}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      class="size-4"
                    >
                      <path
                        fill-rule="evenodd"
                        d="M8.75 1A2.75 2.75 0 0 0 6 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 1 0 .23 1.482l.149-.022.841 10.518A2.75 2.75 0 0 0 7.596 19h4.807a2.75 2.75 0 0 0 2.742-2.53l.841-10.52.149.023a.75.75 0 0 0 .23-1.482A41.03 41.03 0 0 0 14 4.193V3.75A2.75 2.75 0 0 0 11.25 1h-2.5ZM10 4c-.84 0-1.673.025-2.5.075V3.75c0-.69.56-1.25 1.25-1.25h2.5c.69 0 1.25.56 1.25 1.25v.325C11.673 4.025 10.84 4 10 4ZM8.58 7.72a.75.75 0 0 1 .7.42l1.5 3.3a.75.75 0 0 1-.11.87l-2 2.25a.75.75 0 1 1-1.14-1l1.64-1.84-1.29-2.84a.75.75 0 0 1 .7-1.01Zm3.34.98a.75.75 0 0 1 1.07.27l1.5 2.5a.75.75 0 0 1-.06.88l-1.75 2a.75.75 0 1 1-1.16-1l1.25-1.42-1.12-1.86a.75.75 0 0 1 .27-1.07Z"
                        clip-rule="evenodd"
                      />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Rename modal -->
{#if renameTarget}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={cancelRename}>
    <div class="bg-base-100 rounded-box shadow-xl p-6 w-full max-w-md mx-4" onclick={(e) => e.stopPropagation()}>
      <h3 class="text-lg font-bold mb-4">Rename Event</h3>
      <input
        type="text"
        class="input input-bordered w-full"
        bind:value={renameName}
        onkeydown={(e) => {
          if (e.key === "Enter") submitRename();
          if (e.key === "Escape") cancelRename();
        }}
        autofocus
      />
      <div class="flex justify-end gap-2 mt-4">
        <button class="btn btn-ghost btn-sm" onclick={cancelRename}>Cancel</button>
        <button
          class="btn btn-primary btn-sm"
          onclick={submitRename}
          disabled={renaming || !renameName.trim()}
        >
          {renaming ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Delete confirmation modal -->
{#if deleteTarget}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={cancelDelete}>
    <div class="bg-base-100 rounded-box shadow-xl p-6 w-full max-w-md mx-4" onclick={(e) => e.stopPropagation()}>
      <h3 class="text-lg font-bold mb-2">Delete Event</h3>
      <p class="text-base-content/70">
        Are you sure you want to delete <strong>"{deleteTarget.name}"</strong>?
        This cannot be undone.
      </p>
      <div class="flex justify-end gap-2 mt-4">
        <button class="btn btn-ghost btn-sm" onclick={cancelDelete}>Cancel</button>
        <button
          class="btn btn-error btn-sm"
          onclick={confirmDelete}
          disabled={deleting}
        >
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </div>
  </div>
{/if}
