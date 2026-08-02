export const REGION_PALETTES: Record<string, string[]> = {
  "Aorangi":                 ["#008751", "#FFFFFF", "#000000"],
  "Auckland":                ["#0033A0", "#FFFFFF", "#C0C0C0"],
  "Bay of Plenty":           ["#002B49", "#FFC72C", "#FFFFFF"],
  "Canterbury":              ["#D32F2F", "#000000"],
  "Counties - Manukau":      ["#008080", "#FF6B00", "#000000"],
  "Harbour":                 ["#000000", "#800020"],
  "Hawkes Bay / Poverty Bay":["#000000", "#FFFFFF"],
  "Manawatu - Whanganui":    ["#0C2340", "#008751"],
  "Northland":               ["#0C2340", "#7BA4D5", "#FFFFFF"],
  "Otago":                   ["#002147", "#FFC72C"],
  "Southland":               ["#800000", "#0C2340", "#FFC72C"],
  "Taranaki":                ["#FFC72C", "#000000"],
  "Top of the South":        ["#00A3E0", "#FFFFFF", "#D32F2F"],
  "Waikato":                 ["#000000", "#D32F2F", "#FFC72C"],
  "Wellington":              ["#000000", "#FFC72C", "#FFFFFF"],
};

export const REGION_ORDER: string[] = [
  "Northland",
  "Harbour",
  "Auckland",
  "Counties - Manukau",
  "Waikato",
  "Bay of Plenty",
  "Taranaki",
  "Hawkes Bay / Poverty Bay",
  "Manawatu - Whanganui",
  "Wellington",
  "Top of the South",
  "Canterbury",
  "Aorangi",
  "Otago",
  "Southland",
];

export function textColor(hex: string): string {
  let h = hex.replace("#", "");
  let r = parseInt(h.substring(0, 2), 16);
  let g = parseInt(h.substring(2, 4), 16);
  let b = parseInt(h.substring(4, 6), 16);
  return (r * 0.299 + g * 0.587 + b * 0.114) > 160 ? "#111" : "#fff";
}

export function gradientTextColor(colors: string[]): string {
  if (!colors.length) return "#111";
  const lum = (hex: string) => {
    const h = hex.replace("#", "");
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return r * 0.299 + g * 0.587 + b * 0.114;
  };
  // Pick the palette stop furthest from luminance 128 so heading stays readable
  // regardless of where the gradient falls behind it.
  const stop = colors.reduce((best, c) =>
    Math.abs(lum(c) - 128) > Math.abs(lum(best) - 128) ? c : best
  );
  return lum(stop) > 160 ? "#111" : "#fff";
}

export function gradientBackground(colors: string[]): string {
  if (!colors.length) return "linear-gradient(135deg, #e5e7eb, #9ca3af)";
  const c0 = colors[0];
  const c1 = colors[1] ?? colors[0];
  return `linear-gradient(135deg, ${c0} 0%, ${c0} 40%, ${c1} 90%, ${c1} 100%)`;
}

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return r * 0.299 + g * 0.587 + b * 0.114;
}

// Prefer the palette's secondary colour for headings, but fall back to the
// contrast-derived text colour when it doesn't contrast with the primary.
export function headingColor(colors: string[]): string {
  if (colors.length < 2) return gradientTextColor(colors);
  const a = luminance(colors[0]);
  const b = luminance(colors[1]);
  if (Math.abs(a - b) < 50) return gradientTextColor(colors);
  return colors[1];
}
