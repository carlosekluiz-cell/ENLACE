"use client";

// App chrome: role-filtered sidebar (desktop) / top bar (mobile), session
// info, locale toggle, the audit picker (current-audit selection from the
// tenant's persisted list) and the always-visible data-source badge.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import type { ReactNode } from "react";
import { NAV_ITEMS } from "@/lib/navigation";
import { roleAtLeast } from "@/lib/roles";
import { useAuth } from "@/lib/auth";
import { useI18n, type Locale } from "@/lib/i18n";
import type { FeedMeta } from "@/lib/useOps";
import AuditPicker from "@/components/AuditPicker";
import SourceBadge from "@/components/SourceBadge";

export default function AppShell({
  title,
  meta,
  actions,
  children,
}: {
  title: string;
  meta: FeedMeta | null;
  /** Optional view-specific header actions (e.g. the exec PDF download). */
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { session, logout } = useAuth();
  const { t, locale, setLocale } = useI18n();
  const pathname = usePathname();
  const router = useRouter();

  const items = session
    ? NAV_ITEMS.filter((item) => roleAtLeast(session.role, item.minRole))
    : [];

  const nav = (
    <nav className="flex md:flex-col gap-1 overflow-x-auto">
      {items.map((item) => {
        const active =
          pathname === item.href ||
          (item.href !== "/noc" && pathname.startsWith(item.href + "/")) ||
          (item.href === "/noc" && pathname === "/noc");
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center gap-2 px-3 py-2 font-mono text-xs whitespace-nowrap"
            style={{
              color: active ? "var(--accent-hover)" : "var(--text-on-dark-secondary)",
              backgroundColor: active ? "var(--bg-dark-subtle)" : "transparent",
              borderLeft: active
                ? "2px solid var(--accent)"
                : "2px solid transparent",
            }}
          >
            <Icon size={14} />
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Sidebar (desktop) / top strip (mobile) */}
      <aside
        className="md:w-56 md:min-h-screen flex md:flex-col justify-between px-3 py-3 md:py-5 gap-3"
        style={{
          backgroundColor: "var(--bg-dark-surface)",
          borderRight: "1px solid var(--border-dark-strong)",
          borderBottom: "1px solid var(--border-dark-strong)",
        }}
      >
        <div className="flex md:flex-col gap-4 md:gap-6 items-center md:items-stretch min-w-0">
          <Link href="/" className="px-3 shrink-0">
            <span
              className="font-serif text-lg font-semibold"
              style={{ color: "var(--text-on-dark)" }}
            >
              enlace
            </span>
            <span className="font-mono text-[10px] ml-2" style={{ color: "var(--accent)" }}>
              OPS
            </span>
          </Link>
          {nav}
        </div>

        <div className="flex md:flex-col items-center md:items-stretch gap-2 px-1">
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            className="bg-transparent font-mono text-[11px] px-2 py-1 cursor-pointer"
            style={{
              color: "var(--text-on-dark-muted)",
              border: "1px solid var(--border-dark)",
            }}
            aria-label="Language"
          >
            <option value="en">EN</option>
            <option value="pt-BR">PT-BR</option>
          </select>
          {session && (
            <div className="flex items-center justify-between gap-2 px-2">
              <div className="hidden md:block min-w-0">
                <p
                  className="text-xs truncate"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  {session.name}
                </p>
                <p className="font-mono text-[10px]" style={{ color: "var(--text-on-dark-muted)" }}>
                  {session.role}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  // Revoke server-side first so middleware sees a dead
                  // cookie before we land on the login page.
                  void logout().then(() => router.replace("/"));
                }}
                title={t("nav.logout")}
                className="cursor-pointer p-1"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0">
        <header
          className="flex items-center justify-between gap-4 px-4 md:px-6 py-3"
          style={{ borderBottom: "1px solid var(--border-dark-strong)" }}
        >
          <h1
            className="font-serif text-lg md:text-xl"
            style={{ color: "var(--text-on-dark)" }}
          >
            {title}
          </h1>
          <div className="flex items-center gap-3">
            {actions}
            <AuditPicker />
            {meta && <SourceBadge meta={meta} />}
          </div>
        </header>
        <main className="p-4 md:p-6 flex flex-col gap-4">{children}</main>
      </div>
    </div>
  );
}
