---
name: Emerald Pulse Analytics
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3c4a43'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#6c7a73'
  outline-variant: '#bbcac1'
  surface-tint: '#006c4f'
  primary: '#006c4f'
  on-primary: '#ffffff'
  primary-container: '#00b386'
  on-primary-container: '#003d2c'
  inverse-primary: '#50ddad'
  secondary: '#575e70'
  on-secondary: '#ffffff'
  secondary-container: '#d9dff5'
  on-secondary-container: '#5c6274'
  tertiary: '#494bd6'
  on-tertiary: '#ffffff'
  tertiary-container: '#9093ff'
  on-tertiary-container: '#170eae'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#71fac8'
  primary-fixed-dim: '#50ddad'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#dce2f7'
  secondary-fixed-dim: '#c0c6db'
  on-secondary-fixed: '#141b2b'
  on-secondary-fixed-variant: '#404758'
  tertiary-fixed: '#e1e0ff'
  tertiary-fixed-dim: '#c0c1ff'
  on-tertiary-fixed: '#07006c'
  on-tertiary-fixed-variant: '#2f2ebe'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.015em
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.03em
  data-metric:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  data-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xxs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style

This design system establishes an ultra-refined, high-precision analytics workspace built specifically for engineering intelligence, weekly review cadences, and operational pulse-checks. The brand personality blends institutional rigor with modern fintech vitality: razor-sharp, transparent, disciplined, and proactive. 

The emotional response must be total confidence under high cognitive load. Data is never decorative; it is rendered with calibrated typographic scale, decisive data visualization geometry, and immediate semantic status awareness.

The design movement combines **Modern High-Precision Corporate SaaS** with **Tactile Subtlety**:
- Crisp slate background layers and structural hairline borders define visual boundaries without relying on noisy shadows.
- Vibrant, signature emerald accents punctuate actionable moments and positive operational throughput.
- Typography provides an executive-grade cadence: functional, rhythmic, and legible across dense data grids, funnel visualizations, and pipeline monitors.

## Colors

The palette is tuned for high-density, long-session readability under daylight conditions while retaining crisp contrast ratios meeting WCAG 2.1 AA/AAA compliance.

### Brand Core
- **Primary (`#00B386`)**: Signature emerald green. Utilized for critical positive metrics, key actions, active navigation states, and confirmed completion indicators. A brighter tint (`#00D09C`) serves as an interactive hover/accent state.
- **Secondary (`#111827`)**: Deep navy-slate. Anchors dominant typography, high-impact cards, top-tier metric readouts, and primary active controls.
- **Tertiary (`#6366F1`)**: Indigo-violet. Reserved for synthetic review metrics, secondary pipeline streams, predictive trend overlays, and comparative timelines.
- **Neutral (`#64748B`)**: Slate gray. Calibrated for secondary metadata, column borders, disabled components, and structural dividers.

### Canvas & Surface Hierarchy
- **Base Canvas (`#F8FAFC`)**: Soft, anti-glare slate canvas preventing eye fatigue during lengthy reviews.
- **Surface Layer 01 (`#FFFFFF`)**: Pure white cards, metrics modules, and primary tables.
- **Surface Layer 02 (`#F1F5F9`)**: Sub-tables, filter bars, code/hash chips, and inset data wells.
- **Surface Layer 03 (`#E2E8F0`)**: Hairline outlines and interactive hover foundations.

### High-Contrast Review Status Tokens
Review states must be immediately scannable without ambiguity:
- **Completed**: `#00875A` text on `#E3FCEF` surface with `#ABF5D1` border.
- **Running / Active**: `#0052CC` text on `#DEEBFF` surface with `#B3D4FF` border, accented with an emerald-pulsing beacon dot.
- **Partial**: `#B76E00` text on `#FFF0B3` surface with `#FFE380` border.
- **Failed**: `#DE350B` text on `#FFEBE6` surface with `#FFBDAD` border.
- **Dry Run**: `#5243AA` text on `#EAE6FF` surface with `#C0B6F2` border.
- **Pending**: `#475569` text on `#F1F5F9` surface with `#CBD5E1` border.

## Typography

The type system balances technical rigor with structural authority:
- **Headings & Quantitative Accents (`Plus Jakarta Sans`)**: Delivers geometric clarity and structural weight. Used for page titles, modal heads, KPI figures, and rating aggregates.
- **Body & Data Grid (`Inter`)**: Deployed for high-density tables, multi-column logs, execution telemetry, and analytical annotations. Tabular figures (`tnum`) must be forced on all numeric displays to eliminate horizontal jitter when values refresh in real time.
- **Technical & Tracing (`JetBrains Mono`)**: Targeted exclusively for git hashes, run IDs, pipeline timestamps, and dry-run query previews.

Letter tracking tightens deliberately as font sizes scale upward to maintain visual cohesion across wide desktop viewports.

## Layout & Spacing

The layout model is anchored on a **fluid 12-column grid** configured for rapid contextual data parsing.

### Grid & Breakpoints
- **Desktop (1280px and above)**: 12 columns, `1.25rem` (20px) gutters, and `2rem` (32px) canvas margin. Supports persistent side navigation, unified 4-up metric stat ribbons, and side-by-side funnel/timeline visualizations.
- **Tablet (768px – 1279px)**: 8 columns, `1rem` (16px) gutters, `1.5rem` (24px) margin. Navigation shifts to a collapsible drawer; KPI ribbons reflow into 2x2 grids.
- **Mobile (< 768px)**: 4 columns, `0.75rem` (12px) gutters, `1rem` (16px) outer margin. Visual funnels stack linearly; pipeline timelines convert to stacked stepped cards.

