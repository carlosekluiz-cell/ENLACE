// /api/admin/settings — tenant assumption constants (admin only).
//
//   GET → current constants with their meaning.
//   PUT → update { arpu_gbp_month?, truck_roll_cost_gbp?, currency? }.
//
// These constants parameterize `estimated_*` figures (revenue-at-risk,
// fix cost). Changing them is an admin act → audit_log. The seam, stated
// honestly: the agent computes estimates at audit time with the assumptions
// it declares in the result; settings changes feed FUTURE estimate math and
// are surfaced (labeled) in the exec projection — persisted audits are never
// retro-recomputed.

import { NextRequest, NextResponse } from "next/server";
import type { TenantSettingsResponse } from "@/lib/adminTypes";
import {
  getTenantInfo,
  updateTenantAssumptions,
  type AssumptionPatch,
} from "@/lib/tenantSettings";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";

const APPLIES_TO =
  "Used for revenue-at-risk and fix-cost ESTIMATES. Applies to future estimate math; persisted audits keep the assumptions the agent declared when they ran.";

function respond(tenantId: string): NextResponse {
  const info = getTenantInfo(tenantId);
  if (!info) {
    return NextResponse.json({ error: "tenant not found" }, { status: 404 });
  }
  const res: TenantSettingsResponse = {
    tenant: { id: info.id, name: info.name },
    assumptions: info.assumptions,
    applies_to: APPLIES_TO,
  };
  return NextResponse.json(res);
}

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "admin");
    return respond(session.tenant_id);
  } catch (err) {
    return authzResponse(err);
  }
}

export async function PUT(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "admin");

    const body = (await req.json().catch(() => ({}))) as {
      arpu_gbp_month?: unknown;
      truck_roll_cost_gbp?: unknown;
      currency?: unknown;
    };

    const patch: AssumptionPatch = {};
    if (body.arpu_gbp_month !== undefined) {
      const v = Number(body.arpu_gbp_month);
      if (!Number.isFinite(v) || v < 0) {
        return NextResponse.json(
          { error: "arpu_gbp_month must be a non-negative number" },
          { status: 400 },
        );
      }
      patch.arpu_gbp_month = v;
    }
    if (body.truck_roll_cost_gbp !== undefined) {
      const v = Number(body.truck_roll_cost_gbp);
      if (!Number.isFinite(v) || v < 0) {
        return NextResponse.json(
          { error: "truck_roll_cost_gbp must be a non-negative number" },
          { status: 400 },
        );
      }
      patch.truck_roll_cost_gbp = v;
    }
    if (body.currency !== undefined) {
      if (typeof body.currency !== "string" || !/^[A-Za-z]{3}$/.test(body.currency.trim())) {
        return NextResponse.json(
          { error: "currency must be a 3-letter ISO 4217 code (e.g. GBP)" },
          { status: 400 },
        );
      }
      patch.currency = body.currency.trim().toUpperCase();
    }
    if (Object.keys(patch).length === 0) {
      return NextResponse.json(
        { error: "nothing to update — send arpu_gbp_month, truck_roll_cost_gbp and/or currency" },
        { status: 400 },
      );
    }

    const updated = updateTenantAssumptions(session.tenant_id, patch);
    if (!updated) {
      return NextResponse.json({ error: "tenant not found" }, { status: 404 });
    }

    logAction(
      session,
      "admin.settings.update",
      Object.entries(patch)
        .map(([k, v]) => `${k}=${v}`)
        .join(" "),
    );
    return respond(session.tenant_id);
  } catch (err) {
    return authzResponse(err);
  }
}
