export function ThemeChip({ themeId, label }: { themeId: string; label: string }) {
  return (
    <span
      data-theme-id={themeId}
      className="inline-flex items-center rounded-full border border-outline-variant bg-secondary-container px-space-sm py-space-xxs text-label-sm text-on-secondary-container"
    >
      {label}
    </span>
  );
}
