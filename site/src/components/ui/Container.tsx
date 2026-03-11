export default function Container({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`mx-auto max-w-6xl px-4 ${className || ''}`}>
      {children}
    </div>
  );
}
