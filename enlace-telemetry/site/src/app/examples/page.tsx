import type { Metadata } from "next";
import ExamplesContent from "./ExamplesContent";

export const metadata: Metadata = {
  title: "Example report — Enlace Telemetry",
  description:
    "See what an Enlace audit produces: fleet health score, fault classification with dying-gasp evidence, churn risk with stated assumptions, proactive tickets, and per-ONT diagnostics. Example output from internal validation on representative data — not customer data.",
};

export default function ExamplesPage() {
  return <ExamplesContent />;
}
