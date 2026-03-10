import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';
import { BLOG_POSTS } from '@/lib/blog-posts';

export const metadata: Metadata = {
  title: 'Blog — Pulso Network',
  description: 'Artigos sobre telecomunicações, expansão de ISPs e inteligência de mercado baseados em dados reais.',
};

export default function BlogPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Blog
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Análises baseadas em dados.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Não em opinião.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Artigos produzidos pela equipe Pulso com base em 17M+ registros reais de
            telecomunicações, demografia e infraestrutura do Brasil.
          </p>
        </div>
      </Section>

      {/* Posts — Light */}
      <Section background="primary">
        <div className="space-y-0">
          {BLOG_POSTS.map((post, i) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="block group"
            >
              <div
                className="grid grid-cols-1 gap-4 py-10 md:grid-cols-[1fr_2fr] md:gap-10"
                style={{ borderBottom: i < BLOG_POSTS.length - 1 ? '1px solid var(--border)' : 'none' }}
              >
                <div>
                  <div className="font-mono text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                    {new Date(post.date).toLocaleDateString('pt-BR', {
                      day: '2-digit',
                      month: 'long',
                      year: 'numeric',
                    })}
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {post.author}
                  </div>
                  {post.category && (
                    <div
                      className="mt-2 inline-block font-mono text-xs uppercase tracking-wider px-2 py-0.5"
                      style={{ color: 'var(--accent)', border: '1px solid var(--accent)' }}
                    >
                      {post.category}
                    </div>
                  )}
                  {post.readingTime && (
                    <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                      {post.readingTime}
                    </div>
                  )}
                </div>
                <div>
                  <h2
                    className="text-xl font-semibold transition-colors group-hover:text-[var(--accent)]"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {post.title}
                  </h2>
                  <p className="mt-3 text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    {post.excerpt}
                  </p>
                  <div
                    className="mt-4 font-mono text-xs uppercase tracking-wider"
                    style={{ color: 'var(--accent)' }}
                  >
                    Ler artigo &rarr;
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </Section>

      {/* CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Explore os dados você mesmo.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Acesso gratuito ao mapa e dados básicos.</span>
          </h2>
          <div className="mt-6">
            <Link href="/cadastro" className="pulso-btn-dark">
              Criar conta gratuita
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
