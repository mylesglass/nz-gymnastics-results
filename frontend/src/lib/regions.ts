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

function srgbLuminance(hex: string): number {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16) / 255;
  const g = parseInt(h.substring(2, 4), 16) / 255;
  const b = parseInt(h.substring(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: number, b: number): number {
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

// Pick black or white text (whichever gives the higher WCAG contrast ratio)
// against the given background hex. Pure black (#000) rather than #111 so
// mid-tone greens/blues (e.g. #008751) clear the 4.5:1 AA bar.
export function textColor(hex: string): string {
  const bg = srgbLuminance(hex);
  const white = contrast(bg, 1);
  const black = contrast(bg, 0);
  return black > white ? "#000" : "#fff";
}

export function gradientTextColor(colors: string[]): string {
  if (!colors.length) return "#000";
  // Pick the palette stop furthest from luminance 0.5 so heading stays
  // readable regardless of where the gradient falls behind it.
  const stop = colors.reduce((best, c) =>
    Math.abs(srgbLuminance(c) - 0.5) > Math.abs(srgbLuminance(best) - 0.5) ? c : best
  );
  return textColor(stop);
}

export function gradientBackground(colors: string[]): string {
  if (!colors.length) return "linear-gradient(135deg, #e5e7eb, #9ca3af)";
  const c0 = colors[0];
  const c1 = colors[1] ?? colors[0];
  return `linear-gradient(135deg, ${c0} 0%, ${c0} 40%, ${c1} 90%, ${c1} 100%)`;
}

// Prefer the palette's secondary colour for headings, but fall back to the
// contrast-derived text colour when it doesn't contrast with the primary.
export function headingColor(colors: string[]): string {
  if (colors.length < 2) return gradientTextColor(colors);
  const a = srgbLuminance(colors[0]);
  const b = srgbLuminance(colors[1]);
  if (Math.abs(a - b) < 0.2) return gradientTextColor(colors);
  return colors[1];
}
