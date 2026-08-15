<script lang="ts">
  import Tooltip from "$lib/Tooltip.svelte";

  let { region, colors = [] }: { region: string; colors?: string[] } = $props();

  let c = $derived(colors.length ? colors : ["#888", "#888"]);

  let uid: number;
  {
    uid = Math.floor(Math.random() * 1e9);
  }

  function tipId(): string {
    return `rc-tip-${region}-${uid}`;
  }
</script>

<Tooltip
  tipId={tipId()}
  label={`Region ${region}`}
  placement="top"
  triggerClass="inline-flex cursor-help"
>
  {#snippet trigger()}
    <span class="flex flex-wrap w-5 h-5 shrink-0 overflow-hidden rounded" aria-hidden="true">
      <span class="w-2.5 h-2.5" style="background: {c[0]}"></span>
      <span class="w-2.5 h-2.5" style="background: {c[1]}"></span>
      <span class="w-2.5 h-2.5" style="background: {c[1]}"></span>
      <span class="w-2.5 h-2.5" style="background: {c[0]}"></span>
    </span>
  {/snippet}
  {#snippet content()}
    {region}
  {/snippet}
</Tooltip>
