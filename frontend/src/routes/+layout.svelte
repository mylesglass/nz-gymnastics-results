<script lang="ts">
  import { onMount } from "svelte";
  import type { Snippet } from "svelte";
  import { updated } from "$app/state";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { currentUser, authConfigured, logout, hasPermission, setPermissions, getToken, PERMISSIONS } from "$lib/auth";
  import { checkAuthStatus, listYears, me, trackPage } from "$lib/api";
  import { selectedYear, yearOptions } from "$lib/year";
  import "../app.css";

  let { children }: { children: Snippet } = $props();

  const THEMES = [
    "light", "dark", "cupcake", "bumblebee", "emerald", "corporate",
    "synthwave", "retro", "cyberpunk", "valentine", "halloween",
    "garden", "forest", "aqua", "lofi", "pastel", "fantasy",
    "wireframe", "black", "luxury", "dracula", "cmyk", "autumn",
    "business", "acid", "lemonade", "night", "coffee", "winter",
    "dim", "nord", "sunset", "caramellatte", "abyss", "silk",
  ];
  let theme = $state("light");
  let user = $state<{ username: string; role: string; permissions: string[] } | null>(null);
  let authCfg = $state(false);
  let authResolved = $state(false);
  let authRedirectTarget = $state("/");
  let currentPath = $derived($page.url.pathname);
  let selYear = $state<string | null>(null);
  let years = $state<string[]>([]);

  let canNational = $derived(hasPermission(user, PERMISSIONS.national));
  let canWellington = $derived(hasPermission(user, PERMISSIONS.wellington));
  let canRankings = $derived(canNational || canWellington);

  let requiresAuth = $derived(
    currentPath.startsWith("/admin") ||
    currentPath.startsWith("/rankings") ||
    currentPath === "/wellington-ranking"
  );
  let authActive = $derived(authResolved && authCfg);
  let routeAllowed = $derived(
    !authActive ||
    (currentPath.startsWith("/admin") && user?.role === "admin") ||
    (currentPath.startsWith("/rankings") && hasPermission(user, PERMISSIONS.national)) ||
    (currentPath === "/wellington-ranking" && hasPermission(user, PERMISSIONS.wellington))
  );
  let renderChildren = $derived(!requiresAuth || (authActive && routeAllowed));

  let showYearTabs = $derived(
    currentPath === "/events" ||
    currentPath === "/results" ||
    currentPath.startsWith("/rankings") ||
    currentPath === "/wellington-ranking" ||
    currentPath === "/gymnasts" ||
    currentPath.startsWith("/gymnast/") ||
    currentPath.startsWith("/club/")
  );

  onMount(() => {
    theme = document.documentElement.dataset.theme || "light";
    const unsub1 = currentUser.subscribe((v) => (user = v));
    const unsub2 = authConfigured.subscribe((v) => (authCfg = v));
    const unsub3 = selectedYear.subscribe((v) => (selYear = v));
    const unsub4 = yearOptions.subscribe((v) => (years = v));
    const authTasks: Promise<void>[] = [
      checkAuthStatus()
        .then((s) => {
          authConfigured.set(s.configured);
        })
        .catch(() => {}),
    ];
    if (getToken()) {
      authTasks.push(
        me()
          .then((u) => setPermissions(u.permissions))
          .catch((err: Error & { status?: number }) => {
            if (err.status === 401) {
              logout();
              authRedirectTarget = "/login";
            }
          })
      );
    }
    Promise.allSettled(authTasks).then(() => {
      authResolved = true;
    });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && drawerOpen) {
        drawerOpen = false;
        document.getElementById("nav-menu-button")?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    listYears()
      .then((r) => yearOptions.set(r.years.map(String)))
      .catch(() => {});
    return () => {
      document.removeEventListener("keydown", onKey);
      unsub1();
      unsub2();
      unsub3();
      unsub4();
    };
  });

  function setTheme(t: string) {
    theme = t;
    document.documentElement.dataset.theme = t;
    localStorage.setItem("theme", t);
  }

  function active(path: string) {
    return currentPath === path || currentPath.startsWith(path + "/")
  }

  let drawerOpen = $state(false);

  function closeDrawer() {
    drawerOpen = false;
  }

  function handleNavClick() {
    if (window.innerWidth < 768) {
      closeDrawer();
    }
  }

  $effect(() => {
    if (requiresAuth && authActive && !routeAllowed) {
      goto(authRedirectTarget);
    }
  });

  let lastTracked = "";
  $effect(() => {
    if (!authCfg) return;
    const path = currentPath + $page.url.search;
    const key = user ? `${user.username}|${path}` : `anon|${path}`;
    if (key === lastTracked) return;
    lastTracked = key;
    trackPage(path).catch(() => {});
  });

  let updateDismissed = $state(false);
  onMount(() => {
    updated.check().catch(() => {});
    const onVisible = () => {
      if (document.visibilityState === "visible") updated.check().catch(() => {});
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  });
</script>

<div class="drawer">
  <input
    id="nav-drawer"
    type="checkbox"
    class="drawer-toggle"
    aria-label="Toggle navigation menu"
    bind:checked={drawerOpen}
  />
  <div class="drawer-content flex flex-col min-h-screen">
    {#if updated.current && !updateDismissed}
      <div role="status" aria-live="polite" class="sticky top-0 z-[60] bg-primary text-primary-content text-sm px-4 py-2 flex items-center justify-center gap-3">
        <span>A new version of this site is available — reload to see the latest results and features.</span>
        <button
          type="button"
          class="btn btn-sm btn-secondary"
          onclick={() => location.reload()}
        >
          Reload
        </button>
        <button
          type="button"
          class="btn btn-sm btn-ghost btn-square"
          aria-label="Dismiss update notice"
          onclick={() => (updateDismissed = true)}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" class="size-4 fill-current" aria-hidden="true"><path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" /></svg>
        </button>
      </div>
    {/if}
    <a
      href="#main"
      class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:btn focus:btn-primary focus:btn-sm"
    >
      Skip to content
    </a>
    <nav class="navbar bg-base-200 shadow-sm flex-none relative z-50 overflow-visible" aria-label="Main navigation">
      <div class="flex-1 gap-1 items-center min-w-0">
        <button
          id="nav-menu-button"
          type="button"
          class="btn btn-ghost btn-sm btn-square md:hidden shrink-0"
          aria-label="Open menu"
          aria-expanded={drawerOpen}
          aria-controls="nav-drawer"
          onclick={() => (drawerOpen = !drawerOpen)}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-5 fill-current" aria-hidden="true">
            <path d="M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z" />
          </svg>
        </button>
        <a href="/" class="btn btn-ghost text-lg sm:text-xl min-w-0">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-6 text-primary shrink-0">
            <path fill="currentColor" d="M8 22h5v-4H6v2q0 .825.588 1.413T8 22m7 0h5q.825 0 1.413-.587T22 20v-2h-7zM2 18V4q0-.825.588-1.412T4 2h14v2H4v14zm4-2h7v-4H6zm9 0h7v-4h-7zm-9-6h16V8q0-.825-.587-1.412T20 6H8q-.825 0-1.412.588T6 8z"/>
          </svg>
          <span class="hidden sm:inline truncate">NZ Gymnastics Results</span>
          <span class="badge badge-warning badge-sm hidden sm:inline">Beta</span>
        </a>
      </div>

      {#if showYearTabs}
      <div class="flex-none">
        <div class="hidden md:block">
          <div class="tabs tabs-box tabs-xs" aria-label="Year filter">
            {#each years as yr}
              <input
                type="radio"
                name="year_tabs"
                class="tab checked:bg-secondary checked:text-secondary-content"
                aria-label={yr}
                checked={selYear === yr}
                onchange={() => selectedYear.set(yr)}
              />
            {/each}
            <input
              type="radio"
              name="year_tabs"
              class="tab checked:bg-secondary checked:text-secondary-content"
              aria-label="All"
              checked={selYear === null}
              onchange={() => selectedYear.set(null)}
            />
          </div>
        </div>
        <div class="md:hidden">
          <label for="nav-year-select" class="sr-only">Select year</label>
          <select
            id="nav-year-select"
            class="select select-bordered select-sm"
            value={selYear ?? ""}
            onchange={(e) => selectedYear.set((e.currentTarget as HTMLSelectElement).value || null)}
          >
            <option value="">All</option>
            {#each years as yr}
              <option value={yr}>{yr}</option>
            {/each}
          </select>
        </div>
      </div>
      {/if}

      <div class="flex-1 flex justify-end gap-1 items-center min-w-0">
        <div class="hidden md:flex gap-1 items-center">
          <a
            href="/events"
            class="btn btn-sm {active('/events') ? 'btn-primary' : 'btn-ghost'}"
            aria-current={active("/events") ? "page" : undefined}
          >
            Events
          </a>
          <a
            href="/results"
            class="btn btn-sm {active('/results') ? 'btn-primary' : 'btn-ghost'}"
            aria-current={active("/results") ? "page" : undefined}
          >
            Results
          </a>
          <a
            href="/gymnasts"
            class="btn btn-sm {active('/gymnasts') || currentPath.startsWith('/gymnast/') ? 'btn-primary' : 'btn-ghost'}"
            aria-current={active("/gymnasts") || currentPath.startsWith("/gymnast/") ? "page" : undefined}
          >
            Gymnasts
          </a>
          <a
            href="/clubs"
            class="btn btn-sm {active('/clubs') || currentPath.startsWith('/club/') ? 'btn-primary' : 'btn-ghost'}"
            aria-current={active("/clubs") || currentPath.startsWith("/club/") ? "page" : undefined}
          >
            Clubs
          </a>
          {#if canRankings}
            <div class="dropdown dropdown-hover dropdown-end" style="z-index: 100">
              <button
                class="btn btn-sm {active('/rankings') || active('/wellington-ranking') ? 'btn-primary' : 'btn-ghost'}"
                aria-haspopup="menu"
                aria-expanded={false}
                onclick={() => goto(canNational ? '/rankings' : '/wellington-ranking')}
              >
                Rankings
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" class="size-3 fill-current opacity-60" aria-hidden="true"><path fill-rule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" /></svg>
              </button>
              <ul role="menu" aria-label="Rankings" class="dropdown-content menu bg-base-100 rounded-box w-52 p-2 shadow">
                {#if canNational}
                  <li role="none"><a role="menuitem" href="/rankings" class={active('/rankings') && currentPath === "/rankings" ? 'active' : ''}>National Rankings</a></li>
                {/if}
                {#if canNational}
                  <li role="none"><a role="menuitem" href="/rankings/apparatus" class={active('/rankings/apparatus') ? 'active' : ''}>Apparatus Rankings</a></li>
                {/if}
                {#if canWellington}
                  <li role="none"><a role="menuitem" href="/wellington-ranking" class={active('/wellington-ranking') ? 'active' : ''}>Wellington Rankings</a></li>
                {/if}
              </ul>
            </div>
          {/if}
        </div>

        {#if authCfg}
          {#if user}
            <div class="dropdown dropdown-end">
              <button
                type="button"
                class="badge badge-primary badge-sm gap-1 px-3 py-3 cursor-pointer hover:opacity-80 transition-opacity select-none"
                aria-haspopup="menu"
                aria-expanded={false}
              >
                {user.username}
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" class="size-3 fill-current opacity-60" aria-hidden="true"><path fill-rule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" /></svg>
              </button>
              <ul tabindex="0" role="menu" aria-label="User menu" class="dropdown-content menu bg-base-100 rounded-box w-48 p-2 shadow" style="z-index: 50">
                <li role="none"><span class="text-xs text-base-content/70 px-3 py-1">{user.role}</span></li>
                {#if user?.role === "admin"}
                  <li role="none"><a role="menuitem" href="/admin" class={active("/admin") && currentPath === "/admin" ? 'active' : ''}>Dashboard</a></li>
                  <li role="none"><a role="menuitem" href="/admin/activity" class={active("/admin/activity") ? 'active' : ''}>Activity</a></li>
                  <li role="none"><a role="menuitem" href="/upload" class={active("/upload") ? 'active' : ''}>Upload</a></li>
                {/if}
                <li role="none" class="border-t border-base-300 mt-1 pt-1">
                  <button role="menuitem" onclick={() => { logout(); goto("/"); }}>
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          {:else}
            <a href="/login" class="btn btn-ghost btn-sm">Login</a>
          {/if}
        {/if}
      </div>
    </nav>

    <main id="main" class="mx-auto grow shrink-0 basis-auto w-full max-w-full px-4 pt-6">
      {#if renderChildren}
        {@render children()}
      {/if}
    </main>

    <footer class="flex-none bg-base-200 text-base-content px-8 py-10 mt-8">
      <div class="max-w-7xl mx-auto">
        <p class="font-bold text-lg">NZ Gymnastics Results</p>
        <p class="max-w-md text-sm">
          A community tool for viewing and sharing New Zealand gymnastics competition results.
          Built with open-source tools.
        </p>
        <div class="flex gap-4 mt-3">
          <a
            href="https://github.com/mylesglass/nz-gymnastics-results"
            target="_blank"
            rel="noopener noreferrer"
            class="btn btn-outline btn-xs"
          >
            <svg viewBox="0 0 24 24" class="size-4 fill-current"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
            View on GitHub
          </a>
          <a
            href="https://ko-fi.com/mylesglass"
            target="_blank"
            rel="noopener noreferrer"
            class="btn btn-primary btn-xs"
          >
            ☕ Support on Ko-fi
          </a>
        </div>
        <p class="text-xs text-base-content/70 mt-3">
          If this has saved you time, consider donating to cover development costs.
        </p>
        <p class="text-xs text-base-content/70 mt-1">
          Found a bug? Email
          <a href="mailto:myles@hcg.org.nz" class="link">myles@hcg.org.nz</a>.
        </p>
      </div>
      <div class="flex justify-end mt-4">
        <div class="dropdown dropdown-top dropdown-end">
          <button class="btn btn-ghost btn-xs gap-2" aria-label={`Select theme, current: ${theme}`}>
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="size-4 fill-current">
              <path d="M11 22q-.825 0-1.412-.587T9 20v-4H6q-.825 0-1.412-.587T4 14V7q0-1.65 1.175-2.825T8 3h12v11q0 .825-.587 1.413T18 16h-3v4q0 .825-.587 1.413T13 22zM6 10h12V5h-1v4h-2V5h-1v2h-2V5H8q-.825 0-1.412.588T6 7z"/>
            </svg>
            {theme}
          </button>
          <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box w-96 max-w-[calc(100vw-2rem)] p-2 shadow flex-row flex-wrap gap-x-4 gap-y-1" style="z-index: 50">
            {#each THEMES as t}
              <li class="w-1/3">
                <button class={t === theme ? "active" : ""} onclick={() => setTheme(t)}>
                  <span data-theme={t} class="inline-flex items-center gap-0.5 shrink-0 rounded-full border px-1.5 py-0.5" style="background: var(--color-base-100); border-color: var(--color-base-300)">
                    <span class="size-2.5 rounded-full" style="background: var(--color-primary)"></span>
                    <span class="size-2.5 rounded-full" style="background: var(--color-secondary)"></span>
                  </span>
                  {t}
                </button>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    </footer>
  </div>

  <div class="drawer-side z-50">
    <label for="nav-drawer" class="drawer-overlay" aria-label="Close menu"></label>
    <nav aria-label="Mobile menu" class="h-full">
      <ul class="menu bg-base-200 min-h-full w-72 p-4 gap-1 text-base-content">
      <li class="mb-2">
        <a href="/" class="flex items-center gap-2 py-2" onclick={handleNavClick} aria-label="NZ Gymnastics Results home">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-6 text-primary shrink-0">
            <path fill="currentColor" d="M8 22h5v-4H6v2q0 .825.588 1.413T8 22m7 0h5q.825 0 1.413-.587T22 20v-2h-7zM2 18V4q0-.825.588-1.412T4 2h14v2H4v14zm4-2h7v-4H6zm9 0h7v-4h-7zm-9-6h16V8q0-.825-.587-1.412T20 6H8q-.825 0-1.412.588T6 8z"/>
          </svg>
          <span class="text-lg font-bold leading-tight">NZ Gymnastics Results</span>
          <span class="badge badge-warning badge-sm">Beta</span>
        </a>
      </li>
      <li>
        <a href="/events" onclick={handleNavClick} class:active={active("/events")} aria-current={active("/events") ? "page" : undefined}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 fill-current"><path fill="currentColor" d="M14.5 18q-1.05 0-1.775-.725T12 15.5t.725-1.775T14.5 13t1.775.725T17 15.5t-.725 1.775T14.5 18M5 22q-.825 0-1.412-.587T3 20V6q0-.825.588-1.412T5 4h1V2h2v2h8V2h2v2h1q.825 0 1.413.588T21 6v14q0 .825-.587 1.413T19 22zm0-2h14V10H5z"/></svg>
          Events
        </a>
      </li>
      <li>
        <a href="/results" onclick={handleNavClick} class:active={active("/results")} aria-current={active("/results") ? "page" : undefined}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 fill-current"><path fill="currentColor" d="M21 5c0-1.103-.897-2-2-2H5c-1.103 0-2 .897-2 2v14c0 1.103.897 2 2 2h14c1.103 0 2-.897 2-2zM5 19V5h14l.002 14z"/><path fill="currentColor" d="M7 7h1.998v2H7zm4 0h6v2h-6zm-4 4h1.998v2H7zm4 0h6v2h-6zm-4 4h1.998v2H7zm4 0h6v2h-6z"/></svg>
          Results
        </a>
      </li>
      <li>
        <a href="/gymnasts" onclick={handleNavClick} class:active={active("/gymnasts") || currentPath.startsWith("/gymnast/")} aria-current={active("/gymnasts") || currentPath.startsWith("/gymnast/") ? "page" : undefined}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" class="size-4 fill-current"><path d="M10 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3.465 14.493a1.23 1.23 0 0 0 .41 1.412A9.957 9.957 0 0 0 10 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 0 0-13.074.003Z" /></svg>
          Gymnasts
        </a>
      </li>
      <li>
        <a href="/clubs" onclick={handleNavClick} class:active={active("/clubs") || currentPath.startsWith("/club/")} aria-current={active("/clubs") || currentPath.startsWith("/club/") ? "page" : undefined}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 fill-current"><path fill="currentColor" d="M4 21v-9.375L2.2 13L1 11.4L12 3l11 8.4l-1.2 1.575l-1.8-1.35V21zm4-6q-.425 0-.712-.288T7 14t.288-.712T8 13t.713.288T9 14t-.288.713T8 15m4 0q-.425 0-.712-.288T11 14t.288-.712T12 13t.713.288T13 14t-.288.713T12 15m4 0q-.425 0-.712-.288T15 14t.288-.712T16 13t.713.288T17 14t-.288.713T16 15"/></svg>
          Clubs
        </a>
      </li>
      {#if canRankings}
        <li>
          <details class="w-full">
            <summary class="flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-base-300 transition-colors cursor-pointer">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 fill-current"><path fill="currentColor" d="m8 18l4-3.05L16 18l-1.5-4.95l4-2.85h-4.9L12 5l-1.6 5.2H5.5l4 2.85zm4 4q-2.075 0-3.9-.788t-3.175-2.137T2.788 15.9T2 12t.788-3.9t2.137-3.175T8.1 2.788T12 2t3.9.788t3.175 2.137T21.213 8.1T22 12t-.788 3.9t-2.137 3.175t-3.175 2.138T12 22m0-2q3.35 0 5.675-2.325T20 12t-2.325-5.675T12 4T6.325 6.325T4 12t2.325 5.675T12 20m0-8"/></svg>
              Rankings
            </summary>
            <ul class="ml-4 border-l border-base-300 pl-2 mt-1">
              {#if canNational}
                <li>
                  <a href="/rankings" onclick={handleNavClick} class:active={active("/rankings") && currentPath === "/rankings"}>National Rankings</a>
                </li>
              {/if}
              {#if canNational}
                <li>
                  <a href="/rankings/apparatus" onclick={handleNavClick} class:active={active("/rankings/apparatus")}>Apparatus Rankings</a>
                </li>
              {/if}
              {#if canWellington}
                <li>
                  <a href="/wellington-ranking" onclick={handleNavClick} class:active={active("/wellington-ranking")}>Wellington Rankings</a>
                </li>
              {/if}
            </ul>
          </details>
        </li>
      {/if}
      {#if showYearTabs}
      <li class="menu-title mt-4"><span>Year</span></li>
      <li>
        <div class="tabs tabs-box tabs-xs mt-1" aria-label="Year filter">
          {#each years as yr}
            <input
              type="radio"
              name="drawer_year"
              class="tab checked:bg-secondary checked:text-secondary-content"
              aria-label={yr}
              checked={selYear === yr}
              onchange={() => { selectedYear.set(yr); handleNavClick(); }}
            />
          {/each}
          <input
            type="radio"
            name="drawer_year"
            class="tab checked:bg-secondary checked:text-secondary-content"
            aria-label="All"
            checked={selYear === null}
            onchange={() => { selectedYear.set(null); handleNavClick(); }}
          />
        </div>
      </li>
      {/if}
      {#if authCfg}
        <li class="menu-title mt-4">
          {#if user}
            <span>{user.username} ({user.role})</span>
          {:else}
            <span>Account</span>
          {/if}
        </li>
        {#if user}
          {#if user?.role === "admin"}
            <li>
              <a href="/admin" onclick={handleNavClick} class:active={active("/admin") && currentPath === "/admin"}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 fill-current"><path fill="currentColor" d="M13 9V3h8v6zM3 13V3h8v10zm10 8V11h8v10zM3 21v-6h8v6z"/></svg>
                Dashboard
              </a>
            </li>
            <li>
              <a href="/admin/activity" onclick={handleNavClick} class:active={active("/admin/activity")}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4 fill-current"><path fill="currentColor" d="M1 21v-2h22v2zm3-3q-.825 0-1.412-.587T2 16v-5h5.375L9.1 14.45q.125.25.363.4t.512.15t.525-.125t.375-.375l3.075-5.375l.65 1.325q.125.275.375.413T15.5 11H22v5q0 .825-.587 1.412T20 18zm6.075-6.125L8.9 9.55q-.125-.25-.375-.4T8 9H2V5q0-.825.588-1.412T4 3h16q.825 0 1.413.588T22 5v4h-5.875L14.9 6.55q-.125-.275-.375-.413T14 6t-.5.138t-.35.362z"/></svg>
                Activity
              </a>
            </li>
            <li>
              <a href="/upload" onclick={handleNavClick} class:active={active("/upload")}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" class="size-4 fill-current"><path d="M9.25 13.25a.75.75 0 0 0 1.5 0V4.636l2.955 3.129a.75.75 0 0 0 1.09-1.03l-4.25-4.5a.75.75 0 0 0-1.09 0l-4.25 4.5a.75.75 0 1 0 1.09 1.03L9.25 4.636V13.25Z" /><path d="M3.5 12.75a.75.75 0 0 0-1.5 0v2.5A2.75 2.75 0 0 0 4.75 18h10.5A2.75 2.75 0 0 0 18 15.25v-2.5a.75.75 0 0 0-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5Z" /></svg>
                Upload
              </a>
            </li>
          {/if}
          <li>
            <button
              onclick={() => {
                logout();
                closeDrawer();
                goto("/");
              }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" class="size-4 fill-current"><path fill-rule="evenodd" d="M17 4.25A2.25 2.25 0 0 0 14.75 2h-5.5A2.25 2.25 0 0 0 7 4.25v2a.75.75 0 0 0 1.5 0v-2a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 .75.75v11.5a.75.75 0 0 1-.75.75h-5.5a.75.75 0 0 1-.75-.75v-2a.75.75 0 0 0-1.5 0v2A2.25 2.25 0 0 0 9.25 18h5.5A2.25 2.25 0 0 0 17 15.75V4.25Z" clip-rule="evenodd" /><path fill-rule="evenodd" d="M1 10a.75.75 0 0 1 .75-.75h9.546l-1.048-.943a.75.75 0 1 1 1.004-1.114l2.5 2.25a.75.75 0 0 1 0 1.114l-2.5 2.25a.75.75 0 1 1-1.004-1.114l1.048-.943H1.75A.75.75 0 0 1 1 10Z" clip-rule="evenodd" /></svg>
              Logout
            </button>
          </li>
        {:else}
          <li>
            <a href="/login" onclick={handleNavClick}>Login</a>
          </li>
        {/if}
      {/if}
      <li class="mt-4">
        <details class="dropdown w-full">
          <summary class="cursor-pointer list-none flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-base-300 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" class="size-4 fill-current">
              <path d="M11 22q-.825 0-1.412-.587T9 20v-4H6q-.825 0-1.412-.587T4 14V7q0-1.65 1.175-2.825T8 3h12v11q0 .825-.587 1.413T18 16h-3v4q0 .825-.587 1.413T13 22zM6 10h12V5h-1v4h-2V5h-1v2h-2V5H8q-.825 0-1.412.588T6 7z"/>
            </svg>
            {theme}
          </summary>
          <ul class="menu bg-base-200 rounded-box w-full p-2 shadow flex-row flex-wrap gap-x-4 gap-y-1">
            {#each THEMES as t}
              <li class="w-1/3">
                <button class={t === theme ? "active" : ""} onclick={() => { setTheme(t); closeDrawer(); }}>
                  <span data-theme={t} class="inline-flex items-center gap-0.5 shrink-0 rounded-full border px-1.5 py-0.5" style="background: var(--color-base-100); border-color: var(--color-base-300)">
                    <span class="size-2.5 rounded-full" style="background: var(--color-primary)"></span>
                    <span class="size-2.5 rounded-full" style="background: var(--color-secondary)"></span>
                  </span>
                  {t}
                </button>
              </li>
            {/each}
          </ul>
        </details>
      </li>
    </ul>
    </nav>
  </div>
</div>