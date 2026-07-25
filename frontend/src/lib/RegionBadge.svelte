<script lang="ts">
  import type { Snippet } from "svelte";

  let { region, colors = [] }: { region: string; colors?: string[]; children?: Snippet } = $props();
</script>

<span class="inline-flex items-center gap-1.5 text-xs font-medium rounded-full px-2 py-0.5 bg-base-200 border border-base-300 leading-none">
  {#each colors as c}
    <span class="w-2 h-2 rounded-full shrink-0" style="background: {c}"></span>
  {/each}
  {region}
</span>
