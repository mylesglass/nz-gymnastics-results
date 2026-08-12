<script lang="ts">
  import { onMount } from "svelte";
  import type { Snippet } from "svelte";

  let {
    options,
    selected,
    onPick,
    ariaLabel,
    children,
  }: {
    options: string[];
    selected: string[];
    onPick: (next: string[]) => void;
    ariaLabel: string;
    children: Snippet;
  } = $props();

  let isTouch = $state(false);
  let localSelected = $state<string[]>([]);

  $effect(() => {
    localSelected = [...selected];
  });

  function handleChange(e: Event) {
    const sel = e.currentTarget as HTMLSelectElement;
    onPick(Array.from(sel.selectedOptions).map((o) => o.value));
  }

  onMount(() => {
    isTouch = window.matchMedia("(hover: none) and (pointer: coarse)").matches;
  });
</script>

<div class="relative inline-flex">
  {@render children()}
  {#if isTouch}
    <select
      multiple
      class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
      aria-label={ariaLabel}
      bind:value={localSelected}
      onchange={handleChange}
    >
      {#each options as opt}
        <option value={opt}>{opt}</option>
      {/each}
    </select>
  {/if}
</div>
