import type { BlogSection } from '@/lib/blog-posts';

function TextSection({ content }: { content: string }) {
  const paragraphs = content.split('\n\n');
  return (
    <>
      {paragraphs.map((p, i) => (
        <p key={i} className="text-base leading-relaxed mb-6" style={{ color: 'var(--text-secondary)' }}>
          {p}
        </p>
      ))}
    </>
  );
}

function StatSection({ value, label, source }: { value: string; label: string; source?: string }) {
  return (
    <div className="py-10 text-center">
      <div className="font-mono text-4xl font-bold md:text-5xl" style={{ color: 'var(--accent)' }}>
        {value}
      </div>
      <div className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
        {label}
      </div>
      {source && (
        <div className="mt-1 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
          Fonte: {source}
        </div>
      )}
    </div>
  );
}

function TableSection({ headers, rows, caption }: { headers: string[]; rows: string[][]; caption?: string }) {
  return (
    <div className="my-8 overflow-x-auto">
      <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider"
                style={{
                  color: 'var(--text-muted)',
                  borderBottom: '2px solid var(--border)',
                  background: 'var(--bg-subtle)',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={`px-3 py-2 ${j > 0 ? 'font-mono text-xs tabular-nums' : 'text-sm'}`}
                  style={{
                    color: j === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {caption && (
        <p className="mt-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
          {caption}
        </p>
      )}
    </div>
  );
}

function CalloutSection({ title, content }: { title: string; content: string }) {
  return (
    <div
      className="my-8 p-5"
      style={{
        borderLeft: '3px solid var(--accent)',
        background: 'var(--bg-subtle)',
      }}
    >
      <div className="text-sm font-semibold mb-2" style={{ color: 'var(--accent)' }}>
        {title}
      </div>
      <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {content}
      </p>
    </div>
  );
}

function BarChartSection({ title, bars }: { title: string; bars: { label: string; value: number; display: string }[] }) {
  const max = Math.max(...bars.map((b) => b.value));
  return (
    <div className="my-8">
      <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      <div className="space-y-2.5">
        {bars.map((bar, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-24 flex-shrink-0 text-xs text-right truncate" style={{ color: 'var(--text-secondary)' }}>
              {bar.label}
            </div>
            <div className="flex-1 h-6 relative" style={{ background: 'var(--bg-subtle)' }}>
              <div
                className="h-full"
                style={{
                  width: `${(bar.value / max) * 100}%`,
                  background: 'var(--accent)',
                  minWidth: '2px',
                }}
              />
            </div>
            <div className="w-20 flex-shrink-0 font-mono text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
              {bar.display}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BlogSections({ sections }: { sections: BlogSection[] }) {
  return (
    <>
      {sections.map((section, i) => {
        switch (section.type) {
          case 'text':
            return <TextSection key={i} content={section.content} />;
          case 'stat':
            return <StatSection key={i} value={section.value} label={section.label} source={section.source} />;
          case 'table':
            return <TableSection key={i} headers={section.headers} rows={section.rows} caption={section.caption} />;
          case 'callout':
            return <CalloutSection key={i} title={section.title} content={section.content} />;
          case 'bar-chart':
            return <BarChartSection key={i} title={section.title} bars={section.bars} />;
        }
      })}
    </>
  );
}
