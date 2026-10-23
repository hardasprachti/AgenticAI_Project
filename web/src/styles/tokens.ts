/**
 * Design tokens: the single source for Tailwind (tailwind.config.ts) and the contrast tests.
 *
 * Light colours are the `tailwind-config` of overview_groww_review_pulse/code.html (it rendered the
 * screenshots), not the DESIGN.md prose: primary is #006c4f, with #00b386 as the container fill.
 * There is no dark design, so the dark set is derived: surfaces from #0b1c30 / #213145, emerald
 * kept as the accent.
 */

export const lightColors = {
  "inverse-on-surface": "#eaf1ff",
  "on-tertiary": "#ffffff",
  "surface-variant": "#d3e4fe",
  "surface-container-high": "#dce9ff",
  "on-primary-fixed-variant": "#00513b",
  "on-primary-fixed": "#002116",
  secondary: "#575e70",
  "on-secondary-fixed-variant": "#404758",
  "surface-container-lowest": "#ffffff",
  "surface-container-low": "#eff4ff",
  "on-tertiary-fixed-variant": "#2f2ebe",
  surface: "#f8f9ff",
  "on-primary": "#ffffff",
  primary: "#006c4f",
  "primary-fixed-dim": "#50ddad",
  "on-tertiary-container": "#170eae",
  "inverse-surface": "#213145",
  "on-secondary-fixed": "#141b2b",
  "on-error-container": "#93000a",
  "on-surface-variant": "#3c4a43",
  "surface-dim": "#cbdbf5",
  background: "#f8f9ff",
  "inverse-primary": "#50ddad",
  "tertiary-container": "#9093ff",
  "error-container": "#ffdad6",
  "tertiary-fixed-dim": "#c0c1ff",
  error: "#ba1a1a",
  "secondary-fixed": "#dce2f7",
  "surface-container-highest": "#d3e4fe",
  "surface-container": "#e5eeff",
  "on-tertiary-fixed": "#07006c",
  "on-secondary": "#ffffff",
  "surface-tint": "#006c4f",
  "primary-fixed": "#71fac8",
  "on-secondary-container": "#5c6274",
  tertiary: "#494bd6",
  "surface-bright": "#f8f9ff",
  "outline-variant": "#bbcac1",
  "primary-container": "#00b386",
  "on-surface": "#0b1c30",
  "on-background": "#0b1c30",
  "secondary-container": "#d9dff5",
  // White on #00b386 is about 2.7:1; buttons use this dark green on the emerald fill instead.
  "on-primary-container": "#003d2c",
  outline: "#6c7a73",
  "on-error": "#ffffff",
  "tertiary-fixed": "#e1e0ff",
  "secondary-fixed-dim": "#c0c6db",
} as const;

export type ColorName = keyof typeof lightColors;

export const darkColors: Record<ColorName, string> = {
  ...lightColors,
  background: "#0b1c30",
  surface: "#0b1c30",
  "surface-dim": "#081525",
  "surface-bright": "#2b3d53",
  "surface-container-lowest": "#10243b",
  "surface-container-low": "#152a42",
  "surface-container": "#1a3049",
  "surface-container-high": "#213145",
  "surface-container-highest": "#2b3d53",
  "surface-variant": "#2b3d53",
  "on-surface": "#eaf1ff",
  "on-background": "#eaf1ff",
  "on-surface-variant": "#bbcac1",
  "inverse-surface": "#eaf1ff",
  "inverse-on-surface": "#213145",
  outline: "#86948c",
  "outline-variant": "#3c4a43",
  "surface-tint": "#50ddad",
  primary: "#50ddad",
  "on-primary": "#002116",
  "inverse-primary": "#006c4f",
  "primary-container": "#00b386",
  "on-primary-container": "#003d2c",
  secondary: "#c0c6db",
  "on-secondary": "#2a3041",
  "secondary-container": "#404758",
  "on-secondary-container": "#d9dff5",
  tertiary: "#c0c1ff",
  "on-tertiary": "#1c1b8c",
  "tertiary-container": "#2f2ebe",
  "on-tertiary-container": "#e1e0ff",
  error: "#ffb4ab",
  "on-error": "#690005",
  "error-container": "#93000a",
  "on-error-container": "#ffdad6",
};

export type StatusKey = "completed" | "running" | "partial" | "failed" | "dryrun" | "pending";
export type StatusColors = { fg: string; bg: string; border: string };

/**
 * Status badges (DESIGN.md prose). Text hexes that failed 4.5:1 at 11px against their background
 * were darkened until they passed; the original hex is noted beside each change.
 */
