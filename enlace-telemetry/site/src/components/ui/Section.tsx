interface SectionProps {
  children: React.ReactNode;
  className?: string;
  id?: string;
  background?:
    | "primary"
    | "surface"
    | "subtle"
    | "dark"
    | "dark-surface"
    | "dark-subtle";
  grain?: boolean;
  hero?: boolean;
}

const bgMap: Record<string, string> = {
  primary: "var(--bg-primary)",
  surface: "var(--bg-surface)",
  subtle: "var(--bg-subtle)",
  dark: "var(--bg-dark)",
  "dark-surface": "var(--bg-dark-surface)",
  "dark-subtle": "var(--bg-dark-subtle)",
};

const textMap: Record<string, string> = {
  primary: "var(--text-primary)",
  surface: "var(--text-primary)",
  subtle: "var(--text-primary)",
  dark: "var(--text-on-dark)",
  "dark-surface": "var(--text-on-dark)",
  "dark-subtle": "var(--text-on-dark)",
};

export default function Section({
  children,
  className = "",
  id,
  background = "primary",
  grain = false,
  hero = false,
}: SectionProps) {
  const sectionPadding = hero
    ? "-mt-14 pt-28 pb-20 md:pt-36 md:pb-28"
    : "py-20 md:py-28";

  return (
    <section
      id={id}
      className={`relative ${grain ? "grain" : ""} ${sectionPadding} ${className}`}
      style={{
        backgroundColor: bgMap[background],
        color: textMap[background],
      }}
    >
      <div className="relative z-10 mx-auto max-w-6xl px-4">{children}</div>
    </section>
  );
}
