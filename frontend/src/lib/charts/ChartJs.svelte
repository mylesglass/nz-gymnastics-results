<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import type { Chart, ChartData, ChartOptions, ChartType } from "chart.js";

  let {
    type,
    data,
    options,
    label = "Chart",
    heightClass = "h-64",
    fallbackText = "",
  }: {
    type: ChartType;
    data: ChartData;
    options?: ChartOptions;
    label?: string;
    heightClass?: string;
    fallbackText?: string;
  } = $props();

  let canvasEl: HTMLCanvasElement | undefined = $state();
  let chart: Chart | undefined = $state();
  let chartError = $state<string | null>(null);

  onMount(async () => {
    try {
      const mod = await import("chart.js/auto");
      const ChartCtor = (mod.default ?? mod.Chart) as typeof Chart;
      chart = new ChartCtor(canvasEl as HTMLCanvasElement, {
        type,
        data,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          ...options,
        },
      });
    } catch (e) {
      chartError = String(e);
    }
  });

  $effect(() => {
    if (!chart) return;
    chart.data = data as never;
    chart.options = { responsive: true, maintainAspectRatio: false, ...options } as never;
    chart.update();
  });

  onDestroy(() => {
    chart?.destroy();
    chart = undefined;
  });
</script>

<div class="relative {heightClass}">
  <canvas
    bind:this={canvasEl}
    role="img"
    aria-label={label}
  >{fallbackText}</canvas>
</div>
{#if chartError}
  <p role="alert" class="text-sm text-error">Chart failed to load: {chartError}</p>
{/if}
