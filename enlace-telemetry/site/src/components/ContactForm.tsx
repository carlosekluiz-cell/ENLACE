"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";

const fields = [
  { id: "name", label: "Name", type: "text", placeholder: "Jane Doe" },
  {
    id: "operator",
    label: "ISP / operator",
    type: "text",
    placeholder: "Acme Fibre",
  },
  {
    id: "email",
    label: "Work email",
    type: "email",
    placeholder: "jane@acmefibre.com",
  },
  {
    id: "vendor",
    label: "OLT vendor",
    type: "text",
    placeholder: "Huawei, ZTE, Nokia…",
  },
] as const;

type Status = "idle" | "submitting" | "success" | "error";

export default function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    setError("");

    const formData = new FormData(e.currentTarget);
    const payload = {
      name: String(formData.get("name") ?? ""),
      operator: String(formData.get("operator") ?? ""),
      email: String(formData.get("email") ?? ""),
      vendor: String(formData.get("vendor") ?? ""),
      message: String(formData.get("message") ?? ""),
    };

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.error || "Something went wrong. Please try again.");
        setStatus("error");
        return;
      }
      setStatus("success");
    } catch {
      setError("Couldn't reach the server. Please try again.");
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div
        className="flex flex-col gap-3 p-6"
        style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderLeft: "3px solid var(--accent)",
        }}
      >
        <p
          className="font-serif text-xl font-bold"
          style={{ color: "var(--text-primary)" }}
        >
          Thanks — we&apos;ll be in touch.
        </p>
        <p
          className="text-sm leading-relaxed"
          style={{ color: "var(--text-secondary)" }}
        >
          We&apos;ll be in touch at hello@enlace.network.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {fields.map((field) => (
        <div key={field.id} className="flex flex-col gap-2">
          <label
            htmlFor={field.id}
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "var(--text-muted)" }}
          >
            {field.label}
          </label>
          <input
            id={field.id}
            name={field.id}
            type={field.type}
            placeholder={field.placeholder}
            className="text-sm px-4 py-3 outline-none"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
        </div>
      ))}

      <div className="flex flex-col gap-2">
        <label
          htmlFor="message"
          className="font-mono text-xs uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}
        >
          Message
        </label>
        <textarea
          id="message"
          name="message"
          rows={4}
          placeholder="What would you like Enlace to see on your network?"
          className="text-sm px-4 py-3 outline-none resize-y"
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
          }}
        />
      </div>

      {status === "error" && (
        <p className="text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="enlace-btn-primary mt-2 gap-2"
        style={status === "submitting" ? { opacity: 0.7 } : undefined}
      >
        {status === "submitting" ? "Sending…" : "Request a pilot"}
        {status !== "submitting" && <ArrowRight size={16} />}
      </button>
    </form>
  );
}
