<script lang="ts">
  import { textColor } from "./regions";
  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c = $derived(colors.length ? colors : ["#888", "#888"]);
  let bg = $derived(c[0]);
  let ckA = $derived(c[0]);
  let ckB = $derived(c[1]);
</script>

<span
  class="inline-flex items-stretch h-5 text-xs font-medium leading-none rounded overflow-hidden whitespace-nowrap"
  style="background: {bg}; color: {textColor(bg)}"
>
  <span class="flex flex-wrap w-5 h-5 shrink-0 overflow-hidden">
    <span class="w-2.5 h-2.5" style="background: {ckA}"></span>
    <span class="w-2.5 h-2.5" style="background: {ckB}"></span>
    <span class="w-2.5 h-2.5" style="background: {ckB}"></span>
    <span class="w-2.5 h-2.5" style="background: {ckA}"></span>
  </span>
  <span class="px-1.5 flex items-center">{region}</span>
</span>
