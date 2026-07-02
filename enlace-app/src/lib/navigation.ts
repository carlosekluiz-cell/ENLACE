// ── Declarative navigation with role gating ──
// Same pattern as frontend/src/lib/navigation.ts: items declare a minRole
// and an i18n labelKey; the sidebar filters by the session role.

import {
  Activity,
  ClipboardList,
  LayoutList,
  Radio,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/lib/roles";

export interface NavItem {
  labelKey: string;
  href: string;
  icon: LucideIcon;
  minRole: Role;
}

export const NAV_ITEMS: NavItem[] = [
  { labelKey: "nav.noc", href: "/noc", icon: Activity, minRole: "analyst" },
  { labelKey: "nav.onts", href: "/noc/onts", icon: Radio, minRole: "analyst" },
  { labelKey: "nav.field", href: "/field", icon: ClipboardList, minRole: "viewer" },
  { labelKey: "nav.supervisor", href: "/supervisor", icon: LayoutList, minRole: "manager" },
  { labelKey: "nav.exec", href: "/exec", icon: TrendingUp, minRole: "manager" },
];
