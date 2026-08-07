<script lang="ts">
  import { MEDAL_LABELS, medalColor } from "./medals";

  let {
    rank,
    size = "sm",
  }: {
    rank: number | null;
    size?: "xs" | "sm";
  } = $props();

  let color = $derived(medalColor(rank));
  let label = $derived(rank != null ? (MEDAL_LABELS[rank] ?? null) : null);
</script>

{#if color && label}
  <span
    class="rounded-full shrink-0 inline-block {size === 'xs' ? 'size-2' : 'size-2.5'}"
    style="background: {color}"
    role="img"
    aria-label="{label} medal, rank {rank}"
    title="{label} medal"
  ></span>
{/if}
