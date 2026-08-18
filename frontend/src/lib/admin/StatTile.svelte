<script lang="ts">
  let {
    icon,
    label,
    value,
    sub,
    valueClass = "text-lg",
    onclick,
    buttonClass = "",
    iconClass = "text-primary",
  }: {
    icon: string;
    label: string;
    value: string;
    sub?: string;
    valueClass?: string;
    onclick?: () => void;
    buttonClass?: string;
    iconClass?: string;
  } = $props();
</script>

{#if onclick}
  <button
    class="btn btn-ghost btn-sm normal-case flex-col items-center gap-0.5 px-4 py-1.5 h-auto rounded-xl {buttonClass}"
    onclick={onclick}
    aria-label={`${label}: ${value}${sub ? ` (${sub})` : ""}`}
  >
    <span class="material-symbols-outlined {iconClass}" aria-hidden="true">{icon}</span>
    <span class="{valueClass} font-bold leading-none">{value}</span>
    <span class="text-[10px] text-base-content/70 text-center leading-tight">{label}</span>
    {#if sub}
      <span class="text-[9px] text-base-content/60 text-center leading-tight">{sub}</span>
    {/if}
  </button>
{:else}
  <div class="flex flex-col items-center justify-center gap-0.5 px-4 py-1.5">
    <span class="material-symbols-outlined text-primary" aria-hidden="true">{icon}</span>
    <span class="{valueClass} font-bold leading-none">{value}</span>
    <span class="text-[10px] text-base-content/70 text-center leading-tight">{label}</span>
    {#if sub}
      <span class="text-[9px] text-base-content/60 text-center leading-tight">{sub}</span>
    {/if}
  </div>
{/if}
