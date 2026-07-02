import { appendFile } from "fs/promises";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(req: Request) {
  let body: {
    name?: string;
    operator?: string;
    email?: string;
    vendor?: string;
    message?: string;
  };

  try {
    body = await req.json();
  } catch {
    return Response.json(
      { ok: false, error: "Invalid request body." },
      { status: 400 },
    );
  }

  const name = (body.name ?? "").trim();
  const operator = (body.operator ?? "").trim();
  const email = (body.email ?? "").trim();
  const vendor = (body.vendor ?? "").trim();
  const message = (body.message ?? "").trim();

  if (!name) {
    return Response.json(
      { ok: false, error: "Please enter your name." },
      { status: 400 },
    );
  }
  if (!email || !EMAIL_RE.test(email)) {
    return Response.json(
      { ok: false, error: "Please enter a valid email address." },
      { status: 400 },
    );
  }
  if (!message) {
    return Response.json(
      { ok: false, error: "Please enter a message." },
      { status: 400 },
    );
  }

  const userAgent = req.headers.get("user-agent") ?? "";
  const sourceIp =
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "";

  // Primary store: Postgres. Fall back to a local file so a lead is never lost.
  let stored = false;
  const pool = getPool();
  if (pool) {
    try {
      await pool.query(
        `INSERT INTO contact_submissions
           (name, operator, email, vendor, message, user_agent, source_ip)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [name, operator, email, vendor, message, userAgent, sourceIp],
      );
      stored = true;
    } catch (err) {
      console.error("contact: DB insert failed, falling back to file:", err);
    }
  }

  if (!stored) {
    try {
      await appendFile(
        `${process.cwd()}/contact-submissions.jsonl`,
        JSON.stringify({
          timestamp: new Date().toISOString(),
          name,
          operator,
          email,
          vendor,
          message,
          userAgent,
          sourceIp,
        }) + "\n",
      );
    } catch (err) {
      console.error("contact: file fallback failed:", err);
      return Response.json(
        { ok: false, error: "Could not save your message. Please email us directly." },
        { status: 500 },
      );
    }
  }

  if (process.env.WEB3FORMS_ACCESS_KEY) {
    try {
      await fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_key: process.env.WEB3FORMS_ACCESS_KEY,
          subject: "Enlace pilot enquiry",
          from_name: name,
          email,
          operator,
          vendor,
          message,
        }),
      });
    } catch {
      // Never fail the request on email delivery error.
    }
  }

  return Response.json({ ok: true });
}
