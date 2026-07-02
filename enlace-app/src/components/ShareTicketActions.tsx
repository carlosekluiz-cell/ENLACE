"use client";

// Share-to-WhatsApp + copy-link actions for a ticket (Wave C1).
//
// HONEST LABELING: this opens the wa.me share URL — the sender's own
// WhatsApp with a prefilled dispatch message. It is not the WhatsApp
// Business API; nothing is sent server-side. When the assignee has a phone
// on file the chat opens directly with them, otherwise WhatsApp asks the
// sender to pick the recipient.

import { useRef, useState } from "react";
import { Check, Copy, MessageCircle } from "lucide-react";
import type { TicketWithState } from "@/lib/opsTypes";
import { ticketDeepLink, ticketShareText, waShareUrl } from "@/lib/shareTicket";

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to the legacy path (insecure context / permission denied)
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export default function ShareTicketActions({
  t,
  auditRowId,
  phone,
}: {
  t: TicketWithState;
  auditRowId: string;
  /** Assignee phone when known — opens the wa.me chat directly with them. */
  phone?: string | null;
}) {
  const [copied, setCopied] = useState<"ok" | "fail" | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const deepLink = ticketDeepLink(t.ticket_ref, auditRowId);
  const waHref = waShareUrl(ticketShareText(t, deepLink), phone);

  function onCopy() {
    void copyText(deepLink).then((ok) => {
      setCopied(ok ? "ok" : "fail");
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(null), 2000);
    });
  }

  return (
    <span className="inline-flex items-center gap-1.5 flex-wrap">
      <a
        href={waHref}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 cursor-pointer"
        style={{ border: "1px solid #25D366", color: "#25D366" }}
        title={
          phone
            ? `Opens WhatsApp chat with ${phone} (share-to-WhatsApp, not the Business API)`
            : "Opens your WhatsApp with the dispatch message prefilled (share-to-WhatsApp, not the Business API)"
        }
      >
        <MessageCircle size={11} />
        WhatsApp
      </a>
      <button
        type="button"
        onClick={onCopy}
        className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 cursor-pointer"
        style={{
          border: "1px solid var(--border-dark-strong)",
          color:
            copied === "ok"
              ? "var(--status-online)"
              : "var(--text-on-dark-muted)",
        }}
        title={deepLink}
      >
        {copied === "ok" ? <Check size={11} /> : <Copy size={11} />}
        {copied === "ok" ? "copied" : copied === "fail" ? "copy failed" : "copy link"}
      </button>
    </span>
  );
}
