import {
  BookOpen,
  History,
  LayoutDashboard,
  Menu,
  Play,
  Monitor,
  Moon,
  Activity,
  SlidersHorizontal,
  Sun,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { isMockMode } from "../api/client";
import { RunControl } from "./RunControl";
import { RunControlProvider } from "./RunControlContext";
import { useMediaQuery } from "../lib/useMediaQuery";
import { useTheme, type Theme } from "../lib/theme";

/** Sidebar is fixed at and above this width; below it, it becomes a drawer. */
const SIDEBAR_QUERY = "(min-width: 1280px)";

type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  isActive: (pathname: string) => boolean;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", to: "/", icon: LayoutDashboard, isActive: (p) => p === "/" },
  {
    label: "Run Detail",
    to: "/runs/latest",
    icon: Activity,
    isActive: (p) => p.startsWith("/runs/"),
  },
  { label: "Run History", to: "/runs", icon: History, isActive: (p) => p === "/runs" },
  { label: "Publishing Ledger", to: "/ledger", icon: BookOpen, isActive: (p) => p === "/ledger" },
  { label: "Settings", to: "/settings", icon: SlidersHorizontal, isActive: (p) => p === "/settings" },
];

const THEME_OPTIONS: { value: Theme; label: string; icon: LucideIcon }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function LogoMark() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="#00b386" />
      <path
        d="M5 17h5l3-8 5 15 3-9h6"
        fill="none"
        stroke="#003d2c"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();
  return (
    <nav aria-label="Main" className="flex flex-col gap-space-xs">
      {NAV_ITEMS.map(({ label, to, icon: Icon, isActive }) => {
        const active = isActive(pathname);
        return (
          <Link
            key={label}
            to={to}
            aria-current={active ? "page" : undefined}
            onClick={onNavigate}
            className={
              "flex items-center gap-space-sm rounded-lg px-space-md py-space-sm transition-colors " +
              (active
                ? "bg-surface-container-high font-semibold text-primary"
                : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface")
            }
          >
            <Icon size={20} aria-hidden="true" />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function ThemeMenu() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const current = THEME_OPTIONS.find((option) => option.value === theme) ?? THEME_OPTIONS[2];
  const CurrentIcon = current.icon;

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    const onPointer = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open]);

  return (
    <div ref={wrapper} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Theme: ${current.label}`}
        onClick={() => setOpen((value) => !value)}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
      >
        <CurrentIcon size={18} aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Theme"
          className="absolute right-0 top-full z-50 mt-space-xs w-40 rounded-lg border border-outline-variant bg-surface-container-lowest p-space-xs"
        >
          {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="menuitemradio"
              aria-checked={theme === value}
              onClick={() => {
                setTheme(value);
                setOpen(false);
              }}
              className={
                "flex w-full items-center gap-space-sm rounded px-space-sm py-space-sm text-left text-body-md hover:bg-surface-container-low " +
                (theme === value ? "font-semibold text-primary" : "text-on-surface")
              }
            >
              <Icon size={16} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const wide = useMediaQuery(SIDEBAR_QUERY);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [runControlOpen, setRunControlOpen] = useState(false);
  const openButton = useRef<HTMLButtonElement>(null);
  const showDrawer = drawerOpen && !wide;

  useEffect(() => {
    if (!showDrawer) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDrawerOpen(false);
        openButton.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [showDrawer]);

  return (
    <RunControlProvider value={{ open: () => setRunControlOpen(true) }}>
    <div className="min-h-screen bg-background text-on-surface">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-space-md focus:top-space-md focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-space-md focus:py-space-sm focus:text-on-primary"
      >
        Skip to content
      </a>

      <header className="fixed left-0 right-0 top-0 z-50 h-16 border-b border-outline-variant bg-surface-container-lowest">
        <div className="flex h-16 items-center justify-between px-space-lg">
          <div className="flex items-center gap-space-md">
            {!wide && (
              <button
                ref={openButton}
                type="button"
                aria-label="Open navigation"
                aria-expanded={showDrawer}
                onClick={() => setDrawerOpen(true)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
              >
                <Menu size={20} aria-hidden="true" />
              </button>
            )}
            <LogoMark />
            <div className="flex flex-col">
              <span className="font-headline-md text-headline-md leading-tight">
                Groww Review Pulse
              </span>
              <span className="text-label-sm font-medium text-on-surface-variant">
                Weekly review intelligence
              </span>
            </div>
          </div>
          <div className="flex items-center gap-space-sm">
            {isMockMode() && (
              <span className="rounded-full border border-status-dryrun-border bg-status-dryrun-bg px-space-sm py-space-xs text-label-sm font-semibold text-status-dryrun-fg">
                Mock data
              </span>
            )}
            <button
              type="button"
              onClick={() => setRunControlOpen(true)}
              className="inline-flex items-center gap-space-xs rounded-lg bg-primary-container px-space-md py-space-sm text-label-lg text-on-primary-container hover:opacity-90"
            >
              <Play size={16} aria-hidden="true" />
              New Run (Dry Run)
            </button>
            <ThemeMenu />
          </div>
        </div>
      </header>

      {wide && (
        <aside className="fixed bottom-0 left-0 top-16 z-40 w-64 border-r border-outline-variant bg-surface-container-lowest p-space-md">
          <SideNav />
        </aside>
      )}

      {showDrawer && (
        <div className="fixed inset-0 z-[60]">
          <button
            type="button"
            aria-label="Close navigation"
            tabIndex={-1}
            className="absolute inset-0 bg-inverse-surface/50"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute bottom-0 left-0 top-0 w-64 bg-surface-container-lowest p-space-md">
            <div className="mb-space-md flex items-center justify-between">
              <span className="font-headline-md text-headline-md">Navigate</span>
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => {
                  setDrawerOpen(false);
                  openButton.current?.focus();
                }}
                className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-surface-container"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            <SideNav onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      <div className={wide ? "pl-64" : ""}>
        <main
          id="main"
          tabIndex={-1}
          className="min-h-screen px-space-lg pb-space-2xl pt-[calc(4rem+theme(spacing.space-xl))]"
        >
          {children}
        </main>
      </div>
      <RunControl open={runControlOpen} onClose={() => setRunControlOpen(false)} />
    </div>
    </RunControlProvider>
  );
}
