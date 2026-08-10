<script lang="ts">
  import type { EventSummary, KnownClub } from "$lib/api";
  import { selectedYear } from "$lib/year";
  import { REGION_PALETTES } from "$lib/regions";
  import RegionBadge from "$lib/RegionBadge.svelte";

  let { events, knownClubs }: { events: EventSummary[]; knownClubs: KnownClub[] } = $props();

  const PITCH = 96;
  const STACK_H = 40;
  const BASE_RISE = 78;
  const STUB = 16;
  const ARM = 12;
  const STROKE = 3;
  const CK_CELL = 6;
  const DATE_PUSH = 14;
  const TOP_OVER = 18;
  const BOTTOM_OVER = 30;
  const WIDTH_MARGIN = 320;
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const year = $derived($selectedYear);

  const clubRegions = $derived(new Map(knownClubs.map((c) => [c.name.toLowerCase(), c.region])));

  interface CompNode {
    ev: EventSummary;
    short: string;
    col: number;
    x: number;
    up: boolean;
    rise: number;
    nameY: number;
    dateY: number;
    dateX: number;
    labelX: number;
    hitX: number;
    hitY: number;
    hitW: number;
    d: string;
    ckA: string;
    ckB: string;
  }

  interface MonthMark {
    x: number;
    label: string;
    noLine?: boolean;
  }

  function regionFor(ev: EventSummary): string | null {
    if (ev.is_national) return null;
    const club = ev.host_club;
    if (!club) return null;
    if (club.toLowerCase().includes("gymnastics nz")) return null;
    return clubRegions.get(club.toLowerCase()) ?? null;
  }

  function parseDate(d: string): { m: number; day: number; doy: number } | null {
    const re = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
    if (!re) return null;
    const y = +re[1];
    const m = +re[2] - 1;
    const day = +re[3];
    const doy = Math.floor((Date.UTC(y, m, day) - Date.UTC(y, 0, 1)) / 86400000);
    return { m, day, doy };
  }

  function fmtDate(d: string): string {
    const p = parseDate(d);
    if (!p) return d;
    return `${p.day} ${MONTHS[p.m]}`;
  }

  function dateRange(ev: EventSummary): string {
    const s = fmtDate(ev.start_date);
    if (ev.end_date && ev.end_date !== ev.start_date) return `${s} – ${fmtDate(ev.end_date)}`;
    return s;
  }

  function weekCol(ev: EventSummary): number {
    const p = parseDate(ev.start_date);
    return p ? Math.floor(p.doy / 7) : 0;
  }

  function shortName(name: string): string {
    return name.length > 22 ? name.slice(0, 22).trimEnd() + "…" : name;
  }

  const yearEvents = $derived(
    year === null
      ? []
      : events
          .filter((e) => String(e.year ?? "") === year)
          .sort((a, b) => a.start_date.localeCompare(b.start_date))
  );

  const weeks = $derived.by(() => {
    const map = new Map<number, EventSummary[]>();
    for (const ev of yearEvents) {
      const col = weekCol(ev);
      const arr = map.get(col) ?? [];
      arr.push(ev);
      map.set(col, arr);
    }
    return [...map.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([col, comps]) => ({ col, comps }));
  });

  const startWeek = $derived(weeks.length ? Math.max(0, weeks[0].col - 1) : 0);
  const endWeek = $derived(weeks.length ? Math.min(52, weeks[weeks.length - 1].col + 1) : 52);

  const maxRise = $derived(
    BASE_RISE + (Math.max(0, ...weeks.map((w) => w.comps.length)) - 1) * STACK_H
  );

  const mainY = $derived(maxRise + TOP_OVER + 24);

  const nodes = $derived.by(() => {
    const out: CompNode[] = [];
    for (const w of weeks) {
      const x = (w.col - startWeek) * PITCH + PITCH / 2;
      w.comps.forEach((ev, i) => {
        const up = w.col % 2 === 0;
        const rise = BASE_RISE + i * STACK_H;
        const riseGap = rise - STUB;
        const nameY = up ? mainY - rise : mainY + rise;
        const labelX = x + riseGap + ARM;
        const region = regionFor(ev);
        const pal = region ? REGION_PALETTES[region] : [];
        const ckA = pal[0] ?? "#888";
        const ckB = pal[1] ?? "#888";
        const d = up
          ? `M ${x} ${mainY} V ${mainY - STUB} L ${x + riseGap} ${nameY}`
          : `M ${x} ${mainY} V ${mainY + STUB} L ${x + riseGap} ${nameY}`;
        const nameW = shortName(ev.name).length * 6.6;
        const dateW = dateRange(ev).length * 5.6;
        const hitW = Math.max(nameW, dateW) + 12 + (up ? 0 : DATE_PUSH);
        out.push({
          ev,
          short: shortName(ev.name),
          col: w.col,
          x,
          up,
          rise,
          nameY,
          dateY: nameY + 16,
          dateX: labelX + (up ? 0 : DATE_PUSH),
          labelX,
          hitX: labelX - 4,
          hitY: nameY - 16,
          hitW,
          d,
          ckA,
          ckB,
        });
      });
    }
    return out;
  });

  const topMinY = $derived(mainY - maxRise - TOP_OVER);
  const bottomMaxY = $derived(mainY + maxRise + BOTTOM_OVER);
  const monthY = $derived(bottomMaxY + 16);
  const svgHeight = $derived(monthY + 24);
  const width = $derived((endWeek - startWeek + 1) * PITCH + WIDTH_MARGIN);

  const months = $derived.by(() => {
    const y = Number(year);
    if (Number.isNaN(y)) return [];
    const marks: MonthMark[] = [];
    for (let m = 0; m < 12; m++) {
      const ms = Math.floor((Date.UTC(y, m, 1) - Date.UTC(y, 0, 1)) / 86400000 / 7);
      if (ms >= startWeek && ms <= endWeek) {
        marks.push({ x: (ms - startWeek) * PITCH, label: MONTHS[m] });
      }
    }
    const firstDate = new Date(Date.UTC(y, 0, 1) + startWeek * 7 * 86400000);
    const firstLabel = MONTHS[firstDate.getUTCMonth()];
    if (!marks.some((mk) => mk.label === firstLabel)) {
      marks.unshift({ x: 0, label: firstLabel, noLine: true });
    }
    return marks;
  });

  let hoverId = $state<number | null>(null);
  let focusedId = $state<number | null>(null);
  let tip = $state<{ ev: EventSummary; x: number; y: number; above: boolean } | null>(null);

  function labelFor(ev: EventSummary): string {
    const region = regionFor(ev);
    const parts = [
      ev.name,
      dateRange(ev),
      ev.discipline === "WAG" || ev.discipline === "MAG" ? `${ev.discipline} event` : "WAG and MAG event",
      ev.host_club ? `hosted by ${ev.host_club}` : "host club not set",
    ];
    if (region) parts.push(`region ${region}`);
    if (ev.is_national) parts.push("National Championships");
    return parts.join(", ");
  }

  function showTip(e: MouseEvent | FocusEvent, ev: EventSummary) {
    const el = e.currentTarget as Element;
    const r = el.getBoundingClientRect();
    const x = Math.min(Math.max(r.left + r.width / 2 - 128, 8), window.innerWidth - 264);
    const above = r.top > 280;
    tip = { ev, x, y: above ? r.top - 10 : r.bottom + 10, above };
  }

  function hideTip() {
    tip = null;
  }
