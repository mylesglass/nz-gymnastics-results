<script lang="ts">
  import mapData from "@svg-maps/new-zealand";
  import { REGION_PALETTES } from "./regions";

  let {
    active = null,
    onSelect = () => {},
  }: {
    active?: string | null;
    onSelect?: (region: string) => void;
  } = $props();

  const paths = new Map(mapData.locations.map((l) => [l.id, l.path]));

  interface RegionConfig {
    name: string;
    ids: string[];
    clip?: { x: number; y: number; w: number; h: number };
  }

  const REGION_CONFIGS: RegionConfig[] = [
    { name: "Northland", ids: ["ntl"] },
    { name: "Harbour", ids: ["auk"], clip: { x: 320, y: 78, w: 60, h: 22 } },
    { name: "Auckland", ids: ["auk"], clip: { x: 320, y: 100, w: 60, h: 22 } },
    { name: "Counties - Manukau", ids: ["auk"], clip: { x: 320, y: 122, w: 60, h: 23 } },
    { name: "Waikato", ids: ["wko"] },
    { name: "Bay of Plenty", ids: ["bop"] },
    { name: "Hawkes Bay / Poverty Bay", ids: ["gis", "hkb"] },
    { name: "Taranaki", ids: ["tki"] },
    { name: "Manawatu - Whanganui", ids: ["mwt"] },
    { name: "Wellington", ids: ["wgn"] },
    { name: "Top of the South", ids: ["tas", "nsn", "mbh"] },
    { name: "Canterbury", ids: ["can"], clip: { x: 140, y: 370, w: 185, h: 110 } },
    { name: "Aorangi", ids: ["can"], clip: { x: 140, y: 480, w: 185, h: 60 } },
    { name: "Otago", ids: ["ota"] },
    { name: "Southland", ids: ["stl"] },
  ];

  const NEUTRAL_IDS = ["wtc"];

  const CLIP_CONFIGS = REGION_CONFIGS.filter((c) => c.clip);
  const CLIP_ID_BY_NAME = new Map(CLIP_CONFIGS.map((c, i) => [c.name, `nz-clip-${i}`]));
  const CHECKER_BY_NAME = new Map(REGION_CONFIGS.map((c, i) => [c.name, `url(#nz-checker-${i})`]));

  function regionPrimary(name: string): string {
    return REGION_PALETTES[name]?.[0] ?? "var(--color-primary)";
  }

  function regionSecondary(name: string): string {
    return REGION_PALETTES[name]?.[1] ?? regionPrimary(name);
  }

  const SCROLL_DIRECTIONS: [number, number][] = [
    [-80, -20], [-80, 20], [80, -20], [80, 20],
    [-20, -80], [-20, 80], [20, -80], [20, 80],
    [-80, 0], [80, 0], [0, -80], [0, 80],
  ];

  function pick(i: number, n: number): number {
    let h = i + 1;
    h = (h * 9301 + 49297) % 233280;
    return h % n;
  }

  function scrollFor(i: number): { x: number; y: number; duration: number } {
    const [x, y] = SCROLL_DIRECTIONS[pick(i, SCROLL_DIRECTIONS.length)];
    return { x, y, duration: 3 + pick(i, 5) };
  }
</script>

<svg
  viewBox="0 0 525 989"
  aria-label="Map of New Zealand with selectable regions"
  class="w-full h-auto"
>
  <defs>
    {#each CLIP_CONFIGS as c, i}
      <clipPath id="nz-clip-{i}">
        <rect x={c.clip.x} y={c.clip.y} width={c.clip.w} height={c.clip.h} />
      </clipPath>
    {/each}
  </defs>

  {#each NEUTRAL_IDS as id}
    {#if paths.has(id)}
      <path d={paths.get(id)} class="nz-neutral" />
    {/if}
  {/each}

  {#each REGION_CONFIGS as c, i}
    {@const clipId = CLIP_ID_BY_NAME.get(c.name) ?? null}
    {@const isActive = active === c.name}
    {@const regionColor = regionPrimary(c.name)}
    {@const checker = CHECKER_BY_NAME.get(c.name) ?? "var(--color-primary)"}
    {@const p = regionPrimary(c.name)}
    {@const s = regionSecondary(c.name)}
    {@const scroll = scrollFor(i)}
    <g
      role="button"
      tabindex="0"
      aria-label={c.name}
      aria-pressed={isActive}
      class="nz-region"
      class:nz-active={isActive}
      style="--region-color: {regionColor}; --checker: {checker}; --scroll-x: {scroll.x}px; --scroll-y: {scroll.y}px; --scroll-duration: {scroll.duration}s;"
      onclick={() => onSelect(c.name)}
      onkeydown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(c.name);
        }
      }}
    >
      <pattern id="nz-checker-{i}" width="20" height="20" patternUnits="userSpaceOnUse">
        <rect width="10" height="10" fill={p} />
        <rect x="10" y="10" width="10" height="10" fill={p} />
        <rect x="10" width="10" height="10" fill={s} />
        <rect y="10" width="10" height="10" fill={s} />
      </pattern>
      {#each c.ids as id}
        {#if paths.has(id)}
          <path d={paths.get(id)} clip-path={clipId ? `url(#${clipId})` : undefined} />
        {/if}
      {/each}
    </g>
  {/each}
</svg>

<style>
  .nz-region {
    fill: var(--color-accent);
    stroke: var(--color-base-content);
    stroke-opacity: 0.12;
    stroke-width: 0.6;
    stroke-linejoin: round;
    transition: fill 0.3s ease, opacity 0.3s ease, stroke 0.3s ease;
    cursor: pointer;
    opacity: 0.85;
  }
  .nz-region:hover {
    fill: var(--checker, var(--region-color, var(--color-primary)));
    stroke: var(--color-base-content);
    stroke-opacity: 0.5;
    stroke-width: 0.8;
    opacity: 1;
  }
  .nz-active {
    fill: var(--checker, var(--region-color, var(--color-primary)));
    stroke: var(--color-base-content);
    stroke-opacity: 0.5;
    stroke-width: 0.8;
    opacity: 1;
  }
  @media (prefers-reduced-motion: no-preference) {
    .nz-region:hover pattern,
    .nz-active pattern {
      animation: nz-checker-scroll var(--scroll-duration, 4s) linear infinite;
    }
  }
  @keyframes nz-checker-scroll {
    from {
      transform: translate(0, 0);
    }
    to {
      transform: translate(var(--scroll-x, -80px), var(--scroll-y, -20px));
    }
  }
  .nz-neutral {
    fill: var(--color-accent);
    opacity: 0.5;
    stroke: var(--color-base-content);
    stroke-opacity: 0.12;
    stroke-width: 0.6;
    stroke-linejoin: round;
  }
  .nz-region:focus-visible {
    outline: 3px solid var(--color-primary);
    outline-offset: 2px;
    stroke: var(--color-base-content);
    stroke-opacity: 0.8;
    stroke-width: 1.5;
  }
</style>
