<script lang="ts">
  import Tooltip from "$lib/Tooltip.svelte";

  let uid: number;
  {
    uid = Math.floor(Math.random() * 1e9);
  }

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
  let tipContentId = $derived(`score-tip-content-${prefix}-${uid}`);
  let triggerLabel = $derived(
    `${row[`${prefix}-d`] ?? ""} / ${row[`${prefix}-total`] ?? "DNS"}, ${appLabel} score for ${row.name}`,
  );
</script>

{#if hasMulti}
  <Tooltip
    tipId={tipContentId}
    label={triggerLabel}
    placement="right"
    triggerClass="cursor-pointer border-b border-dotted border-base-content/40 hover:border-base-content/70 leading-tight"
    panelClass="p-3 min-w-64"
  >
    {#snippet trigger()}
      {row[`${prefix}-d`] ?? ""} / {row[`${prefix}-total`] ?? "DNS"}
    {/snippet}
    {#snippet content()}
      <div class="text-xs mb-1 text-left text-neutral-content/90">
        {row.name} - {appLabel}
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
          <span class="text-accent">+{row[`${prefix}-bonus`]}</span>
        {/if}
        {#if row[`${prefix}-rank`] != null}
          <span>Rank {row[`${prefix}-rank`]}</span>
        {/if}
      </div>
    {/snippet}
  </Tooltip>
{:else}
  <Tooltip
    tipId={tipContentId}
    label={triggerLabel}
    placement="right"
    triggerClass="cursor-pointer border-b border-dotted border-base-content/40 hover:border-base-content/70 leading-tight"
    panelClass="p-3 min-w-36"
  >
    {#snippet trigger()}
      {row[`${prefix}-d`] ?? ""} / {row[`${prefix}-total`] ?? "DNS"}
    {/snippet}
    {#snippet content()}
      <div class="text-xs mb-1 text-left text-neutral-content/90">
        {row.name} - {appLabel}
      </div>

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

        {#if row[`${prefix}-bonus`] != null}
          <div class="flex justify-between gap-4 text-accent">
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
        <div class="flex justify-between pt-2 gap-4">
          <span class="font-bold">Total</span><span
            >{row[`${prefix}-total`] ?? "DNS"}</span
          >
        </div>
      </div>
    {/snippet}
  </Tooltip>
{/if}
