<script lang="ts">
  import { onMount } from "svelte";
  import "../app.css";

  let theme = $state("dark");

  onMount(() => {
    theme = document.documentElement.dataset.theme || "dark";
  });

  function toggleTheme() {
    theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }
</script>

<div class="navbar bg-base-200 shadow-sm">
  <div class="flex-1">
    <a href="/" class="btn btn-ghost text-xl">🤸 NZ Gymnastics Results</a>
  </div>
  <div class="flex-none gap-2 items-center">
    <a href="/" class="btn btn-outline btn-sm">Upload</a>
    <a href="/events" class="btn btn-outline btn-sm">Events</a>
    <a href="/results" class="btn btn-outline btn-sm">Results</a>
    <button onclick={toggleTheme} class="btn btn-ghost btn-sm btn-square">
      {#if theme === "dark"}☀️{:else}🌙{/if}
    </button>
  </div>
</div>

<main class="mx-auto">
  <slot />
</main>
