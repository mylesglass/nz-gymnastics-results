<script lang="ts">
  let {
    icon,
    label,
    value,
    sub,
    valueClass = "text-lg",
  }: {
    icon: string;
    label: string;
    value: string;
    sub?: string;
    valueClass?: string;
  } = $props();
</script>

<div class="flex flex-col items-center justify-center gap-0.5 rounded-box bg-base-200 border border-base-300 {sub ? 'w-28 min-h-28 px-2 py-2' : 'w-24 h-24'}">
  <span class="material-symbols-outlined text-primary" aria-hidden="true">{icon}</span>
  <span class="{valueClass} font-bold leading-none">{value}</span>
  <span class="text-[10px] text-base-content/70 text-center leading-tight">{label}</span>
  {#if sub}
    <span class="text-[9px] text-base-content/60 text-center leading-tight">{sub}</span>
  {/if}
</div>
