<script lang="ts">
  let {
    options,
    selected = $bindable(),
    label,
    placeholder = "",
    disabled = false,
  }: {
    options: string[];
    selected: string[];
    label: string;
    placeholder?: string;
    disabled?: boolean;
  } = $props();

  function toggle(opt: string) {
    if (selected.includes(opt)) {
      selected = selected.filter((s) => s !== opt);
    } else {
      selected = [...selected, opt];
    }
  }

  function clear() {
    selected = [];
  }
</script>

<div class="dropdown dropdown-end">
  <button
    class="btn btn-outline btn-xs min-w-42 {disabled ? 'btn-disabled' : ''}"
    tabindex="0"
  >
    <span class="truncate">
      {selected.length === 0
        ? placeholder || label
        : `${label} (${selected.length})`}
    </span>
    <span class="text-xs opacity-50">▼</span>
  </button>
  <div
    class="dropdown-content bg-base-200 rounded-box p-2 shadow-md z-50 min-w-44"
    tabindex="0"
  >
    {#if options.length === 0}
      <p class="text-xs text-base-content/70 px-1 py-2">No options</p>
    {:else}
      <div class="flex justify-between items-center mb-1 px-1">
        <span class="text-xs font-semibold">{label}</span>
        {#if selected.length > 0}
          <button onclick={clear} class="text-xs text-primary hover:underline"
            >Clear</button
          >
        {/if}
      </div>
      {#each options as opt}
        <label
          class="flex items-center gap-2 px-1 py-0.5 hover:bg-base-300 rounded cursor-pointer"
        >
          <input
            type="checkbox"
            checked={selected.includes(opt)}
            onchange={() => toggle(opt)}
            class="checkbox checkbox-xs"
          />
          <span class="text-xs">{opt}</span>
        </label>
      {/each}
    {/if}
  </div>
</div>
