<script lang="ts">
  import { onMount } from "svelte";
  import NativeMultiSelect from "./NativeMultiSelect.svelte";
  import { isTouchDevice } from "./touch";

  let { label, options, selected, onPick, ariaLabel }: {
    label: string;
    options: string[];
    selected: string[];
    onPick: (next: string[]) => void;
    ariaLabel: string;
  } = $props();

  let open = $state(false);
  let root: HTMLElement;
  let isTouch = $state(false);

  let count = $derived(selected.length);

  function toggle(opt: string) {
    if (selected.includes(opt)) {
      onPick(selected.filter((o) => o !== opt));
    } else {
      onPick([...selected, opt]);
    }
  }

  onMount(() => {
    isTouch = isTouchDevice();
    const handler = (e: MouseEvent) => {
      if (open && root && !root.contains(e.target as Node)) open = false;
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  });
</script>

{#if isTouch}
  <div class="inline-flex items-center gap-1">
    <NativeMultiSelect {options} {selected} onPick={onPick} {ariaLabel}>
      <button
        type="button"
        class="inline-flex items-center gap-1 cursor-pointer"
        aria-label={count > 0 ? `${ariaLabel}, ${count} selected` : ariaLabel}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          class="size-3.5 {count > 0 ? 'text-primary' : 'text-base-content/50'}"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
        </svg>
        {#if count > 0}
          <span class="badge badge-primary badge-sm min-w-5 h-5 px-1 text-xs font-bold" aria-hidden="true">{count}</span>
        {/if}
      </button>
    </NativeMultiSelect>
    {#if count > 0}
      <button
        type="button"
        class="cursor-pointer text-base-content/50 hover:text-error"
        aria-label={`Clear ${label} filter`}
        onclick={() => onPick([])}
      >✕</button>
    {/if}
  </div>
{:else}
  <div
    class="dropdown dropdown-bottom dropdown-end {open ? 'dropdown-open' : ''}"
    bind:this={root}
    onfocusout={(e) => {
      if (open && root && !(e.relatedTarget instanceof Node && root.contains(e.relatedTarget))) open = false;
    }}
  >
    <button
      type="button"
      class="inline-flex items-center gap-1 cursor-pointer"
      aria-label={count > 0 ? `${ariaLabel}, ${count} selected` : ariaLabel}
      aria-haspopup="menu"
      aria-expanded={open}
      onclick={() => (open = !open)}
      onkeydown={(e) => {
        if (e.key === "Escape") open = false;
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        class="size-3.5 {count > 0 ? 'text-primary' : 'text-base-content/50'}"
        aria-hidden="true"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
      </svg>
      {#if count > 0}
        <span class="badge badge-primary badge-sm min-w-5 h-5 px-1 text-xs font-bold" aria-hidden="true">{count}</span>
      {/if}
    </button>
    <ul
      role="menu"
      aria-label={ariaLabel}
      class="dropdown-content z-50 bg-base-100 border border-base-300 rounded-box shadow-xl p-1 max-h-72 overflow-y-auto w-72 text-sm font-normal"
      onkeydown={(e) => {
        if (e.key === "Escape") open = false;
      }}
    >
      {#if options.length === 0}
        <li role="none">
          <div class="px-2 py-1.5 text-base-content/50">No options</div>
        </li>
      {/if}
      {#each options as opt}
        {@const sel = selected.includes(opt)}
        <li role="none">
          <button
            type="button"
            role="menuitemcheckbox"
            aria-checked={sel}
            class="w-full text-left px-2 py-1.5 rounded hover:bg-base-200 flex items-center gap-2 {sel ? 'font-semibold text-primary' : ''}"
            onclick={() => toggle(opt)}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              class="size-3.5 shrink-0 {sel ? 'text-primary' : 'text-base-content/25'}"
              aria-hidden="true"
            >
              <path fill-rule="evenodd" d="M19.916 4.626a.75.75 0 0 1 .208 1.04l-9 13.5a.75.75 0 0 1-1.154.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 8.48-12.72a.75.75 0 0 1 1.04-.208Z" clip-rule="evenodd" />
            </svg>
            <span class="truncate">{opt}</span>
          </button>
        </li>
      {/each}
      {#if selected.length > 0}
        <li role="none" class="border-t border-base-300 mt-1 pt-1">
          <button
            type="button"
            class="w-full text-left px-2 py-1.5 rounded hover:bg-base-200 text-sm"
            onclick={() => onPick([])}
          >
            Clear {label} filter
          </button>
        </li>
      {/if}
    </ul>
  </div>
{/if}
