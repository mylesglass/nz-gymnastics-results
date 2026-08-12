<script lang="ts">
  import { onMount } from "svelte";
  import { listGymnasts, getMedals } from "$lib/api";
  import type { GymnastMedals } from "$lib/api";
  import { selectedYear } from "$lib/year";
  import MedalBadges from "$lib/MedalBadges.svelte";

  interface Gymnast {
    slug?: string;
    gnz_id: string;
    name: string;
    club: string | null;
    alt_ids: string[];
    alt_clubs: string[];
  }

  let gymnasts = $state<Gymnast[]>([]);
  let loading = $state(true);
  let search = $state("");
  let activeLetter = $state("");
  let scrolled = $state(false);
  let filterYear = $state<string | null>(null);
  let gymnastMedals = $state<Record<string, GymnastMedals>>({});

  let filtered = $derived(
    search
      ? gymnasts.filter(g => g.name.toLowerCase().includes(search.toLowerCase()))
      : gymnasts
  );

  onMount(() => {
    const unsub = selectedYear.subscribe((v) => (filterYear = v));
    return unsub;
  });

  $effect(() => {
    loading = true;
    listGymnasts(filterYear ? { year: parseInt(filterYear) } : {})
      .then((g) => (gymnasts = g))
      .catch(() => (gymnasts = []))
      .finally(() => (loading = false));
  });

  $effect(() => {
    getMedals(filterYear ? { year: parseInt(filterYear) } : {})
      .then((r) => (gymnastMedals = Object.fromEntries(r.gymnasts.map((g) => [g.slug || g.gnz_id, g]))))
      .catch(() => (gymnastMedals = {}));
  });

  let grouped = $derived.by(() => {
    const g: Record<string, Gymnast[]> = {};
    for (const gr of filtered) {
      const letter = gr.name.charAt(0).toUpperCase();
      if (!/[A-Z]/.test(letter)) continue;
      if (!g[letter]) g[letter] = [];
      g[letter].push(gr);
    }
    const sorted: Record<string, Gymnast[]> = {};
    for (const k of Object.keys(g).sort()) {
      sorted[k] = g[k];
    }
    return sorted;
  });

  function displayIds(gr: Gymnast): string {
    const all = [gr.gnz_id, ...gr.alt_ids];
    return all.join(", ");
  }

  function scrollToLetter(letter: string) {
    document.getElementById(`letter-${letter}`)?.scrollIntoView({ behavior: "smooth" });
    setTimeout(updateActiveLetter, 400);
  }

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function updateActiveLetter() {
    const headerOffset = 140;
    let current = "";
    for (const letter of Object.keys(grouped)) {
      const el = document.getElementById(`letter-${letter}`);
      if (!el) continue;
      if (el.getBoundingClientRect().top <= headerOffset) {
        current = letter;
      } else {
        break;
      }
    }
    activeLetter = current;
  }

  onMount(() => {
    const onScroll = () => {
      updateActiveLetter();
      scrolled = window.scrollY > 8;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    updateActiveLetter();
    return () => window.removeEventListener("scroll", onScroll);
  });

</script>

<svelte:head>
  <title>Gymnasts — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <div class="sticky top-4 z-10 rounded-box bg-base-200/80 backdrop-blur border border-base-300/50 p-4 mb-6 transition-all">
    <div class="flex items-center justify-between">
      <h1
        class="font-bold transition-all"
        class:text-3xl={!scrolled}
        class:text-lg={scrolled}
        class:mb-3={!scrolled}
        class:mb-1={scrolled}
      >Gymnasts</h1>
      {#if scrolled}
        <button
          class="btn btn-ghost btn-xs gap-1 transition-opacity"
          aria-label="Back to top"
          title="Back to top"
          onclick={scrollToTop}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-3.5 fill-current" aria-hidden="true">
            <path d="M12 19.5a1 1 0 0 1-1-1V7.828l-3.793 3.793a1 1 0 0 1-1.414-1.414l5.5-5.5a1 1 0 0 1 1.414 0l5.5 5.5a1 1 0 0 1-1.414 1.414L13 7.828V18.5a1 1 0 0 1-1 1Z"/>
          </svg>
          Back to top
        </button>
      {/if}
    </div>
    <div class="flex items-center justify-between gap-4">
      <p class="text-base-content/70 text-sm shrink-0">
        {filtered.length} gymnast{filtered.length === 1 ? "" : "s"}
        {#if search}(filtered){/if}
      </p>
      <nav
        class="flex-1 flex-wrap justify-center gap-0.5 hidden md:flex"
        aria-label="Jump to letter"
      >
        {#each Object.keys(grouped) as letter}
          <button
            class="text-xs font-medium leading-none px-1.5 py-1 rounded hover:bg-base-300 transition-colors cursor-pointer"
            class:bg-primary={activeLetter === letter}
            class:text-primary-content={activeLetter === letter}
            aria-current={activeLetter === letter ? "true" : undefined}
            onclick={() => scrollToLetter(letter)}
          >
            {letter}
          </button>
        {/each}
      </nav>
      <div class="relative w-full max-w-56 md:max-w-xs shrink-0">
        <label for="gymnast-search" class="sr-only">Search gymnasts</label>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-base-content/60 pointer-events-none z-10" aria-hidden="true">
          <path fill="currentColor" d="M6.175 10.825Q5 9.65 5 8t1.175-2.825T9 4t2.825 1.175T13 8t-1.175 2.825T9 12t-2.825-1.175M18.413 18.5q.562-.5.587-1.5q.025-.85-.562-1.425T17 15t-1.425.575T15 17t.575 1.425T17 19t1.413-.5M21.6 23l-2.55-2.55q-.45.275-.962.413T17 21q-1.65 0-2.825-1.175T13 17t1.175-2.825T17 13t2.825 1.175T21 17q0 .575-.137 1.088t-.413.962L23 21.6zM1 20v-2.8q0-.85.438-1.562T2.6 14.55q1.55-.775 3.15-1.162T9 13q.8 0 1.613.088t1.612.287q-.6.8-.912 1.725T11 17q0 .8.2 1.563T11.8 20zm16.825-9.175Q16.65 12 15 12q-.275 0-.7-.062t-.7-.138q.675-.8 1.038-1.775T15 8t-.362-2.025T13.6 4.2q.35-.125.7-.163T15 4q1.65 0 2.825 1.175T19 8t-1.175 2.825"/>
        </svg>
        <input
          id="gymnast-search"
          type="text"
          placeholder="Search gymnasts..."
          class="input input-bordered input-sm w-full pl-8"
          bind:value={search}
        />
      </div>
    </div>
  </div>

  {#if loading}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {#each [1, 2, 3, 4, 5, 6] as _}
        <div class="card bg-base-200 animate-pulse">
          <div class="card-body">
            <div class="h-4 bg-base-300 rounded w-3/4 mb-2"></div>
            <div class="h-3 bg-base-300 rounded w-1/2"></div>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    {#each Object.entries(grouped) as [letter, letterGymnasts]}
      <div class="mb-6 scroll-mt-[140px]" id="letter-{letter}">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-lg font-bold">{letter}</span>
          <span class="text-xs text-base-content/70">({letterGymnasts.length})</span>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-1">
          {#each letterGymnasts as gr}
            <a
              href="/gymnast/{gr.slug || gr.gnz_id}"
              class="flex flex-col px-3 py-1.5 rounded hover:bg-base-200 transition-colors"
            >
              <span class="flex items-center gap-1">
                <span class="flex items-center gap-1 min-w-0">
                  <span class="text-sm font-medium truncate">{gr.name}</span>
                  {#if gr.alt_ids.length > 0}
                    <span class="text-warning text-xs shrink-0">⚠</span>
                  {/if}
                </span>
                <span class="ml-auto flex items-center gap-2 shrink-0">
                  {#if gymnastMedals[gr.slug || gr.gnz_id]}
                    <MedalBadges size="xs" showEmpty={false} medals={gymnastMedals[gr.slug || gr.gnz_id].medals} />
                  {/if}
                  <span class="badge badge-ghost badge-xs font-mono">{displayIds(gr)}</span>
                </span>
              </span>
              <span class="text-xs leading-snug mt-0.5">
                {#each (gr.alt_clubs.length > 0 ? [gr.club, ...gr.alt_clubs].filter(Boolean) : gr.club ? [gr.club] : []) as clubName, i}
                  <span class="{clubName === gr.club ? 'text-base-content/70' : 'text-base-content/60'}">{i > 0 ? ", " : ""}{clubName}</span>
                {:else}
                  <span class="text-base-content/30">—</span>
                {/each}
              </span>
            </a>
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
