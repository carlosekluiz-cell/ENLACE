import type { Metadata } from "next";
import { DM_Sans, Fraunces, JetBrains_Mono } from "next/font/google";
import Nav from "@/components/layout/Nav";
import Footer from "@/components/layout/Footer";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const fraunces = Fraunces({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Enlace Telemetry — Your network is talking. Now you can listen.",
  description:
    "Read-only PON telemetry agent. Collect OLT/ONU metrics via SNMP, NETCONF, and TR-069 from any vendor — Huawei, ZTE, Nokia, FiberHome, Adtran, and more. Real-time fault detection, predictive analytics, and Elasticsearch integration.",
  icons: { icon: "/logo.svg" },
  keywords: [
    "PON telemetry",
    "OLT monitoring",
    "ONU metrics",
    "SNMP",
    "TR-069",
    "NETCONF",
    "fiber optics",
    "network monitoring",
    "Enlace",
  ],
  openGraph: {
    title: "Enlace Telemetry — Your network is talking. Now you can listen.",
    description:
      "Read-only PON telemetry agent for multi-vendor fiber networks.",
    type: "website",
    siteName: "Enlace Telemetry",
  },
  twitter: {
    card: "summary_large_image",
    title: "Enlace Telemetry",
    description:
      "Read-only PON telemetry agent for multi-vendor fiber networks.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLdOrg = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Pulso Technologies Limited",
    url: "https://enlace.network",
    logo: "https://enlace.network/logo.svg",
    sameAs: [
      "https://find-and-update.company-information.service.gov.uk/company/17151141",
    ],
  };

  const jsonLdApp = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Enlace Telemetry",
    applicationCategory: "NetworkApplication",
    operatingSystem: "Linux",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    description:
      "Read-only PON telemetry agent for multi-vendor fiber networks.",
    author: {
      "@type": "Organization",
      name: "Pulso Technologies Limited",
    },
  };

  return (
    <html
      lang="en"
      className={`${dmSans.variable} ${fraunces.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdOrg) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdApp) }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <I18nProvider>
          <Nav />
          <main className="flex-1">{children}</main>
          <Footer />
        </I18nProvider>
      </body>
    </html>
  );
}
