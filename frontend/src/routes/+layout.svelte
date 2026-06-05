<script lang="ts">
  import { onMount } from "svelte";
  import "../app.css";

  let theme = $state("dark");
  let navScrolled = $state(false);

  onMount(() => {
    theme = document.documentElement.dataset.theme || "dark";
    const onScroll = () => { navScrolled = window.scrollY > 10; };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  });

  function toggleTheme() {
    theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }
</script>

<div class="navbar sticky top-0 z-50 bg-base-200 shadow-sm transition-all duration-200 {navScrolled ? 'py-1' : ''}">
  <div class="flex-1">
    <a href="/" class="btn btn-ghost transition-all duration-200 {navScrolled ? 'text-lg' : 'text-xl'}">🤸 NZ Gymnastics Results</a>
  </div>
  <div class="flex-none gap-2 items-center">
    <a href="/" class="btn btn-ghost btn-sm">Upload</a>
    <a href="/events" class="btn btn-ghost btn-sm">Events</a>
    <a href="/results" class="btn btn-ghost btn-sm">Results</a>
    <button onclick={toggleTheme} class="btn btn-ghost btn-sm btn-square">
      {#if theme === "dark"}☀️{:else}🌙{/if}
    </button>
  </div>
</div>

<main class="mx-auto px-4">
  <slot />
</main>