export const statusLight: Record<StatusKey, StatusColors> = {
  completed: { fg: "#006644", bg: "#e3fcef", border: "#abf5d1" }, // was #00875a
  running: { fg: "#0052cc", bg: "#deebff", border: "#b3d4ff" },
  partial: { fg: "#8a5300", bg: "#fff0b3", border: "#ffe380" }, // was #b76e00
  failed: { fg: "#c22e08", bg: "#ffebe6", border: "#ffbdad" }, // was #de350b
  dryrun: { fg: "#5243aa", bg: "#eae6ff", border: "#c0b6f2" },
  pending: { fg: "#475569", bg: "#f1f5f9", border: "#cbd5e1" },
};

export const statusDark: Record<StatusKey, StatusColors> = {
  completed: { fg: "#79f2c0", bg: "#0d3b2c", border: "#1f6f52" },
  running: { fg: "#a5c8ff", bg: "#0f2a52", border: "#2a4f8f" },
  partial: { fg: "#ffd666", bg: "#40300a", border: "#7a5a12" },
  failed: { fg: "#ffb4a2", bg: "#4a1710", border: "#8a3324" },
  dryrun: { fg: "#c9c0ff", bg: "#2a2159", border: "#4d41a0" },
  pending: { fg: "#cbd5e1", bg: "#1f2d40", border: "#3b4b61" },
};

export const borderRadius = {
  DEFAULT: "0.25rem",
  lg: "0.5rem",
  xl: "0.75rem",
  full: "9999px",
} as const;

export const spacing = {
  "space-xs": "0.25rem",
  "gutter-mobile": "0.75rem",
  "space-xl": "2rem",
  "space-xxs": "0.125rem",
  "space-md": "1rem",
  "space-lg": "1.5rem",
  "margin-mobile": "1rem",
  "space-2xl": "3rem",
  margin: "2rem",
  gutter: "1.25rem",
  "space-sm": "0.5rem",
} as const;

// @fontsource registers "<Family> Variable"; the plain family name stays as a fallback.
const jakarta = ["Plus Jakarta Sans Variable", "Plus Jakarta Sans", "sans-serif"];
const inter = ["Inter Variable", "Inter", "sans-serif"];
const mono = ["JetBrains Mono", "monospace"];

export const fontFamily = {
  "display-lg": jakarta,
  "data-code": mono,
  "data-metric": jakarta,
  "headline-xl": jakarta,
  "display-lg-mobile": jakarta,
  "headline-md": jakarta,
  "body-sm": inter,
  "body-md": inter,
  "label-lg": inter,
  "body-lg": inter,
  "label-md": inter,
  "label-sm": inter,
  "headline-lg": jakarta,
};

type FontSize = [string, { lineHeight: string; letterSpacing?: string; fontWeight: string }];

export const fontSize: Record<string, FontSize> = {
  "display-lg": ["40px", { lineHeight: "48px", letterSpacing: "-0.02em", fontWeight: "700" }],
  "data-code": ["12px", { lineHeight: "16px", fontWeight: "500" }],
  "data-metric": ["32px", { lineHeight: "36px", letterSpacing: "-0.02em", fontWeight: "700" }],
  "headline-xl": ["28px", { lineHeight: "36px", letterSpacing: "-0.015em", fontWeight: "600" }],
  "display-lg-mobile": [
    "30px",
    { lineHeight: "38px", letterSpacing: "-0.015em", fontWeight: "700" },
  ],
  "headline-md": ["18px", { lineHeight: "24px", letterSpacing: "-0.005em", fontWeight: "600" }],
  "body-sm": ["13px", { lineHeight: "18px", fontWeight: "400" }],
  "body-md": ["14px", { lineHeight: "20px", fontWeight: "400" }],
  "label-lg": ["14px", { lineHeight: "20px", fontWeight: "600" }],
  "body-lg": ["16px", { lineHeight: "24px", fontWeight: "400" }],
  "label-md": ["12px", { lineHeight: "16px", letterSpacing: "0.02em", fontWeight: "600" }],
  "label-sm": ["11px", { lineHeight: "14px", letterSpacing: "0.03em", fontWeight: "600" }],
  "headline-lg": ["22px", { lineHeight: "28px", letterSpacing: "-0.01em", fontWeight: "600" }],
};

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => channel(parseInt(h.slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.x contrast ratio between two #rrggbb colours (1 to 21). */
export function contrastRatio(hexA: string, hexB: string): number {
  const [hi, lo] = [luminance(hexA), luminance(hexB)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}
