'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Star,
  Target,
  Briefcase,
  Handshake,
  Globe,
  TrendingUp,
  Database,
  Shield,
  Brain,
  Cpu,
  MessageSquare,
  Wrench,
  Map,
  Zap,
  BookOpen,
  ChevronRight,
  Search,
  ArrowUp,
  Loader2,
  BookMarked,
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResearchDoc {
  id: string;
  file: string;
  title: string;
  description: string;
  icon: string;
  tier: string;
  available: boolean;
  size_bytes: number;
}

// ---------------------------------------------------------------------------
// Icon mapping
// ---------------------------------------------------------------------------

const iconMap: Record<string, React.ReactNode> = {
  star: <Star size={16} />,
  target: <Target size={16} />,
  briefcase: <Briefcase size={16} />,
  handshake: <Handshake size={16} />,
  globe: <Globe size={16} />,
  'trending-up': <TrendingUp size={16} />,
  database: <Database size={16} />,
  shield: <Shield size={16} />,
  brain: <Brain size={16} />,
  cpu: <Cpu size={16} />,
  'message-square': <MessageSquare size={16} />,
  wrench: <Wrench size={16} />,
  map: <Map size={16} />,
  zap: <Zap size={16} />,
  'book-open': <BookOpen size={16} />,
};

const tierLabels: Record<string, string> = {
  overview: 'Overview',
  strategy: 'Estratégia',
  product: 'Produto',
  technology: 'Tecnologia',
};

const tierColors: Record<string, string> = {
  overview: '#f59e0b',
  strategy: '#8b5cf6',
  product: '#10b981',
  technology: '#3b82f6',
};

// ---------------------------------------------------------------------------
// Simple Markdown Renderer
// Content comes from our own docs/ directory (trusted internal files).
// We escape HTML entities as an extra safety measure.
// ---------------------------------------------------------------------------

