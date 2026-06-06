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

<div class="min-h-screen flex flex-col">
  <div class="navbar bg-base-200 shadow-sm flex-none">
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

  <main class="mx-auto grow shrink-0 basis-auto">
    <slot />
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
      <p class="text-xs text-base-content/60 mt-3">
        If this has saved you time, consider donating to cover development costs.
      </p>
    </div>
  </footer>
</div>
