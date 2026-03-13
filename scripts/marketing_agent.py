#!/usr/bin/env python3
"""Marketing content agent — generates AND auto-publishes content from live DB data.

Uses Claude Code CLI (`claude -p`) for content generation — no API key needed.
Blog posts are auto-inserted into blog-posts.ts and the site is rebuilt.
Pulso Semanal is also published as a blog post.
LinkedIn drafts are saved for manual posting.

Run daily via cron. Generates:
  - LinkedIn posts (Mon-Fri) → saved to marketing/drafts/ for manual posting
  - Blog post (Wed) → auto-published to site
  - Pulso Semanal report (Sat) → auto-published to site as blog post

Usage:
  python3 scripts/marketing_agent.py              # auto-detect day
  python3 scripts/marketing_agent.py linkedin      # LinkedIn drafts only
  python3 scripts/marketing_agent.py blog          # blog post → auto-publish
  python3 scripts/marketing_agent.py report        # Pulso Semanal → auto-publish
  python3 scripts/marketing_agent.py all           # everything

Requires:
  Claude Code CLI (`claude` command)
  PostgreSQL (enlace database)
"""

import json
import math
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

DB_DSN = os.getenv("DATABASE_URL", "dbname=enlace user=enlace")
BASE_DIR = Path(__file__).resolve().parent.parent
DRAFTS_DIR = BASE_DIR / "marketing" / "drafts"
BLOG_POSTS_TS = BASE_DIR / "site" / "src" / "lib" / "blog-posts.ts"
SITE_DIR = BASE_DIR / "site"

# ── Data queries ──────────────────────────────────────────────────────────────

QUERIES = {
    "market_overview": """
        SELECT
            COUNT(DISTINCT bs.provider_id) AS active_isps,
            COUNT(DISTINCT bs.l2_id) AS municipalities,
            SUM(bs.subscribers) AS total_subscribers,
            bs.year_month
        FROM broadband_subscribers bs
        WHERE bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
          AND bs.subscribers > 0
        GROUP BY bs.year_month
    """,
    "top_growth_municipalities": """
        WITH latest AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
              AND subscribers > 0
            GROUP BY l2_id
        ),
        prev_month AS (
            SELECT DISTINCT year_month FROM broadband_subscribers
            ORDER BY year_month DESC OFFSET 1 LIMIT 1
        ),
        previous AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers
            WHERE year_month = (SELECT year_month FROM prev_month)
              AND subscribers > 0
            GROUP BY l2_id
        )
        SELECT a2.name, a1.abbrev AS uf,
               l.subs AS current_subs, p.subs AS prev_subs,
               ROUND((l.subs - p.subs)::numeric / NULLIF(p.subs, 0) * 100, 1) AS growth_pct
        FROM latest l
        JOIN previous p ON p.l2_id = l.l2_id
        JOIN admin_level_2 a2 ON a2.id = l.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE p.subs > 1000
        ORDER BY growth_pct DESC
        LIMIT 10
    """,
    "monopoly_cities": """
        SELECT a2.name, a1.abbrev AS uf, a2.population,
               COUNT(DISTINCT bs.provider_id) AS isp_count,
               SUM(bs.subscribers) AS subs
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
          AND bs.subscribers > 0
        GROUP BY a2.id, a2.name, a1.abbrev, a2.population
        HAVING COUNT(DISTINCT bs.provider_id) = 1 AND SUM(bs.subscribers) > 500
        ORDER BY a2.population DESC
        LIMIT 15
    """,
    "fiber_leaders": """
        SELECT a2.name, a1.abbrev AS uf,
               SUM(CASE WHEN bs.technology IN ('fiber','ftth','fttb') THEN bs.subscribers ELSE 0 END) AS fiber,
               SUM(bs.subscribers) AS total,
               ROUND(SUM(CASE WHEN bs.technology IN ('fiber','ftth','fttb') THEN bs.subscribers ELSE 0 END)::numeric
                     / NULLIF(SUM(bs.subscribers), 0) * 100, 1) AS fiber_pct
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
          AND bs.subscribers > 0
        GROUP BY a2.id, a2.name, a1.abbrev
        HAVING SUM(bs.subscribers) > 5000
        ORDER BY fiber_pct DESC
        LIMIT 10
    """,
    "tax_debt_summary": """
        SELECT
            COUNT(DISTINCT provider_id) AS isps_with_debt,
            COUNT(*) AS total_records,
            ROUND(SUM(valor_consolidado)::numeric / 1e9, 1) AS total_billion_brl
        FROM provider_tax_debts
    """,
    "quality_seal_summary": """
        SELECT seal_level, COUNT(*) AS cnt
        FROM quality_seals
        WHERE year_half = (SELECT MAX(year_half) FROM quality_seals)
        GROUP BY seal_level
        ORDER BY cnt DESC
    """,
    "recent_complaints": """
        SELECT
            COUNT(*) AS total,
            ROUND(AVG(response_time_days)::numeric, 1) AS avg_response_days,
            ROUND(AVG(satisfaction_score)::numeric, 1) AS avg_satisfaction
        FROM consumer_complaints
    """,
}