</script>

{#if year !== null && nodes.length > 0}
  <div class="rounded-box border border-base-300 bg-base-100 overflow-x-auto" onscroll={hideTip}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={width}
      height={svgHeight}
      role="group"
      aria-label={`Timeline of competitions in ${year}`}
      class="block max-w-none"
    >
      {#each months as mo}
        {#if !mo.noLine}
        <line
          x1={mo.x}
          y1={topMinY - 6}
          x2={mo.x}
          y2={bottomMaxY + 8}
          style="stroke: var(--color-base-content); stroke-width: 1; opacity: 0.1"
          aria-hidden="true"
        />
        {/if}
        <text
          x={mo.x + PITCH / 2}
          y={monthY}
          font-size="11"
          text-anchor="middle"
          style="fill: var(--color-base-content); opacity: 0.5"
          aria-hidden="true"
        >
          {mo.label}
        </text>
      {/each}

      <line
        x1="0"
        y1={mainY}
        x2={width - 40}
        y2={mainY}
        style="stroke: var(--color-base-content); stroke-width: {STROKE}; opacity: 0.4"
        aria-hidden="true"
      />

      {#each nodes as node (node.ev.id)}
        {@const dimmed = hoverId !== null && hoverId !== node.ev.id}
        <g
          class="transition-opacity duration-200 {dimmed ? 'opacity-20' : ''}"
          aria-hidden="true"
          onmouseenter={(e) => showTip(e, node.ev)}
          onmouseleave={hideTip}
        >
          <path
            d={node.d}
            style="stroke: var(--color-base-content); stroke-width: {STROKE}; fill: none; stroke-linecap: round; stroke-linejoin: round"
          />
        </g>
      {/each}

      {#each nodes as node (node.ev.id)}
        {@const dimmed = hoverId !== null && hoverId !== node.ev.id}
        <a
          href={`/events/${node.ev.id}`}
          aria-label={labelFor(node.ev)}
          class="transition-opacity duration-200 {dimmed ? 'opacity-20' : ''}"
          onmouseenter={(e) => showTip(e, node.ev)}
          onmouseleave={hideTip}
          onfocusin={(e) => {
            focusedId = node.ev.id;
            showTip(e, node.ev);
          }}
          onfocusout={() => {
            focusedId = null;
            hideTip();
          }}
        >
          <rect x={node.hitX} y={node.hitY} width={node.hitW} height="38" fill="transparent" />
          {#if focusedId === node.ev.id}
            <rect
              x={node.hitX - 2}
              y={node.hitY - 2}
              width={node.hitW + 4}
              height="42"
              rx="3"
              style="fill: none; stroke: var(--color-primary); stroke-width: 1.5; stroke-dasharray: 4 3"
            />
          {/if}
          <text
            x={node.labelX}
            y={node.nameY}
            font-size="12.5"
            font-weight="600"
            style="fill: var(--color-base-content); stroke: var(--color-base-100); stroke-width: 4; paint-order: stroke; stroke-linejoin: round"
            aria-hidden="true"
          >
            {node.short}
          </text>
          <text
            x={node.dateX}
            y={node.dateY}
            font-size="10.5"
            style="fill: var(--color-base-content); opacity: 0.6"
            aria-hidden="true"
          >
            {dateRange(node.ev)}
          </text>
          <g
            transform={`translate(${node.x + node.rise - STUB - CK_CELL}, ${node.nameY - CK_CELL})`}
            aria-hidden="true"
          >
            <rect x="0" y="0" width={CK_CELL} height={CK_CELL} style="fill: {node.ckA}" />
            <rect x={CK_CELL} y="0" width={CK_CELL} height={CK_CELL} style="fill: {node.ckB}" />
            <rect x="0" y={CK_CELL} width={CK_CELL} height={CK_CELL} style="fill: {node.ckB}" />
            <rect x={CK_CELL} y={CK_CELL} width={CK_CELL} height={CK_CELL} style="fill: {node.ckA}" />
            <rect
              x="0"
              y="0"
              width={CK_CELL * 2}
              height={CK_CELL * 2}
              rx={CK_CELL / 2}
              fill="none"
              style="stroke: var(--color-base-100); stroke-width: 3"
            />
          </g>
        </a>
      {/each}

      {#each weeks as w}
        {@const hasNational = w.comps.some((c) => c.is_national)}
        <g aria-hidden="true">
          <circle
            cx={(w.col - startWeek) * PITCH + PITCH / 2}
            cy={mainY}
            r="6"
            style="fill: var(--color-base-100); stroke: var(--color-base-content); stroke-width: {STROKE}"
          />
          {#if hasNational}
            <circle
              cx={(w.col - startWeek) * PITCH + PITCH / 2}
              cy={mainY}
              r="9.5"
              style="fill: none; stroke: var(--color-accent); stroke-width: 2"
            />
          {/if}
        </g>
      {/each}
    </svg>
  </div>
{/if}

{#if tip}
  <div
    role="tooltip"
    aria-hidden="true"
    class="pointer-events-none fixed z-50 w-64 rounded-box border border-base-300 bg-base-100 p-3 shadow-lg"
    style="left: {tip.x}px; top: {tip.y}px; {tip.above ? 'transform: translateY(-100%)' : ''}"
  >
    <p class="text-sm font-semibold">{tip.ev.name}</p>
    <p class="text-xs text-base-content/70 mt-0.5">{dateRange(tip.ev)}</p>
    <div class="flex flex-wrap items-center gap-1.5 mt-2">
      {#if tip.ev.discipline === "WAG"}
        <span class="badge badge-primary badge-sm">WAG</span>
      {:else if tip.ev.discipline === "MAG"}
        <span class="badge badge-secondary badge-sm">MAG</span>
      {:else}
        <span class="badge badge-primary badge-sm">WAG</span>
        <span class="badge badge-secondary badge-sm">MAG</span>
      {/if}
      {#if tip.ev.is_national}
        <span class="badge badge-accent badge-sm">Nationals</span>
      {/if}
    </div>
    {#if tip.ev.host_club}
      {@const region = regionFor(tip.ev)}
      <div class="mt-2">
        {#if region}
          <RegionBadge region={region} colors={REGION_PALETTES[region] ?? []} label={tip.ev.host_club} truncate />
        {:else}
          <span class="text-xs text-base-content/70">{tip.ev.host_club}</span>
        {/if}
      </div>
    {/if}
  </div>
{/if}
