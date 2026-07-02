"use client";

// Sub-navigation for the /admin area (users · settings · activity).

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/admin/users", label: "Users" },
  { href: "/admin/settings", label: "Settings" },
  { href: "/admin/activity", label: "Activity" },
];

export default function AdminTabs() {
  const pathname = usePathname();
  return (
    <div
      className="flex gap-1 overflow-x-auto"
      style={{ borderBottom: "1px solid var(--border-dark-strong)" }}
    >
      {TABS.map((tab) => {
        const active = pathname === tab.href || pathname.startsWith(tab.href + "/");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className="font-mono text-xs px-4 py-2 whitespace-nowrap"
            style={{
              color: active ? "var(--accent-hover)" : "var(--text-on-dark-secondary)",
              borderBottom: active
                ? "2px solid var(--accent)"
                : "2px solid transparent",
              marginBottom: -1,
            }}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