def fetch_data():
    """Run all queries and return results dict."""
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    data = {}
    for name, query in QUERIES.items():
        try:
            cur.execute(query)
            rows = cur.fetchall()
            data[name] = [
                {k: str(v) if isinstance(v, (date, datetime)) else v for k, v in row.items()}
                for row in rows
            ]
        except Exception as e:
            conn.rollback()
            data[name] = {"error": str(e)}
    cur.close()
    conn.close()
    return data


def call_claude_code(prompt):
    """Call Claude Code CLI in non-interactive mode."""
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "text",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "2",
    ]
    try:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=300, cwd=str(BASE_DIR), env=env,
        )
        if result.returncode != 0:
            print(f"WARNING: claude exited with code {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
        return result.stdout or f"[ERROR: no output from claude]\nstderr: {result.stderr[:500]}"
    except FileNotFoundError:
        print("ERROR: 'claude' command not found. Install Claude Code CLI.")
        return ""
    except subprocess.TimeoutExpired:
        print("ERROR: claude timed out after 300s")
        return ""


def save_draft(category, filename, content):
    """Save draft to marketing/drafts/{category}/."""
    out_dir = DRAFTS_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(content)
    print(f"  Draft saved: {path}")
    return path


# ── Auto-publish helpers ─────────────────────────────────────────────────────

def escape_ts_string(s):
    """Escape a string for use inside TypeScript backtick template literal."""
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def estimate_reading_time(text):
    """Estimate reading time in minutes (200 wpm for PT-BR)."""
    words = len(text.split())
    return max(1, math.ceil(words / 200))


def parse_blog_output(raw):
    """Parse Claude's blog output into structured fields."""
    # Strip any Claude meta-commentary before TITLE:
    match = re.search(r'^TITLE:\s*(.+)', raw, re.MULTILINE)
    if not match:
        return None

    # Extract from TITLE: onwards
    text = raw[match.start():]

    fields = {}
    for key in ('TITLE', 'SLUG', 'EXCERPT', 'CATEGORY', 'TARGET_KEYWORD'):
        m = re.search(rf'^{key}:\s*(.+)', text, re.MULTILINE)
        if m:
            fields[key.lower()] = m.group(1).strip()

    if 'title' not in fields or 'slug' not in fields:
        return None

    # Extract content after the header block (after last field line + separator)
    content_match = re.search(r'(?:TARGET_KEYWORD|CATEGORY|EXCERPT|SLUG|TITLE):[^\n]*\n+(?:---\n+)?(.*)',
                              text, re.DOTALL)
    content = content_match.group(1).strip() if content_match else ""

    # Strip trailing meta-commentary (lines starting with "The report" or similar)
    content = re.sub(r'\n---\n\n(?:The |Want me |Note:|I ).*$', '', content, flags=re.DOTALL)
    # Strip **Nota metodologica** section if at very end
    content = content.rstrip()

    return {
        'slug': fields.get('slug', ''),
        'title': fields.get('title', ''),
        'excerpt': fields.get('excerpt', ''),
        'category': fields.get('category', ''),
        'content': content,
    }


def publish_to_blog(slug, title, excerpt, content, category=None, reading_time=None):
    """Insert a new blog post entry at the top of BLOG_POSTS array in blog-posts.ts."""
    today_str = date.today().isoformat()
    rt = reading_time or f"{estimate_reading_time(content)} min"

    # Build the TypeScript entry
    cat_line = f"    category: '{escape_ts_string(category)}',\n" if category else ""
    entry = (
        f"  {{\n"
        f"    slug: '{escape_ts_string(slug)}',\n"
        f"    title: '{escape_ts_string(title)}',\n"
        f"    excerpt:\n"
        f"      '{escape_ts_string(excerpt)}',\n"
        f"    date: '{today_str}',\n"
        f"    author: 'Equipe Pulso',\n"
        f"    content: `{escape_ts_string(content)}`,\n"
        f"{cat_line}"
        f"    readingTime: '{rt}',\n"
        f"  }},\n"
    )

    # Read current file
    ts_content = BLOG_POSTS_TS.read_text()

    # Check for duplicate slug
    if f"slug: '{slug}'" in ts_content:
        print(f"  SKIP: slug '{slug}' already exists in blog-posts.ts")
        return False

    # Insert after "export const BLOG_POSTS: BlogPost[] = [\n"
    marker = "export const BLOG_POSTS: BlogPost[] = [\n"
    idx = ts_content.find(marker)
    if idx == -1:
        print("  ERROR: could not find BLOG_POSTS array in blog-posts.ts")
        return False

    insert_at = idx + len(marker)
    new_content = ts_content[:insert_at] + entry + ts_content[insert_at:]
    BLOG_POSTS_TS.write_text(new_content)
    print(f"  Published to blog: /blog/{slug}")
    return True


def rebuild_site():
    """Rebuild the Next.js site."""
    print("  Rebuilding site...")
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True, text=True,
        timeout=600, cwd=str(SITE_DIR), env=env,
    )
    if result.returncode == 0:
        print("  Site rebuilt successfully.")
        return True
    else:
        print(f"  BUILD FAILED (exit {result.returncode})")
        # Print last 20 lines of stderr for debugging
        lines = (result.stderr or result.stdout or "").strip().split("\n")
        for line in lines[-20:]:
            print(f"    {line}")
        return False