function renderMarkdown(md: string): string {
  let html = md;

  // Escape HTML entities (content is trusted but we sanitize anyway)
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
    return `<pre class="rd-code-block"><code>${code.trim()}</code></pre>`;
  });

  // Tables
  html = html.replace(
    /^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/gm,
    (_match, header: string, _sep: string, body: string) => {
      const headers = header
        .split('|')
        .filter((c: string) => c.trim())
        .map((c: string) => `<th>${c.trim()}</th>`)
        .join('');
      const rows = body
        .trim()
        .split('\n')
        .map((row: string) => {
          const cells = row
            .split('|')
            .filter((c: string) => c.trim())
            .map((c: string) => `<td>${c.trim()}</td>`)
            .join('');
          return `<tr>${cells}</tr>`;
        })
        .join('');
      return `<div class="rd-table-wrap"><table class="rd-table"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div>`;
    }
  );

  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4 class="rd-h4">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="rd-h3">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="rd-h2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="rd-h1">$1</h1>');

  // Horizontal rules
  html = html.replace(/^---+$/gm, '<hr class="rd-hr" />');

  // Bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="rd-inline-code">$1</code>');

  // Links
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="rd-link">$1</a>'
  );

  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li class="rd-li">$1</li>');
  html = html.replace(/((?:<li class="rd-li">.*<\/li>\n?)+)/g, '<ul class="rd-ul">$1</ul>');

  // Numbered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="rd-oli">$1</li>');
  html = html.replace(/((?:<li class="rd-oli">.*<\/li>\n?)+)/g, '<ol class="rd-ol">$1</ol>');

  // Paragraphs
  html = html
    .split('\n\n')
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return '';
      if (trimmed.startsWith('<')) return trimmed;
      return `<p class="rd-p">${trimmed}</p>`;
    })
    .join('\n');

  return html;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ResearchPage() {
  const [docs, setDocs] = useState<ResearchDoc[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [search, setSearch] = useState('');
  const [showToc, setShowToc] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchApi<{ documents: ResearchDoc[] }>('/api/v1/research/')
      .then((data) => {
        setDocs(data.documents || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const selectDoc = useCallback(
    async (id: string) => {
      if (id === selectedId) return;
      setSelectedId(id);
      setLoadingDoc(true);
      setContent('');
      try {
        const data = await fetchApi<{ content: string }>(`/api/v1/research/${id}`);
        setContent(data.content || '');
      } catch {
        setContent('# Error\n\nCould not load document.');
      }
      setLoadingDoc(false);
      contentRef.current?.scrollTo(0, 0);
    },
    [selectedId]
  );

  useEffect(() => {
    if (docs.length > 0 && !selectedId) {
      selectDoc(docs[0].id);
    }
  }, [docs, selectedId, selectDoc]);

  const filteredDocs = docs.filter(
    (d) =>
      d.title.toLowerCase().includes(search.toLowerCase()) ||
      d.description.toLowerCase().includes(search.toLowerCase())
  );

  const groupedDocs = ['overview', 'strategy', 'product', 'technology'].map((tier) => ({
    tier,
    label: tierLabels[tier],
    color: tierColors[tier],
    docs: filteredDocs.filter((d) => d.tier === tier),
  }));

  const selectedDoc = docs.find((d) => d.id === selectedId);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Rendered HTML from markdown (trusted internal content)
  const renderedHtml = content ? renderMarkdown(content) : '';

  return (
    <div className="flex h-full" style={{ background: 'var(--bg-primary)' }}>
      {/* Sidebar: Document List */}
      <aside
        className="flex flex-col border-r"
        style={{
          width: showToc ? '320px' : '0px',
          minWidth: showToc ? '320px' : '0px',
          borderColor: 'var(--border)',
          background: 'var(--bg-subtle)',
          transition: 'width 0.2s, min-width 0.2s',
          overflow: 'hidden',
        }}
      >
        <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
          <BookMarked size={18} style={{ color: 'var(--accent)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Research Library
          </h2>
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}
          >
            {docs.length} docs
          </span>
        </div>

        <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
          <div
            className="flex items-center gap-2 rounded-md px-2 py-1.5"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}
          >
            <Search size={14} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 bg-transparent text-sm outline-none"
              style={{ color: 'var(--text-primary)' }}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
            </div>
          ) : (
            groupedDocs.map(
              (group) =>
                group.docs.length > 0 && (
                  <div key={group.tier}>
                    <div className="flex items-center gap-2 px-2 py-1">
                      <div className="h-1.5 w-1.5 rounded-full" style={{ background: group.color }} />
                      <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                        {group.label}
                      </span>
                    </div>
                    {group.docs.map((doc) => (
                      <button
                        key={doc.id}
                        onClick={() => selectDoc(doc.id)}
                        className="w-full rounded-md px-3 py-2 text-left transition-colors"
                        style={{
                          background: selectedId === doc.id ? 'var(--accent-subtle)' : 'transparent',
                          borderLeft: selectedId === doc.id ? '2px solid var(--accent)' : '2px solid transparent',
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5" style={{ color: selectedId === doc.id ? 'var(--accent)' : 'var(--text-muted)' }}>
                            {iconMap[doc.icon] || <Star size={16} />}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium truncate" style={{ color: selectedId === doc.id ? 'var(--accent)' : 'var(--text-primary)' }}>
                              {doc.title}
                            </p>
                            <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                              {doc.description}
                            </p>
                            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)', opacity: 0.6 }}>
                              {formatSize(doc.size_bytes)}
                            </p>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )
            )
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col min-w-0">
        <div
          className="flex items-center gap-3 px-6 py-3"
          style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}
        >
          <button
            onClick={() => setShowToc(!showToc)}
            className="rounded p-1.5 transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title={showToc ? 'Hide sidebar' : 'Show sidebar'}
          >
            <ChevronRight
              size={16}
              style={{ transform: showToc ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
            />
          </button>
          {selectedDoc && (
            <>
              <span style={{ color: tierColors[selectedDoc.tier] }}>{iconMap[selectedDoc.icon]}</span>
              <div className="min-w-0">
                <h1 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {selectedDoc.title}
                </h1>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {selectedDoc.description}
                </p>
              </div>
              <span
                className="ml-auto rounded-full px-2 py-0.5 text-xs"
                style={{ background: tierColors[selectedDoc.tier] + '22', color: tierColors[selectedDoc.tier] }}
              >
                {tierLabels[selectedDoc.tier]}
              </span>
            </>
          )}
        </div>

        <div ref={contentRef} className="flex-1 overflow-y-auto">
          {loadingDoc ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
              <span className="ml-3 text-sm" style={{ color: 'var(--text-muted)' }}>Loading document...</span>
            </div>
          ) : renderedHtml ? (
            <div className="mx-auto max-w-4xl px-8 py-8">
              <ResearchContent html={renderedHtml} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20" style={{ color: 'var(--text-muted)' }}>
              <BookMarked size={48} className="mb-4 opacity-30" />
              <p className="text-sm">Select a document to start reading</p>
            </div>
          )}
        </div>

        <button
          onClick={() => contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
          className="fixed bottom-6 right-6 rounded-full p-2 shadow-lg"
          style={{ background: 'var(--accent)', color: 'white' }}
          aria-label="Scroll to top"
        >
          <ArrowUp size={16} />
        </button>
      </div>

      <style jsx global>{`
        .research-doc {
          font-size: 14px;
          line-height: 1.7;
          color: var(--text-primary);
        }
        .rd-h1 {
          font-size: 1.75rem;
          font-weight: 700;
          margin: 0 0 1rem 0;
          padding-bottom: 0.5rem;
          border-bottom: 2px solid var(--border);
          color: var(--text-primary);
        }
        .rd-h2 {
          font-size: 1.35rem;
          font-weight: 600;
          margin: 2rem 0 0.75rem 0;
          padding-bottom: 0.25rem;
          border-bottom: 1px solid var(--border);
          color: var(--text-primary);
        }
        .rd-h3 {
          font-size: 1.1rem;
          font-weight: 600;
          margin: 1.5rem 0 0.5rem 0;
          color: var(--accent);
        }
        .rd-h4 {
          font-size: 0.95rem;
          font-weight: 600;
          margin: 1rem 0 0.4rem 0;
          color: var(--text-secondary);
        }
        .rd-p { margin: 0.5rem 0; }
        .rd-hr {
          border: none;
          border-top: 1px solid var(--border);
          margin: 2rem 0;
        }
        .rd-ul, .rd-ol {
          margin: 0.5rem 0;
          padding-left: 1.5rem;
        }
        .rd-li, .rd-oli { margin: 0.25rem 0; }
        .rd-link {
          color: var(--accent);
          text-decoration: underline;
          text-underline-offset: 2px;
        }
        .rd-link:hover { opacity: 0.8; }
        .rd-inline-code {
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: 4px;
          padding: 1px 5px;
          font-family: var(--font-ibm-plex-mono), monospace;
          font-size: 0.85em;
        }
        .rd-code-block {
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 1rem;
          overflow-x: auto;
          font-family: var(--font-ibm-plex-mono), monospace;
          font-size: 0.8rem;
          line-height: 1.5;
          margin: 1rem 0;
        }
        .rd-table-wrap {
          overflow-x: auto;
          margin: 1rem 0;
          border-radius: 8px;
          border: 1px solid var(--border);
        }
        .rd-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.8rem;
        }
        .rd-table th {
          background: var(--bg-subtle);
          padding: 8px 12px;
          text-align: left;
          font-weight: 600;
          border-bottom: 1px solid var(--border);
          white-space: nowrap;
          color: var(--text-primary);
        }
        .rd-table td {
          padding: 6px 12px;
          border-bottom: 1px solid var(--border);
          color: var(--text-secondary);
        }
        .rd-table tbody tr:last-child td { border-bottom: none; }
        .rd-table tbody tr:hover { background: var(--accent-subtle); }
        .research-doc strong {
          font-weight: 600;
          color: var(--text-primary);
        }
        .research-doc em { font-style: italic; }
      `}</style>
    </div>
  );
}

/**
 * Renders trusted internal HTML content from our own research markdown files.
 * Content is pre-sanitized by renderMarkdown() which escapes all HTML entities.
 */
function ResearchContent({ html }: { html: string }) {
  return (
    <article
      className="research-doc"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
