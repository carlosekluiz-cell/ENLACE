"use client";

// / — login (persona picker) + role-aware redirect. A live session skips
// straight to its persona home. Demo auth only; see TODO in lib/auth.tsx.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PERSONAS } from "@/lib/roles";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { session, ready, login } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");

  useEffect(() => {
    if (ready && session) {
      const persona = PERSONAS.find((p) => p.id === session.persona);
      router.replace(persona?.home ?? "/noc");
    }
  }, [ready, session, router]);

  if (!ready || session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          …
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        <div className="text-center">
          <p className="font-serif text-4xl" style={{ color: "var(--text-on-dark)" }}>
            enlace{" "}
            <span className="font-mono text-sm align-middle" style={{ color: "var(--accent)" }}>
              OPERATIONS
            </span>
          </p>
          <p className="mt-2 text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
            Your network is talking. Choose who&apos;s listening.
          </p>
        </div>

        <div>
          <label className="op-label block mb-2" htmlFor="name">
            your name (optional)
          </label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Sam Achebe"
            className="enlace-input-dark"
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          {PERSONAS.map((persona) => (
            <button
              key={persona.id}
              type="button"
              onClick={() => {
                const p = login(persona.id, name);
                if (p) router.push(p.home);
              }}
              className="op-card text-left p-4 cursor-pointer transition-colors hover:border-[var(--accent)]"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-sm" style={{ color: "var(--text-on-dark)" }}>
                  {persona.label}
                </span>
                <span className="font-mono text-[10px] uppercase" style={{ color: "var(--accent)" }}>
                  {persona.role}
                </span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-on-dark-muted)" }}>
                {persona.description}
              </p>
            </button>
          ))}
        </div>

        <p
          className="text-center font-mono text-[11px]"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          demo session — persona selection stands in for real auth (JWT wiring
          pending, see docs/ONTOLOGY.md §3)
        </p>
      </div>
    </div>
  );
}
