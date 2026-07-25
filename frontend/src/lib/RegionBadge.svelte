<script lang="ts">
  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c = $derived(colors.length ? colors : ["#888", "#888"]);
  let bg = $derived(c[0]);
  let ckA = $derived(c[0]);
  let ckB = $derived(c[1]);

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
  style="background: {bg}; color: {textColor(bg)}"
>
  <span class="grid grid-cols-3 w-[30px] h-full shrink-0">
    <span style="background: {ckA}"></span>
    <span style="background: {ckB}"></span>
    <span style="background: {ckA}"></span>
    <span style="background: {ckB}"></span>
    <span style="background: {ckA}"></span>
    <span style="background: {ckB}"></span>
    <span style="background: {ckA}"></span>
    <span style="background: {ckB}"></span>
    <span style="background: {ckA}"></span>
    <span style="background: {ckB}"></span>
    <span style="background: {ckA}"></span>
    <span style="background: {ckB}"></span>
  </span>
  <span class="px-1.5 flex items-center">{region}</span>
</span>
