<script lang="ts">
  import Tooltip from "$lib/Tooltip.svelte";

  let uid: number;
  {
    uid = Math.floor(Math.random() * 1e9);
  }

  let {
    row,
    prefixes,
  }: { row: Record<string, unknown>; prefixes: string[] } = $props();

  function sum(col: string): number {
    return prefixes.reduce((acc, p) => {
      const val = row[`${p}-${col}`];
      return acc + (parseFloat(String(val ?? "0")) || 0);
    }, 0);
  }

  function competedCount(col: string): number {
    return prefixes.reduce((acc, p) => {
      const val = row[`${p}-${col}`];
      return acc + (val != null && val !== "" && !Number.isNaN(Number(val)) ? 1 : 0);
    }, 0);
  }

  let totalD = $derived(sum("d"));
  let totalE = $derived(sum("e"));
  let totalN = $derived(sum("n"));
  let appCount = $derived(competedCount("e"));
  let eDeductions = $derived(appCount * 10 - totalE);
  let tipContentId = $derived(`aa-tip-content-${uid}`);
</script>

<Tooltip
  tipId={tipContentId}
  label={`${row["aa-score"] ?? ""}, all around score for ${row.name}`}
  placement="left"
  triggerClass="cursor-pointer"
  panelClass="p-3 min-w-44"
>
  {#snippet trigger()}
    {row["aa-score"] ?? ""}
  {/snippet}
  {#snippet content()}
    <div class="text-xs mb-1 text-left text-neutral-content/90">
      {row.name} - All Around
    </div>
    <div class="divider my-1"></div>
    <div class="flex flex-col gap-0.5">
      <div class="flex justify-between gap-4">
        <span class="font-semibold">AA Score</span>
        <span>{row["aa-score"] ?? ""}</span>
      </div>
      {#if row["aa-rank"] != null}
        <div class="flex justify-between gap-4">
          <span class="font-semibold">Rank</span>
          <span>{row["aa-rank"]}</span>
        </div>
      {/if}
      <div class="divider my-1"></div>
      <div class="flex justify-between gap-4">
        <span>Total D Score</span><span>{totalD.toFixed(1)}</span>
      </div>
      <div class="flex justify-between gap-4">
        <span>Total E Deductions</span><span>{eDeductions.toFixed(3)}</span>
      </div>
      <div class="flex justify-between gap-4">
        <span>Total ND</span><span>{totalN.toFixed(1)}</span>
      </div>
    </div>
  {/snippet}
</Tooltip>
