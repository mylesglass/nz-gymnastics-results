<script lang="ts">
  let { row, prefix }: { row: Record<string, unknown>; prefix: string } =
    $props();

  let hasMulti = $derived(row[`${prefix}-1-total`] != null);

  const APP_LABELS: Record<string, string> = {
    vt: "Vault",
    ub: "Uneven Bars",
    bb: "Balance Beam",
    fx: "Floor",
    ph: "Pommel Horse",
    sr: "Still Rings",
    pb: "Parallel Bars",
    hb: "Horizontal Bar",
  };
  let appLabel = $derived(APP_LABELS[prefix] ?? prefix.toUpperCase());
</script>

{#if hasMulti}
  <div class="dropdown dropdown-hover dropdown-right">
    <div class="cursor-pointer" tabindex="0">
      {row[`${prefix}-d`] ?? ""} / {row[`${prefix}-total`] ?? "DNS"}
    </div>
    <div
      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs min-w-64"
      tabindex="0"
    >
      <div class="text-[0.65rem] opacity-70 mb-1 text-left">
        {row.name} — {appLabel}
      </div>
      <div class="divider my-1"></div>
      {#each [1, 2] as i}
        <div class="flex gap-3 justify-between whitespace-nowrap">
          <span class="font-semibold">Pass {i}</span>
          <span>D {row[`${prefix}-${i}-d`] ?? ""}</span>
          <span>E {row[`${prefix}-${i}-e`] ?? ""}</span>
          <span>N {row[`${prefix}-${i}-n`] ?? ""}</span>
          <span class="font-semibold"
            >{row[`${prefix}-${i}-total`] ?? "DNS"}</span
          >
        </div>
      {/each}
      <div class="divider my-1"></div>
      <div class="flex gap-3 justify-between whitespace-nowrap">
        <span class="font-semibold">Score</span>
        <span>D {row[`${prefix}-d`] ?? ""}</span>
        <span class="font-semibold">{row[`${prefix}-total`] ?? ""}</span>
        {#if row[`${prefix}-bonus`] != null}
          <span class="text-success">+{row[`${prefix}-bonus`]}</span>
        {/if}
        {#if row[`${prefix}-rank`] != null}
          <span>Rank {row[`${prefix}-rank`]}</span>
        {/if}
      </div>
    </div>
  </div>
{:else}
  <div class="dropdown dropdown-hover dropdown-right">
    <div class="cursor-pointer" tabindex="0">
      {row[`${prefix}-d`] ?? ""} / {row[`${prefix}-total`] ?? "DNS"}
    </div>
    <div
      class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs min-w-48"
      tabindex="0"
    >
      <div class="flex justify-between">
        <div class="text-[0.65rem] opacity-70 mb-1">
          {row.name}
        </div>
        <div class="text-[0.65rem] opacity-70 mb-1">
          {appLabel}
        </div>
      </div>

      <div class="divider my-1"></div>
      <div class="flex flex-col gap-0.5">
        <div class="flex justify-between gap-4">
          <span class="font-semibold">D</span><span
            >{row[`${prefix}-d`] ?? ""}</span
          >
        </div>
        {#if row[`${prefix}-e`] != null}
          <div class="flex justify-between gap-4">
            <span class="font-semibold">E</span><span>{row[`${prefix}-e`]}</span
            >
          </div>
        {/if}
        {#if row[`${prefix}-n`] != null}
          <div class="flex justify-between gap-4">
            <span class="font-semibold">N</span><span>{row[`${prefix}-n`]}</span
            >
          </div>
        {/if}
        <div class="flex justify-between gap-4">
          <span class="font-semibold">Total</span><span
            >{row[`${prefix}-total`] ?? "DNS"}</span
          >
        </div>
        {#if row[`${prefix}-bonus`] != null}
          <div class="flex justify-between gap-4 text-success">
            <span class="font-semibold">Bonus</span><span
              >+{row[`${prefix}-bonus`]}</span
            >
          </div>
        {/if}
        {#if row[`${prefix}-rank`] != null}
          <div class="flex justify-between gap-4">
            <span class="font-semibold">Rank</span><span
              >{row[`${prefix}-rank`]}</span
            >
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
