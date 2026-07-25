<script lang="ts">
  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c = $derived(colors.length ? colors : ["#888", "#888"]);
  let bg = $derived(c[0]);
  let borderColor = $derived(c.length >= 3 ? c[2] : c[1 % c.length]);

  function textColor(hex: string): string {
    let h = hex.replace("#", "");
    let r = parseInt(h.substring(0, 2), 16);
    let g = parseInt(h.substring(2, 4), 16);
    let b = parseInt(h.substring(4, 6), 16);
    return (r * 0.299 + g * 0.587 + b * 0.114) > 160 ? "#111" : "#fff";
  }
</script>

<span
  class="inline-flex items-stretch h-5 text-xs font-medium leading-none rounded overflow-hidden"
  style="background: {bg}; color: {textColor(bg)}; box-shadow: 0 0 0 1.5px {borderColor}"
>
  <span class="grid grid-cols-2 w-5 shrink-0">
    <span class="w-2.5 h-2.5" style="background: {c[0]}"></span>
    <span class="w-2.5 h-2.5" style="background: {c[1]}"></span>
    <span class="w-2.5 h-2.5" style="background: {c[1]}"></span>
    <span class="w-2.5 h-2.5" style="background: {c[0]}"></span>
  </span>
  <span class="px-1.5 flex items-center">{region}</span>
</span>
