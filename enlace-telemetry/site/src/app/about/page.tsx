import type { Metadata } from "next";
import AboutContent from "./AboutContent";

export const metadata: Metadata = {
  title: "About — Enlace Telemetry",
  description:
    "Pulso Technologies builds telemetry intelligence for fibre operators. Enlace is our telemetry agent for per-ONT visibility.",
};

export default function AboutPage() {
  return <AboutContent />;
}