# ── Content generators ────────────────────────────────────────────────────────

def generate_linkedin_posts(data, n=5):
    """Generate LinkedIn post drafts (saved for manual posting)."""
    data_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)

    prompt = f"""Read .agents/skills/social-content/SKILL.md and .agents/product-marketing-context.md first.

Then generate {n} LinkedIn posts in Portuguese (Brazil) for Pulso Network using this real data from our database:

{data_json}

RULES:
- Write in PT-BR, professional but accessible tone
- Each post: hook line + 3-5 short paragraphs + CTA to pulso.network
- Use real data from the stats provided — never fabricate numbers
- No emojis
- Mix post types: data insight, industry trend, contrarian take, behind-the-scenes
- Each post should be self-contained and valuable without clicking the link

Write {n} distinct posts, each separated by "---". Vary the hook styles (curiosity, value, contrarian, story).
Focus on insights that ISP owners/directors would find valuable and want to share.
Always end with a soft CTA mentioning pulso.network (waitlist or raio-x)."""

    result = call_claude_code(prompt)
    today = date.today().isoformat()
    save_draft("linkedin", f"{today}-batch.md", result)
    return result


def generate_blog_post(data):
    """Generate a blog post and auto-publish to site."""
    data_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)

    prompt = f"""Read these files first:
- .agents/skills/copywriting/SKILL.md
- .agents/skills/content-strategy/SKILL.md
- .agents/product-marketing-context.md
- site/src/lib/blog-posts.ts (to avoid duplicate topics)

Then write a data-driven blog post in Portuguese (Brazil) for Pulso Network using this real data from our database:

{data_json}

RULES:
- Write in PT-BR, editorial tone (like Bloomberg/Economist for telecom)
- Use real data — cite specific numbers from the stats provided
- Structure: compelling title + excerpt + 800-1200 words + sections with headers
- Include a "Recomendacao pratica" section at the end
- Mention Pulso Network naturally (not forced) — how the platform helps
- Target a specific long-tail keyword for SEO
- Do NOT repeat topics already covered in blog-posts.ts
- Use only ASCII characters in the SLUG (no accents)

Pick the most interesting insight from the data and build a compelling post around it.
The post should be something an ISP owner would share with their team.
Include the target keyword in the title and first paragraph.

Output format (EXACTLY this, no commentary before TITLE):
TITLE: ...
SLUG: ...
EXCERPT: ...
CATEGORY: ...
TARGET_KEYWORD: ...

[Full post content with ## headers]"""

    result = call_claude_code(prompt)
    if not result or result.startswith("["):
        print("  ERROR: No content generated")
        return result

    today = date.today().isoformat()
    save_draft("blog", f"{today}-post.md", result)

    # Parse and auto-publish
    parsed = parse_blog_output(result)
    if parsed:
        published = publish_to_blog(
            slug=parsed['slug'],
            title=parsed['title'],
            excerpt=parsed['excerpt'],
            content=parsed['content'],
            category=parsed['category'],
        )
        if published:
            return "published"
    else:
        print("  WARNING: Could not parse blog output for auto-publish")
        print("  Draft saved — publish manually")

    return result


