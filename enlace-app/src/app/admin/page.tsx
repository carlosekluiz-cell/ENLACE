// /admin — index redirect to the users tab. Role floor (admin) is enforced
// by middleware via src/lib/routeAccess.ts; the tab pages re-guard client-side.

import { redirect } from "next/navigation";

export default function AdminIndexPage() {
  redirect("/admin/users");
}