### Spacing Philosophy
- Base layout rhythm operates on a standard **4px/8px incremental grid**.
- Use `space-xs` and `space-sm` for compact component padding, badge insets, and micro-metrics.
- Use `space-md` for standard card padding, form field gaps, and list item spacing.
- Use `space-lg` and `space-xl` strictly for macro card gaps and major thematic section breaks.

## Elevation & Depth

This design system avoids heavy drop shadows, opting instead for **low-contrast outlines, tonal surface stacking, and microscopic border tints**:

- **Level 0 (Canvas Base)**: `#F8FAFC`. Completely flat; defines background boundaries.
- **Level 1 (Card & Module Foundation)**: `#FFFFFF` background bound by a crisp 1px solid `#E2E8F0` border. Standard elevation for KPI modules, review lists, and rating distribution breakdowns. No ambient shadow is required on standard views.
- **Level 2 (Interactive Floating / Active Filter Surface)**: `#FFFFFF` surrounded by a hairline `#CBD5E1` border, backed by a soft ambient tint: `box-shadow: 0 4px 12px -2px rgba(17, 24, 39, 0.05), 0 2px 6px -1px rgba(17, 24, 39, 0.02)`.
- **Level 3 (Modals, Slide-over Run Detail Drawers, Popovers)**: `#FFFFFF` layered over an overlay scrim (`rgba(15, 23, 42, 0.4)` backdrop blur of `4px`). Shadow profile: `box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`.
- **Level Inset (Data Insets & Code Wells)**: `#F1F5F9` background with an internal hairline border (`border: 1px solid #E2E8F0`). Provides tactile recession for execution logs and terminal output.

## Shapes

The geometric architecture is engineered with a **Balanced Rounded (Level 2)** language:
- Standard elements (buttons, inputs, status badges, dropdowns) carry a crisp **0.5rem (8px)** radius, giving them modern ergonomics without looking toy-like.
- Cards, modal containers, and metric summary panels carry **1rem (16px)** (`rounded-lg`).
- Feature cards, pipeline execution tracks, and slide-in panels use **1.5rem (24px)** (`rounded-xl`).
- Status indicator pills and review author avatars utilize full circular rounding (`9999px`).

## Components

### Buttons
- **Primary**: Solid emerald `#00B386` background, `#FFFFFF` text, `font-weight: 600`, 8px radius. Hover shifts to `#009E75`; active state compresses slightly (`transform: scale(0.99)`).
- **Secondary / Outlined**: `#FFFFFF` background, `#111827` text, 1px solid `#E2E8F0`. Hover triggers `#F8FAFC` background and `#CBD5E1` border.
- **Tertiary / Ghost**: Transparent fill, `#64748B` text. Hover triggers `#F1F5F9` background and `#111827` text.
- **Destructive**: `#FEE2E2` fill, `#DC2626` text, 1px solid `#FECACA`.

### Review Status Badges
Status badges are compact, high-contrast, uppercase metadata tokens:
- Height: 24px, padding: `2px 8px`, border-radius: `9999px`, typography: `label-sm`.
- **Completed**: `#E3FCEF` background, `#00875A` text, `#ABF5D1` border.
- **Running**: `#DEEBFF` background, `#0052CC` text, `#B3D4FF` border. Accompanied by a 6px pulsating `#00D09C` dot.
- **Partial**: `#FFF0B3` background, `#B76E00` text, `#FFE380` border.
- **Failed**: `#FFEBE6` background, `#DE350B` text, `#FFBDAD` border.
- **Dry Run**: `#EAE6FF` background, `#5243AA` text, `#C0B6F2` border.
- **Pending**: `#F1F5F9` background, `#475569` text, `#CBD5E1` border.

### Metric KPI Cards
- White surface, 1px solid `#E2E8F0`, 16px radius, `1.25rem` internal padding.
- Upper row: Metric label in `label-md` uppercase slate (`#64748B`) paired with a categorical micro-icon.
- Center row: Quantitative score in `data-metric` (`Plus Jakarta Sans`, 32px, `#111827`).
- Bottom row: Inline delta badge with emerald up-trend (`+12.4%`) or crimson down-trend (`-3.2%`), accompanied by comparison timeline baseline ("vs last week").

### Data Tables & Review Lists
- Row height: 48px standard, 40px compact.
- Header row: `#F8FAFC` background, 1px solid `#E2E8F0` top/bottom border, `#475569` text in `label-sm` tracking.
- Cells: Vertical alignment centered, hairline horizontal borders between rows (`#F1F5F9`). No vertical borders.
- Hover state: Row background tints smoothly to `#F8FAFC`.

### Funnel & Distribution Visualizations
- Funnel steps utilize graded opacity steps of emerald (`#00B386` to `#00D09C` to `#A7F3D0`) rendered as sharp, horizontally stacked segment blocks with numeric transition conversion markers suspended between stages.
- Rating distributions feature a 5-tier horizontal bar system: track background is `#F1F5F9` (4px height, full radius); progress fill is `#00B386` with tabular count markers aligned right in `label-sm`.

### Pipeline Execution Timelines
- Horizontal stepper for active review runs: stages interconnected by 2px lines (`#00B386` for completed, `#E2E8F0` for pending).
- Stage nodes contain icon indicators with hover tooltips showing duration in seconds and error stack-traces where applicable.

### Form Inputs & Filters
- Inactive: `#FFFFFF` fill, 1px solid `#CBD5E1`, 8px radius, 36px height, text in `body-md`.
- Focus: 1px solid `#00B386` border paired with an emerald ring: `box-shadow: 0 0 0 3px rgba(0, 179, 134, 0.15)`.
- Dropdown select chips: Compact `#F1F5F9` pills with removable trailing chevron/close icon.