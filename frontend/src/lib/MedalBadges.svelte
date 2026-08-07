<script lang="ts">
  import type { MedalCounts } from "./api";
  import { MEDAL_COLORS } from "./medals";

  let {
    medals,
    size = "sm",
    showEmpty = true,
  }: {
    medals: MedalCounts;
    size?: "xs" | "sm";
    showEmpty?: boolean;
  } = $props();

  const colors = { g: MEDAL_COLORS[1], s: MEDAL_COLORS[2], b: MEDAL_COLORS[3] };
  const labels: Record<"g" | "s" | "b", string> = { g: "Gold", s: "Silver", b: "Bronze" };
  const MEDAL_KEYS = ["g", "s", "b"] as const;

  let hasMedals = $derived(medals.total > 0);

  let summary = $derived.by(() => {
    const parts: string[] = [];
    for (const key of MEDAL_KEYS) {
      if (medals[key] > 0) parts.push(`${medals[key]} ${labels[key].toLowerCase()}`);
    }
    return parts.join(", ") || "No medals";
  });

  let dot = $derived(size === "xs" ? "size-2" : "size-2.5");
  let num = $derived(size === "xs" ? "text-[11px]" : "text-xs");
</script>

{#if hasMedals}
  <span class="inline-flex items-center gap-1.5" role="group" aria-label={summary}>
    {#each MEDAL_KEYS as key (key)}
      {@const count = medals[key]}
      {#if count > 0}
        <span class="inline-flex items-center gap-1" title="{labels[key]}: {count}">
          <span class="{dot} rounded-full shrink-0" style="background: {colors[key]}" aria-hidden="true"></span>
          <span class="{num} font-semibold tabular-nums leading-none">{count}</span>
        </span>
      {/if}
    {/each}
  </span>
{:else if showEmpty}
  <span class="text-base-content/30 text-xs">—</span>
{/if}
