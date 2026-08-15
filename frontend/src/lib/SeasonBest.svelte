<script lang="ts">
  interface TabData {
    columns: string[];
    rows: Record<string, unknown>[];
  }

  interface AppBest {
    prefix: string;
    score: number;
    d: number | null;
    eventName: string;
    roundType: string;
  }

  interface AABest {
    score: number;
    d: number | null;
    eventName: string;
    roundType: string;
  }

  let { year, tabs }: { year: string; tabs: Record<string, TabData> } = $props();

  let uid: number;
  {
    uid = Math.floor(Math.random() * 1e9);
  }

  const APP_LABELS: Record<string, string> = {
    vt: "Vault",
    ub: "Uneven Bars",
    bb: "Balance Beam",
    fx: "Floor",
    ph: "Pommel Horse",
    sr: "Still Rings",
    pb: "Parallel Bars",
    hb: "Horizontal Bar",
  };

  function prefixesFor(columns: string[]): string[] {
    const prefixes: string[] = [];
    const seen = new Set<string>();
    for (const c of columns) {
      const m = c.match(/^([a-z]{2,3})(?:-\d+)?-total$/);
      if (m && !seen.has(m[1])) {
        seen.add(m[1]);
        prefixes.push(m[1]);
      }
    }
    return prefixes;
  }

  function bestsFor(rows: Record<string, unknown>[], prefixes: string[]): AppBest[] {
    const result: AppBest[] = [];
    for (const p of prefixes) {
      let best: AppBest | null = null;
      for (const row of rows) {
        const v = row[`${p}-total`];
        if (v == null || v === "DNS") continue;
        const num = Number(v);
        if (Number.isNaN(num)) continue;
        if (!best || num > best.score) {
          const dv = row[`${p}-d`];
          const d = dv == null ? null : Number(dv);
          best = {
            prefix: p,
            score: num,
            d: d != null && !Number.isNaN(d) ? d : null,
            eventName: String(row.event_name ?? ""),
            roundType: String(row["round-type"] ?? ""),
          };
        }
      }
      if (best) result.push(best);
    }
    return result;
  }

  let bests = $derived.by(() => {
    const out: AppBest[] = [];
    for (const key of ["wag", "mag"]) {
      const d = tabs[key];
      if (!d) continue;
      out.push(...bestsFor(d.rows, prefixesFor(d.columns)));
    }
    return out;
  });

  let seasonAA = $derived(bests.reduce((sum, b) => sum + b.score, 0));
  let aaText = $derived(seasonAA.toFixed(3));
  let aaD = $derived.by(() => {
    let sum = 0;
    let count = 0;
    for (const b of bests) {
      if (b.d != null) {
        sum += b.d;
        count++;
      }
    }
    return count ? sum : null;
  });

  let bestAA = $derived.by(() => {
    let best: AABest | null = null;
    for (const key of ["wag", "mag"]) {
      const d = tabs[key];
      if (!d) continue;
      const prefixes = prefixesFor(d.columns);
      for (const row of d.rows) {
        const rt = String(row["round-type"] ?? "").toLowerCase();
        if (rt.includes("apparatus final") || rt.includes("day 2")) {
          const fullSet = prefixes.every((p) => {
            const t = row[`${p}-total`];
            return t != null && t !== "DNS";
          });
          if (!fullSet) continue;
        }
        const v = row["aa-score"];
        if (v == null) continue;
        const num = Number(v);
        if (Number.isNaN(num)) continue;
        if (!best || num > best.score) {
          let dSum = 0;
          let dCount = 0;
          for (const p of prefixes) {
            const dv = row[`${p}-d`];
            if (dv == null) continue;
            const dn = Number(dv);
            if (Number.isNaN(dn)) continue;
            dSum += dn;
            dCount++;
          }
          best = {
            score: num,
            d: dCount ? dSum : null,
            eventName: String(row.event_name ?? ""),
            roundType: String(row["round-type"] ?? ""),
          };
        }
      }
    }
    return best;
  });

  function tipId(b: AppBest): string {
    return `sb-tip-${b.prefix}-${uid}`;
  }

  function aaTipId(): string {
    return `sb-tip-aa-${uid}`;
  }

  function aaBestTipId(): string {
    return `sb-tip-aabest-${uid}`;
  }
</script>

