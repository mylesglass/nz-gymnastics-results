<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { listEvents, deleteEvent, updateEvent, type EventSummary } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { selectedYear } from "$lib/year";

  let events = $state<EventSummary[]>([]);
  let loading = $state(true);
  let filterYear = $state<string | null>(null);
  let searchQuery = $state("");
  let loggedIn = $state(false);

  let sortCol = $state("start_date");
  let sortAsc = $state(false);

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    return unsub;
  });

  function sorted<T>(items: T[], col: string, asc: boolean): T[] {
    return [...items].sort((a, b) => {
      const va = (a as Record<string, unknown>)[col];
      const vb = (b as Record<string, unknown>)[col];
      const aStr = String(va ?? "");
      const bStr = String(vb ?? "");
      let cmp: number;
      if (typeof va === "number" && typeof vb === "number") {
        cmp = va - vb;
      } else {
        cmp = aStr.localeCompare(bStr, undefined, { numeric: true });
      }
      return asc ? cmp : -cmp;
    });
  }

  let filteredEvents = $derived(
    sorted(
      events.filter((e) => {
        if (filterYear && String(e.year ?? "") !== filterYear) return false;
        if (
          searchQuery &&
          !e.name.toLowerCase().includes(searchQuery.toLowerCase())
        )
          return false;
        return true;
      }),
      sortCol,
      sortAsc
    )
  );

  function toggleSort(col: string) {
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = false;
    }
  }

  let editTarget = $state<{ id: number; name: string; is_national?: boolean } | null>(null);
  let editName = $state("");
  let editNational = $state(false);
  let editSaving = $state(false);
  let showDeleteConfirm = $state(false);
  let editDeleting = $state(false);

  onMount(async () => {
    try {
      events = await listEvents();
    } catch {
      // ignore
    } finally {
      loading = false;
    }
    const unsub = currentUser.subscribe((v) => (loggedIn = v?.role === "admin"));
    return unsub;
  });

  function startEdit(ev: EventSummary) {
    editTarget = ev;
    editName = ev.name;
    editNational = ev.is_national ?? false;
    showDeleteConfirm = false;
  }

  function cancelEdit() {
    editTarget = null;
  }

  async function submitEdit() {
    if (!editTarget || !editName.trim()) return;
    editSaving = true;
    try {
      const updated = await updateEvent(editTarget.id, { name: editName.trim(), is_national: editNational });
      events = events.map((e) => (e.id === updated.id ? updated : e));
      editTarget = null;
    } catch {
      // ignore
    } finally {
      editSaving = false;
    }
  }

  async function confirmEditDelete() {
    if (!editTarget) return;
    editDeleting = true;
    try {
      await deleteEvent(editTarget.id);
      events = events.filter((e) => e.id !== editTarget!.id);
      editTarget = null;
    } catch {
      // ignore
    } finally {
      editDeleting = false;
    }
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
        <a href="/upload" class="btn btn-primary btn-sm mt-2">Upload an event</a>
      </div>
    </div>
  {:else}
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

    <div class="overflow-x-auto mt-4">
      <table class="table table-zebra table-pin-rows">
        <thead>
          <tr>
            <th class="cursor-pointer hover:text-primary" onclick={() => toggleSort("name")}>
              Name
              {#if sortCol === "name"}<span class="ml-1 text-xs">{sortAsc ? "▲" : "▼"}</span>{/if}
            </th>
            <th class="cursor-pointer hover:text-primary" onclick={() => toggleSort("year")}>
              Year
              {#if sortCol === "year"}<span class="ml-1 text-xs">{sortAsc ? "▲" : "▼"}</span>{/if}
            </th>
            <th class="cursor-pointer hover:text-primary" onclick={() => toggleSort("start_date")}>
              Date
              {#if sortCol === "start_date"}<span class="ml-1 text-xs">{sortAsc ? "▲" : "▼"}</span>{/if}
            </th>
            <th class="cursor-pointer hover:text-primary" onclick={() => toggleSort("discipline")}>
              Discipline
              {#if sortCol === "discipline"}<span class="ml-1 text-xs">{sortAsc ? "▲" : "▼"}</span>{/if}
            </th>
            <th class="text-right cursor-pointer hover:text-primary" onclick={() => toggleSort("gymnast_count")}>
              Gymnasts
              {#if sortCol === "gymnast_count"}<span class="ml-1 text-xs">{sortAsc ? "▲" : "▼"}</span>{/if}
            </th>
            {#if loggedIn}
              <th class="w-20"></th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each filteredEvents as ev}
            <tr>
              <td
                class="font-medium cursor-pointer hover:link"
                onclick={() => goto(`/events/${ev.id}`)}
              >
                <span class="inline-flex items-center gap-2">
                  {ev.name}
                  {#if ev.is_national}
                    <span class="badge badge-accent badge-sm whitespace-nowrap">Nationals</span>
                  {/if}
                </span>
              </td>
              <td>{ev.year ?? ""}</td>
              <td>{ev.start_date}</td>
              <td>
                {#if ev.discipline === "WAG"}
                  <span class="badge badge-primary badge-sm">WAG</span>
                {:else if ev.discipline === "MAG"}
                  <span class="badge badge-secondary badge-sm">MAG</span>
                {:else}
                  <div class="flex gap-1 items-center">
                    <span class="badge badge-primary badge-sm">WAG</span>
                    <span class="badge badge-secondary badge-sm">MAG</span>
                  </div>
                {/if}
              </td>
              <td class="text-right">{ev.gymnast_count}</td>
              {#if loggedIn}
              <td>
                <button
                  class="btn btn-ghost btn-xs"
                  title="Edit"
                  onclick={() => startEdit(ev)}
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
              </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Edit modal -->
{#if editTarget}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={cancelEdit}>
    <div class="bg-base-100 rounded-box shadow-xl p-6 w-full max-w-md mx-4" onclick={(e) => e.stopPropagation()}>
      {#if showDeleteConfirm}
        <h3 class="text-lg font-bold mb-2">Delete Event</h3>
        <p class="text-base-content/70">
          Are you sure you want to delete <strong>"{editTarget.name}"</strong>?
          This cannot be undone.
        </p>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-ghost btn-sm" onclick={() => (showDeleteConfirm = false)}>Cancel</button>
          <button
            class="btn btn-error btn-sm"
            onclick={confirmEditDelete}
            disabled={editDeleting}
          >
            {editDeleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      {:else}
        <h3 class="text-lg font-bold mb-4">Edit Event</h3>
        <input
          type="text"
          class="input input-bordered w-full"
          bind:value={editName}
          onkeydown={(e) => {
            if (e.key === "Enter") submitEdit();
            if (e.key === "Escape") cancelEdit();
          }}
          autofocus
        />
        <label class="flex items-start gap-3 mt-4 cursor-pointer">
          <input type="checkbox" class="checkbox checkbox-sm mt-0.5" bind:checked={editNational} />
          <div>
            <div class="flex items-center gap-1.5 font-medium text-sm">
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 48 48" fill="currentColor" class="size-4">
                <path fill-rule="evenodd" d="M12 7a1 1 0 0 1 1-1h22a1 1 0 0 1 1 1v1h5a1 1 0 0 1 1 1v6a5 5 0 0 1-5 5h-1.683A12.02 12.02 0 0 1 26 27.834V34h6a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H16a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h6v-6.166A12.02 12.02 0 0 1 12.683 20H11a5 5 0 0 1-5-5V9a1 1 0 0 1 1-1h5zm24 9v-6h4v5a3 3 0 0 1-3 3h-1zm-24-6H8v5a3 3 0 0 0 3 3h1z" clip-rule="evenodd" />
              </svg>
              National Event
            </div>
            <p class="text-xs text-base-content/50 mt-0.5">excluded from ranking lists</p>
          </div>
        </label>
        <div class="flex justify-between items-center mt-6">
          <button
            class="btn btn-error btn-sm"
            onclick={() => (showDeleteConfirm = true)}
          >
            Delete event
          </button>
          <div class="flex gap-2">
            <button class="btn btn-ghost btn-sm" onclick={cancelEdit}>Cancel</button>
            <button
              class="btn btn-primary btn-sm"
              onclick={submitEdit}
              disabled={editSaving || !editName.trim()}
            >
              {editSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
