"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Section from "@/components/ui/Section";
import {
  Upload,
  FileText,
  Activity,
  TrendingDown,
  AlertTriangle,
  UserX,
  Layers,
  CloudRain,
  Cpu,
  Ruler,
  Battery,
  Clock,
  LineChart,
  Search,
  FileBarChart,
  Shield,
  Check,
} from "lucide-react";

const modules = [
  {
    icon: Activity,
    title: "Signal Health Score",
    description: "Overall ONT fleet health (0-100)",
  },
  {
    icon: TrendingDown,
    title: "Degradation Alert",
    description: "ONTs with declining Rx power",
  },
  {
    icon: AlertTriangle,
    title: "Fault Tickets",
    description: "Suspected fibre cuts and failures",
  },
  {
    icon: UserX,
    title: "Ghost Customers",
    description: "ONTs offline for 7+ days (paying but not connected)",
  },
  {
    icon: Layers,
    title: "Splitter Capacity",
    description: "PON ports approaching saturation",
  },
  {
    icon: CloudRain,
    title: "Weather Correlation",
    description: "Signal degradation vs weather events",
  },
  {
    icon: Cpu,
    title: "Vendor Distribution",
    description: "ONT mix by manufacturer",
  },
  {
    icon: Ruler,
    title: "Distance Analysis",
    description: "Signal vs distance per ONT",
  },
  {
    icon: Battery,
    title: "Power Budget",
    description: "ONTs near optical budget limits",
  },
  {
    icon: Clock,
    title: "Uptime Report",
    description: "Session stability per subscriber",
  },
  {
    icon: LineChart,
    title: "Trend Analysis",
    description: "Signal trends over time",
  },
  {
    icon: Search,
    title: "Anomaly Detection",
    description: "Unusual patterns in the data",
  },
  {
    icon: FileBarChart,
    title: "Executive Summary",
    description: "PDF-ready overview for management",
  },
];

const AUDIT_SERVER = "http://localhost:8080";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalysing, setIsAnalysing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleFile = useCallback((f: File) => {
    const name = f.name.toLowerCase();
    if (name.endsWith(".csv") || name.endsWith(".tsv") || name.endsWith(".txt")) {
      setFile(f);
    }
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const handleAnalyse = useCallback(async () => {
    if (!file) return;

    setIsAnalysing(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${AUDIT_SERVER}/audit`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Server error: ${response.status}`);
      }

      const data = await response.json();

      if (!data.audit_id) {
        throw new Error("No audit_id in response");
      }

      // Store the audit result in sessionStorage
      sessionStorage.setItem(`audit:${data.audit_id}`, JSON.stringify(data));

      // Redirect to platform audit page
      router.push(`/platform/audit/${data.audit_id}`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to upload file";
      setError(errorMessage);
      setIsAnalysing(false);
    }
  }, [file, router]);

  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <p
            className="font-mono text-xs tracking-widest uppercase mb-4"
            style={{ color: "var(--accent)" }}
          >
            Try ENLACE
          </p>
          <h1
            className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-6"
            style={{ color: "var(--text-on-dark)" }}
          >
            Drop your OLT export.{" "}
            <span style={{ color: "var(--text-on-dark-muted)" }}>
              Get a full health report.
            </span>
          </h1>
          <p
            className="text-lg md:text-xl leading-relaxed max-w-2xl"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            No install. No signup. No cost. Upload your OLT export and see what
            ENLACE finds in 30 seconds.
          </p>
        </div>
      </Section>

      {/* Upload zone */}
      <Section background="primary">
        <div className="max-w-2xl mx-auto">
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className="flex flex-col items-center justify-center py-16 px-8 cursor-pointer transition-colors duration-200"
            style={{
              border: `2px dashed ${isDragging ? "var(--accent)" : "var(--border-strong)"}`,
              backgroundColor: isDragging
                ? "var(--accent-subtle)"
                : "var(--bg-surface)",
            }}
          >
            <Upload
              size={40}
              style={{
                color: isDragging ? "var(--accent)" : "var(--text-muted)",
              }}
            />
            <p
              className="font-serif text-xl font-semibold mt-4 mb-1"
              style={{ color: "var(--text-primary)" }}
            >
              Drag &amp; drop your CSV here
            </p>
            <p
              className="text-sm mb-6"
              style={{ color: "var(--text-secondary)" }}
            >
              or click to browse
            </p>
            <p
              className="font-mono text-xs text-center leading-relaxed max-w-md"
              style={{ color: "var(--text-muted)" }}
            >
              Supports Huawei, ZTE, FiberHome, Adtran, Datacom, Parks OLT
              exports. CSV or TSV.
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.tsv,.txt"
              onChange={onChange}
              className="hidden"
            />
          </div>

          {/* Selected file */}
          {file && (
            <div
              className="flex items-center gap-3 mt-4 p-4"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <FileText size={20} style={{ color: "var(--accent)" }} />
              <div className="flex-1 min-w-0">
                <p
                  className="font-mono text-sm truncate"
                  style={{ color: "var(--text-primary)" }}
                >
                  {file.name}
                </p>
                <p
                  className="font-mono text-xs"
                  style={{ color: "var(--text-muted)" }}
                >
                  {formatFileSize(file.size)}
                </p>
              </div>
              <button
                className="enlace-btn-primary"
                disabled={isAnalysing}
                onClick={handleAnalyse}
              >
                {isAnalysing ? "Analysing..." : "Analyse"}
              </button>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div
              className="mt-4 p-4"
              style={{
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgb(239, 68, 68)",
                borderRadius: "4px",
              }}
            >
              <p
                className="font-mono text-sm"
                style={{ color: "rgb(220, 38, 38)" }}
              >
                Error: {error}
              </p>
            </div>
          )}
        </div>
      </Section>

      {/* What you get */}
      <Section background="subtle">
        <p
          className="font-mono text-xs tracking-widest uppercase mb-4"
          style={{ color: "var(--accent)" }}
        >
          13 Analysis Modules
        </p>
        <h2
          className="font-serif text-3xl md:text-4xl font-bold mb-12"
          style={{ color: "var(--text-primary)" }}
        >
          What you get from a single CSV.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {modules.map((mod) => (
            <div
              key={mod.title}
              className="p-5"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <mod.icon
                size={20}
                className="mb-3"
                style={{ color: "var(--accent)" }}
              />
              <h3
                className="font-serif text-base font-semibold mb-1"
                style={{ color: "var(--text-primary)" }}
              >
                {mod.title}
              </h3>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)" }}
              >
                {mod.description}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Privacy */}
      <Section background="surface">
        <div className="max-w-2xl mx-auto text-center">
          <Shield
            size={32}
            className="mx-auto mb-4"
            style={{ color: "var(--accent)" }}
          />
          <h2
            className="font-serif text-2xl md:text-3xl font-bold mb-4"
            style={{ color: "var(--text-primary)" }}
          >
            Your data stays yours.
          </h2>
          <div className="flex flex-col gap-3">
            {[
              "CSV is processed in your browser. Nothing is uploaded to our servers.",
              "No account required. No email required. Completely free.",
              "No tracking. Your data stays private.",
            ].map((line) => (
              <p
                key={line}
                className="flex items-start gap-2 text-left mx-auto max-w-md"
              >
                <Check
                  size={16}
                  className="mt-0.5 shrink-0"
                  style={{ color: "var(--success)" }}
                />
                <span
                  className="text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {line}
                </span>
              </p>
            ))}
          </div>
        </div>
      </Section>
    </>
  );
}
