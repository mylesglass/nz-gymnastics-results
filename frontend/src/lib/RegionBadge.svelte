<script lang="ts">
  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c = $derived(colors.length ? colors : ["#888", "#888"]);
  let bg = $derived(c[0]);
  let accents = $derived(c.slice(1));

  function textColor(hex: string): string {
    let h = hex.replace("#", "");
    let r = parseInt(h.substring(0, 2), 16);
    let g = parseInt(h.substring(2, 4), 16);
    let b = parseInt(h.substring(4, 6), 16);
    return (r * 0.299 + g * 0.587 + b * 0.114) > 160 ? "#111" : "#fff";
  }
</script>

<span
  class="inline-flex items-stretch h-5 text-xs font-medium rounded overflow-hidden leading-none"
  style="background: {bg}; color: {textColor(bg)}"
>
  {#each accents as ac}
    <span class="w-[3px] h-full shrink-0" style="background: {ac}"></span>
  {/each}
  <span class="px-1.5 flex items-center truncate max-w-28">{region}</span>
  {#each [...accents].reverse() as ac}
    <span class="w-[3px] h-full shrink-0" style="background: {ac}"></span>
  {/each}
</span>
