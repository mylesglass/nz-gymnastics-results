<script lang="ts">
  import { onMount } from "svelte";
  import type { Snippet } from "svelte";

  let {
    tipId,
    label,
    placement = "top",
    triggerClass = "",
    panelClass = "",
    trigger,
    content,
  }: {
    tipId: string;
    label: string;
    placement?: "top" | "bottom" | "left" | "right";
    triggerClass?: string;
    panelClass?: string;
    trigger: Snippet;
    content: Snippet;
  } = $props();

  const GAP = 8;

  let pos = $state<{ top: number; left: number } | null>(null);
  let btnEl: HTMLButtonElement | undefined = $state();
  let panelEl: HTMLElement | undefined = $state();

  function position(): void {
    if (!btnEl || !panelEl) return;
    const rect = btnEl.getBoundingClientRect();
    const pw = panelEl.offsetWidth;
    const ph = panelEl.offsetHeight;
    const clampX = (x: number) =>
      Math.min(Math.max(x, GAP), window.innerWidth - pw - GAP);
    const clampY = (y: number) =>
      Math.min(Math.max(y, GAP), window.innerHeight - ph - GAP);
    let top: number;
    let left: number;
    switch (placement) {
      case "top":
        top = rect.top - ph - GAP;
        if (top < GAP) {
          top = rect.bottom + GAP;
          if (top + ph > window.innerHeight - GAP) top = window.innerHeight - ph - GAP;
        }
        left = clampX(rect.left + rect.width / 2 - pw / 2);
        break;
      case "bottom":
        top = rect.bottom + GAP;
        if (top + ph > window.innerHeight - GAP) {
          top = rect.top - ph - GAP;
          if (top < GAP) top = GAP;
        }
        left = clampX(rect.left + rect.width / 2 - pw / 2);
        break;
      case "left":
        left = rect.left - pw - GAP;
        if (left < GAP) left = rect.right + GAP;
        top = clampY(rect.top + rect.height / 2 - ph / 2);
        break;
      default:
        left = rect.right + GAP;
        if (left + pw > window.innerWidth - GAP) left = rect.left - pw - GAP;
        top = clampY(rect.top + rect.height / 2 - ph / 2);
        break;
    }
    pos = { top, left };
  }

  function show(): void {
    position();
  }

  function hide(): void {
    pos = null;
  }

  onMount(() => {
    const reposition = () => {
      if (pos) position();
    };
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  });
</script>

<span class="inline-flex">
  <button
    type="button"
    class={triggerClass}
    aria-label={label}
    aria-describedby={tipId}
    bind:this={btnEl}
    onmouseenter={show}
    onfocus={show}
    onmouseleave={hide}
    onblur={hide}
    onkeydown={(e) => {
      if (e.key === "Escape") hide();
    }}
  >
    {@render trigger()}
  </button>
  <span
    id={tipId}
    role="tooltip"
    bind:this={panelEl}
    class="pointer-events-none fixed z-50 rounded-box bg-neutral text-neutral-content shadow-xl text-xs {pos ? '' : 'invisible'} {panelClass}"
    style="left: {pos?.left ?? 0}px; top: {pos?.top ?? 0}px"
  >
    {@render content()}
  </span>
</span>
