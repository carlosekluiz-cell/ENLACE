interface ScreenshotProps {
  src: string;
  alt: string;
  className?: string;
}

export default function Screenshot({ src, alt, className }: ScreenshotProps) {
  return (
    <div
      className={`overflow-hidden rounded-lg ${className || ''}`}
      style={{ border: '1px solid var(--border)' }}
    >
      <img
        src={src}
        alt={alt}
        loading="lazy"
        className="w-full h-auto"
        style={{ background: 'var(--bg-subtle)' }}
      />
    </div>
  );
}
