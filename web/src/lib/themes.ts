import type { RankedTheme } from "../api/types";

/** The catch-all theme: backend `theme_id_for("Other")`. Never one of the top themes. */
export const CATCH_ALL_THEME_ID = "other";

export interface Components {
  volume: number;
  recency: number;
  severity: number;
}

/** weight x component for each part of the score. Weights come from /api/config. */
export function weightedContributions(scores: Components, weights: Components): Components {
  return {
    volume: weights.volume * scores.volume,
    recency: weights.recency * scores.recency,
    severity: weights.severity * scores.severity,
  };
}

/**
 * Splits the ranked list for the theme matrix: the selected themes in `top` order, the catch-all
 * (excluded even when it scores highest), and everyone else in score order.
 */
export function splitSelected(ranked: RankedTheme[], top: string[]) {
  const byId = new Map(ranked.map((r) => [r.theme.theme_id, r]));
  const selected = top
    .map((id) => byId.get(id))
    .filter((r): r is RankedTheme => r !== undefined && r.theme.theme_id !== CATCH_ALL_THEME_ID);
  const chosen = new Set(selected.map((r) => r.theme.theme_id));
  return {
    selected,
    excludedOther: ranked.filter((r) => r.theme.theme_id === CATCH_ALL_THEME_ID),
    notSelected: ranked.filter(
      (r) => r.theme.theme_id !== CATCH_ALL_THEME_ID && !chosen.has(r.theme.theme_id),
    ),
  };
}
