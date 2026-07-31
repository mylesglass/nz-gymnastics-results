<script lang="ts">
  import mapData from "@svg-maps/new-zealand";

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
</script>

<svg
  viewBox="0 0 525 989"
  role="img"
  aria-label="Map of New Zealand"
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
      <path d={paths.get(id)} class="nz-neutral" stroke-linejoin="round" />
    {/if}
  {/each}

  {#each REGION_CONFIGS as c}
    {@const clipId = CLIP_ID_BY_NAME.get(c.name) ?? null}
    {@const isActive = active === c.name}
    <g
      role="button"
      tabindex="0"
      aria-label={c.name}
      class="nz-region"
      class:nz-active={isActive}
      onclick={() => onSelect(c.name)}
      onkeydown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect(c.name);
      }}
    >
      {#each c.ids as id}
        {#if paths.has(id)}
          <path d={paths.get(id)} clip-path={clipId ? `url(#${clipId})` : undefined} />
        {/if}
      {/each}
      <title>{c.name}</title>
    </g>
  {/each}
</svg>

<style>
  .nz-region {
    fill: var(--color-base-300);
    stroke: var(--color-base-content);
    stroke-opacity: 0.35;
    stroke-width: 0.6;
    stroke-linejoin: round;
    transition: fill 0.2s ease, opacity 0.2s ease;
    cursor: pointer;
    opacity: 0.85;
  }
  .nz-region:hover {
    fill: var(--color-primary);
    opacity: 1;
  }
  .nz-active {
    fill: var(--color-primary);
    stroke: var(--color-primary-content);
    stroke-opacity: 1;
    stroke-width: 0.8;
    opacity: 1;
  }
  .nz-neutral {
    fill: var(--color-base-200);
    stroke: var(--color-base-content);
    stroke-opacity: 0.35;
    stroke-width: 0.6;
    stroke-linejoin: round;
  }
  .nz-region:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: -2px;
  }
</style>
