<script lang="ts">
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

  let totalD = $derived(sum("d"));
  let totalE = $derived(sum("e"));
  let totalN = $derived(sum("n"));
</script>

<div class="dropdown dropdown-hover dropdown-right">
  <div class="cursor-pointer" role="button" tabindex="0">
    {row["aa-score"] ?? ""}
  </div>
  <div
    class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs min-w-44"
    role="menu"
    tabindex="0"
  >
    <div class="text-[0.65rem] opacity-70 mb-1 text-left">
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
        <span>Total D</span><span>{totalD.toFixed(1)}</span>
      </div>
      <div class="flex justify-between gap-4">
        <span>Total E</span><span>{totalE.toFixed(3)}</span>
      </div>
      <div class="flex justify-between gap-4">
        <span>Total N</span><span>{totalN.toFixed(1)}</span>
      </div>
    </div>
  </div>
</div>