{#if bests.length}
  <section class="card bg-base-200 border border-base-300 shadow-sm w-fit max-md:w-full" aria-label="{year} season best">
    <div class="card-body p-3 gap-1">
      <h2 class="card-title text-sm">{year} Personal Bests</h2>
      <p class="text-xs text-base-content/70">Best score on each apparatus this season, plus the Best Possible AA</p>
      <div class="flex flex-wrap items-center gap-x-5 gap-y-2 max-md:justify-center max-md:gap-x-3 max-md:gap-y-3">
        {#each bests as b}
          <div class="dropdown dropdown-hover dropdown-bottom dropdown-end">
            <button
              type="button"
              class="flex flex-col items-center cursor-pointer border-b border-dotted border-base-content/40 hover:border-base-content/70"
              aria-label={`${b.prefix.toUpperCase()} ${b.score.toFixed(3)}${b.d != null ? `, D ${b.d.toFixed(1)}` : ""}, ${APP_LABELS[b.prefix] ?? b.prefix.toUpperCase()}`}
              aria-describedby={tipId(b)}
            >
              <span class="text-xs text-base-content/70">{b.prefix.toUpperCase()}</span>
              <span class="bg-secondary text-secondary-content rounded px-1.5 py-0.5 font-semibold leading-none">{b.score.toFixed(3)}</span>
              {#if b.d != null}
                <span class="text-[10px] text-base-content/60">D {b.d.toFixed(1)}</span>
              {/if}
            </button>
            <div
              id={tipId(b)}
              role="tooltip"
              class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs"
            >
              <div class="text-xs mb-1 text-left text-neutral-content/90">
                {year} — {APP_LABELS[b.prefix] ?? b.prefix.toUpperCase()}
              </div>
              <div class="divider my-1"></div>
              <div class="flex flex-col gap-0.5 whitespace-nowrap">
                <div class="flex justify-between gap-4">
                  <span class="font-semibold">Competition</span
                  ><span>{b.eventName || "—"}</span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="font-semibold">Round</span
                  ><span>{b.roundType || "—"}</span>
                </div>
              </div>
            </div>
          </div>
        {/each}
        {#if bestAA}
          <div class="dropdown dropdown-hover dropdown-bottom dropdown-end">
            <button
              type="button"
              class="flex flex-col items-center cursor-pointer border-b border-dotted border-base-content/40 hover:border-base-content/70"
              aria-label={`AA ${bestAA.score.toFixed(3)}${bestAA.d != null ? `, D ${bestAA.d.toFixed(1)}` : ""}`}
              aria-describedby={aaBestTipId()}
            >
              <span class="text-xs text-base-content/70">AA</span>
              <span class="bg-secondary text-secondary-content rounded px-1.5 py-0.5 font-semibold leading-none">{bestAA.score.toFixed(3)}</span>
              {#if bestAA.d != null}
                <span class="text-[10px] text-base-content/60">D {bestAA.d.toFixed(1)}</span>
              {/if}
            </button>
            <div
              id={aaBestTipId()}
              role="tooltip"
              class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs"
            >
              <div class="text-xs mb-1 text-left text-neutral-content/90">
                {year} — Best All-Around
              </div>
              <div class="divider my-1"></div>
              <div class="flex flex-col gap-0.5 whitespace-nowrap">
                <div class="flex justify-between gap-4">
                  <span class="font-semibold">Competition</span
                  ><span>{bestAA.eventName || "—"}</span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="font-semibold">Round</span
                  ><span>{bestAA.roundType || "—"}</span>
                </div>
              </div>
            </div>
          </div>
        {/if}
        <div class="divider divider-horizontal ml-auto mr-0 max-md:hidden" aria-hidden="true"></div>
        <div class="md:hidden w-full h-px bg-base-300 my-2" aria-hidden="true"></div>
        <div class="dropdown dropdown-hover dropdown-bottom dropdown-end max-md:mx-auto">
          <button
            type="button"
            class="flex flex-col items-center cursor-pointer border-b border-dotted border-base-content/40 hover:border-base-content/70"
            aria-label={`Best Possible AA ${aaText}${aaD != null ? `, D ${aaD.toFixed(1)}` : ""}`}
            aria-describedby={aaTipId()}
          >
            <span class="text-xs text-base-content/70">Best Possible AA</span>
            <span class="bg-primary text-primary-content rounded px-1.5 py-0.5 font-semibold leading-none">{aaText}</span>
            {#if aaD != null}
              <span class="text-[10px] text-base-content/60">D {aaD.toFixed(1)}</span>
            {/if}
          </button>
          <div
            id={aaTipId()}
            role="tooltip"
            class="dropdown-content z-50 bg-neutral text-neutral-content rounded-box shadow-xl p-3 text-xs w-64"
          >
            <div class="text-xs mb-1 text-left text-neutral-content/90">
              {year} — Best Possible AA
            </div>
            <div class="divider my-1"></div>
            <p class="text-xs text-neutral-content/90 leading-snug">
              The best score this gymnast achieved on each apparatus in {year}, added together. This is not an all-around score actually achieved in a single competition.
            </p>
          </div>
        </div>
      </div>
    </div>
  </section>
{/if}
