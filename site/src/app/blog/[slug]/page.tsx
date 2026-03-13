import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { BLOG_POSTS } from '@/lib/blog-posts';
import BlogSections from '@/components/blog/BlogSections';

interface BlogPostPageProps {
  params: Promise<{ slug: string }>;
}

export function generateStaticParams() {
  return BLOG_POSTS.map((post) => ({
    slug: post.slug,
  }));
}

export async function generateMetadata({ params }: BlogPostPageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = BLOG_POSTS.find((p) => p.slug === slug);
  if (!post) return { title: 'Post não encontrado — Pulso Network' };
  const url = `https://pulso.network/blog/${post.slug}`;
  return {
    title: `${post.title} — Pulso Network`,
    description: post.excerpt,
    alternates: { canonical: url },
    openGraph: {
      title: post.title,
      description: post.excerpt,
      url,
      siteName: 'Pulso Network',
      type: 'article',
      publishedTime: post.date,
      authors: [post.author],
      locale: 'pt_BR',
    },
    twitter: {
      card: 'summary_large_image',
      title: post.title,
      description: post.excerpt,
    },
  };
}

export default async function BlogPostPage({ params }: BlogPostPageProps) {
  const { slug } = await params;
  const post = BLOG_POSTS.find((p) => p.slug === slug);
  if (!post) notFound();

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: post.title,
    description: post.excerpt,
    datePublished: post.date,
    author: { '@type': 'Organization', name: post.author || 'Pulso Network' },
    publisher: {
      '@type': 'Organization',
      name: 'Pulso Network',
      url: 'https://pulso.network',
    },
    mainEntityOfPage: `https://pulso.network/blog/${post.slug}`,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <Link
            href="/blog"
            className="inline-flex items-center gap-1 mb-6 font-mono text-xs uppercase tracking-wider transition-colors hover:text-white"
            style={{ color: 'var(--text-on-dark-muted)' }}
          >
            &larr; Blog
          </Link>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            {post.title}
          </h1>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            {post.category && (
              <span
                className="font-mono text-xs uppercase tracking-wider px-2 py-0.5"
                style={{ color: 'var(--accent)', border: '1px solid var(--accent)' }}
              >
                {post.category}
              </span>
            )}
            <span className="font-mono text-xs tabular-nums" style={{ color: 'var(--text-on-dark-muted)' }}>
              {new Date(post.date).toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: 'long',
                year: 'numeric',
              })}
            </span>
            <span className="text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
              {post.author}
            </span>
            {post.readingTime && (
              <span className="text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
                {post.readingTime}
              </span>
            )}
          </div>
        </div>
      </Section>

      {/* Content — Light */}
      <Section background="primary">
        <div className="max-w-3xl">
          {post.sections ? (
            <BlogSections sections={post.sections} />
          ) : (
            post.content.split('\n\n').map((paragraph, i) => (
              <p
                key={i}
                className="text-base leading-relaxed mb-6"
                style={{ color: 'var(--text-secondary)' }}
              >
                {paragraph}
              </p>
            ))
          )}
        </div>
      </Section>

      {/* CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Explore os dados na plataforma.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Acesso gratuito.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
            <Link href="/blog" className="pulso-btn-ghost">
              Mais artigos &rarr;
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