def generate_weekly_report(data):
    """Generate Pulso Semanal and auto-publish as blog post."""
    data_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    week = date.today().isocalendar()[1]

    prompt = f"""Read .agents/product-marketing-context.md first.

Then create this week's "Pulso Semanal" weekly report in Portuguese (Brazil) using this real data from our database:

{data_json}

RULES:
- Write in PT-BR, concise data-driven format
- Structure: 5 key insights of the week, each with stat + context + implication
- Include a "Dado da Semana" highlight — the single most surprising stat
- End with "Proxima semana" teaser
- Keep it scannable — bullet points, bold numbers, short paragraphs
- Do NOT include any meta-commentary about errors, queries, or fixes

Output format (EXACTLY this, no commentary before TITLE):
TITLE: Pulso Semanal #{week} — [compelling subtitle about key insight]
SLUG: pulso-semanal-{week}-{date.today().year}
EXCERPT: [1-2 sentence summary of the key insights]
CATEGORY: Newsletter
TARGET_KEYWORD: mercado telecom brasil

[Full report content with ## headers]"""

    result = call_claude_code(prompt)
    if not result or result.startswith("["):
        print("  ERROR: No content generated")
        return result

    today_str = date.today().isoformat()
    save_draft("reports", f"pulso-semanal-{today_str}-w{week}.md", result)

    # Parse and auto-publish
    parsed = parse_blog_output(result)
    if parsed:
        published = publish_to_blog(
            slug=parsed['slug'],
            title=parsed['title'],
            excerpt=parsed['excerpt'],
            content=parsed['content'],
            category='Newsletter',
        )
        if published:
            return "published"
    else:
        print("  WARNING: Could not parse report output for auto-publish")
        print("  Draft saved — publish manually")

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    today = date.today()
    weekday = today.weekday()  # 0=Mon, 6=Sun

    print(f"Marketing Agent — {today.isoformat()} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][weekday]})")
    print(f"Mode: {mode}")

    # Fetch data
    print("\nFetching data from database...")
    data = fetch_data()

    # Print data summary
    overview = data.get("market_overview", [{}])
    if overview and not isinstance(overview, dict):
        ov = overview[0]
        print(f"  Active ISPs: {ov.get('active_isps', '?')}")
        print(f"  Municipalities: {ov.get('municipalities', '?')}")
        print(f"  Subscribers: {ov.get('total_subscribers', '?')}")

    # Determine what to generate
    tasks = []
    if mode == "auto":
        if weekday in (0, 1, 3, 4):  # Mon, Tue, Thu, Fri
            tasks.append("linkedin")
        if weekday == 2:  # Wed
            tasks.append("linkedin")
            tasks.append("blog")
        if weekday == 5:  # Sat
            tasks.append("report")
    elif mode == "all":
        tasks = ["linkedin", "blog", "report"]
    else:
        tasks = [mode]

    if not tasks:
        print("No tasks for today (Sunday). Use 'all' to force generation.")
        return

    print(f"\nGenerating: {', '.join(tasks)}")

    needs_rebuild = False
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"Generating: {task}")
        print('='*60)

        if task == "linkedin":
            generate_linkedin_posts(data)
        elif task == "blog":
            result = generate_blog_post(data)
            if result == "published":
                needs_rebuild = True
        elif task == "report":
            result = generate_weekly_report(data)
            if result == "published":
                needs_rebuild = True
        else:
            print(f"Unknown task: {task}")

    # Rebuild site once if any content was published
    if needs_rebuild:
        print(f"\n{'='*60}")
        print("Rebuilding site with new content")
        print('='*60)
        rebuild_site()

    print(f"\nDone.")
    if needs_rebuild:
        print("Blog/report auto-published and site rebuilt.")
    print(f"Drafts at: {DRAFTS_DIR}/")


if __name__ == "__main__":
    main()
