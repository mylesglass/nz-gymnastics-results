<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    title,
    onClose,
    children,
    maxWidth = "max-w-md",
  }: {
    title: string;
    onClose: () => void;
    children: Snippet;
    maxWidth?: string;
  } = $props();

  let panelEl: HTMLElement | undefined = $state();
  let titleId = $state(`dialog-title-${Math.random().toString(36).slice(2, 8)}`);
  let prevFocus: HTMLElement | null = null;

  function focusable(el: HTMLElement): boolean {
    const selector =
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    return Boolean(el.matches(selector));
  }

  function getFocusables(): HTMLElement[] {
    if (!panelEl) return [];
    return Array.from(panelEl.querySelectorAll<HTMLElement>("a, button, input, select, textarea, [tabindex]")).filter(
      (el) => focusable(el) && el.getAttribute("aria-hidden") !== "true"
    );
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key !== "Tab") return;
    const items = getFocusables();
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (e.shiftKey && (active === first || active === panelEl || !panelEl?.contains(active))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || active === panelEl || !panelEl?.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  }

  $effect(() => {
    prevFocus = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => {
      panelEl?.focus();
    });
    return () => {
      prevFocus?.focus();
    };
  });
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
  onclick={(e) => {
    if (e.target === e.currentTarget) onClose();
  }}
>
  <div
    bind:this={panelEl}
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
    tabindex="-1"
    class="bg-base-100 rounded-box shadow-xl p-6 w-full {maxWidth} mx-4 max-h-[90vh] overflow-y-auto outline-none"
    onkeydown={onKeydown}
  >
    <h3 id={titleId} class="text-lg font-bold mb-4">{title}</h3>
    {@render children()}
  </div>
</div>
