import type { Metadata } from "next";
import FeaturesContent from "./FeaturesContent";

export const metadata: Metadata = {
  title: "Features — Enlace Telemetry",
  description:
    "Fault detection, signal prediction, capacity planning, multi-vendor support, and real-time diagnostics. Everything Enlace does for your fibre network.",
};

export default function FeaturesPage() {
  return <FeaturesContent />;
}
