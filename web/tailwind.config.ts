import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";
import {
  borderRadius,
  darkColors,
  fontFamily,
  fontSize,
  lightColors,
  spacing,
  statusDark,
  statusLight,
  type StatusKey,
} from "./src/styles/tokens";

const statusKeys = Object.keys(statusLight) as StatusKey[];
const parts = ["fg", "bg", "border"] as const;

/** `text-primary` etc. resolve to CSS variables so one class works in both themes. */
type ColorTree = { [key: string]: string | ColorTree };

const colors: ColorTree = Object.fromEntries(
  Object.keys(lightColors).map((name) => [name, `var(--color-${name})`]),
);
colors["status"] = Object.fromEntries(
  statusKeys.map((key) => [
    key,
    Object.fromEntries(parts.map((part) => [part, `var(--status-${key}-${part})`])) as ColorTree,
  ]),
);

function variables(
  palette: Record<string, string>,
  status: typeof statusLight,
): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const [name, hex] of Object.entries(palette)) vars[`--color-${name}`] = hex;
  for (const key of statusKeys) {
    for (const part of parts) vars[`--status-${key}-${part}`] = status[key][part];
  }
  return vars;
}

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: { colors, borderRadius, spacing, fontFamily, fontSize },
  },
  plugins: [
    plugin(({ addBase }) => {
      addBase({
        ":root": { colorScheme: "light", ...variables(lightColors, statusLight) },
        ".dark": { colorScheme: "dark", ...variables(darkColors, statusDark) },
      });
    }),
  ],
} satisfies Config;
