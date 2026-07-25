<script lang="ts">
  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c0 = $derived(colors[0] ?? "#888");
  let c1 = $derived(colors[1] ?? "#888");

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
  style="background: {c0}; color: {textColor(c0)}"
>
  <span class="grid grid-cols-2 w-5 shrink-0">
    <span class="w-2.5 h-2.5" style="background: {c0}"></span>
    <span class="w-2.5 h-2.5" style="background: {c1}"></span>
    <span class="w-2.5 h-2.5" style="background: {c1}"></span>
    <span class="w-2.5 h-2.5" style="background: {c0}"></span>
  </span>
  <span class="px-1.5 flex items-center">{region}</span>
</span>
