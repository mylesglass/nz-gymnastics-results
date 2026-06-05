<script lang="ts">
  import "../app.css";
</script>

<div class="navbar bg-base-200 mb-6 rounded-box shadow-sm">
  <div class="flex-1">
    <a href="/" class="btn btn-ghost text-xl">🤸 NZ Gymnastics Results</a>
  </div>
  <div class="flex-none gap-2">
    <a href="/" class="btn btn-ghost btn-sm">Upload</a>
    <a href="/events" class="btn btn-ghost btn-sm">Events</a>
  </div>
</div>

<main class="mx-auto px-4">
  <slot />
</main>
