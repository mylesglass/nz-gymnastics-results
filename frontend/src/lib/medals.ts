export const MEDAL_COLORS: Record<number, string> = {
  1: "#d4af37",
  2: "#a8a8a8",
  3: "#cd7f32",
};

export const MEDAL_LABELS: Record<number, string> = {
  1: "Gold",
  2: "Silver",
  3: "Bronze",
};

export function medalColor(rank: number | null | undefined): string | null {
  if (rank == null) return null;
  return MEDAL_COLORS[rank] ?? null;
}
