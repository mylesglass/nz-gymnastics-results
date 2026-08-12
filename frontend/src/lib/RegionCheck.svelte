<script lang="ts">
  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c = $derived(colors.length ? colors : ["#888", "#888"]);
</script>

<button
  type="button"
  class="tooltip tooltip-top cursor-help inline-flex"
  data-tip={region}
  aria-label={`Region ${region}`}
>
  <span class="flex flex-wrap w-5 h-5 shrink-0 overflow-hidden rounded" aria-hidden="true">
    <span class="w-2.5 h-2.5" style="background: {c[0]}"></span>
    <span class="w-2.5 h-2.5" style="background: {c[1]}"></span>
    <span class="w-2.5 h-2.5" style="background: {c[1]}"></span>
    <span class="w-2.5 h-2.5" style="background: {c[0]}"></span>
  </span>
</button>
