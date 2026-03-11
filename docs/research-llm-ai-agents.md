# LLM, AI Agent & Conversational AI Integration Research

**Date:** 2026-03-11
**Platform:** Enlace (Pulso) Telecom Intelligence Platform
**Stack:** FastAPI (Python) + Next.js 14 + PostgreSQL/PostGIS (45+ tables, 12M+ records) + Rust RF Engine

---

## Table of Contents

1. [Text-to-SQL / Natural Language Database Querying](#1-text-to-sql--natural-language-database-querying)
2. [AI Agents for Telecom Workflows](#2-ai-agents-for-telecom-workflows)
3. [RAG (Retrieval Augmented Generation)](#3-rag-retrieval-augmented-generation)
4. [Generative AI for Reports](#4-generative-ai-for-reports)
5. [Voice & Multimodal](#5-voice--multimodal)
6. [Vector Database Options](#6-vector-database-options)
7. [Brazilian Portuguese LLM Support](#7-brazilian-portuguese-llm-support)
8. [Frontend Chat Components](#8-frontend-chat-components)
9. [Prioritized Roadmap](#9-prioritized-roadmap)

---

## 1. Text-to-SQL / Natural Language Database Querying

Enable users to ask questions in natural language: "Which municipalities in Para have subscriber growth above 15% but no fiber provider?" and get instant answers from the 12M+ record database.

### 1a. Vanna.ai

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/vanna-ai/vanna |
| **Website** | https://vanna.ai |
| **Stars** | ~20K GitHub |
| **License** | MIT |
| **Maturity** | Production (Vanna 2.0 released late 2025) |
| **Language** | Python |

**What it does:** RAG-based text-to-SQL. Trains on your schema + sample queries + documentation, then generates accurate SQL from natural language. Vanna 2.0 introduced an agent-based API, user-aware components, and enterprise security (row-level security, group-based access, audit logging).

**Integration with our stack:**
- Native PostgreSQL support via `psycopg2` or `SQLAlchemy`
- Python library drops directly into FastAPI as a new router
- Can train on our 45+ tables, materialized views (`mv_market_summary`), and PostGIS spatial queries
- Supports custom LLM backends (Claude, GPT-4, local models)

**Effort estimate:** 2-3 weeks for MVP (schema training + single endpoint), 4-6 weeks production-ready with caching and guardrails.

**Portuguese support:** Works through underlying LLM -- Claude and GPT-4 handle Portuguese well. Schema descriptions and training examples should be bilingual.

**Impact:** HIGH. Democratizes access to 12M+ records for non-technical users. ISP operators could ask "Qual o market share da Vivo em Manaus?" without SQL knowledge.

**Sample integration:**
```python
# FastAPI router
from vanna.remote import VannaDefault

vn = VannaDefault(model='enlace-telecom', api_key='...')
vn.connect_to_postgres(host='localhost', dbname='enlace', user='enlace')

# Train on schema
vn.train(ddl="CREATE TABLE broadband_subscribers (id SERIAL, l2_id INT, ...)")
vn.train(documentation="l2_id refers to municipality ID in admin_level_2 table")
vn.train(sql="SELECT a.name, SUM(b.subscribers) FROM admin_level_2 a JOIN broadband_subscribers b ON a.id = b.l2_id GROUP BY a.name")

@router.post("/api/ask")
async def ask_database(question: str):
    sql = vn.generate_sql(question)
    result = vn.run_sql(sql)
    return {"sql": sql, "data": result}
```

**References:**
- [Vanna GitHub](https://github.com/vanna-ai/vanna)
- [Vanna 2.0 + NVIDIA NIM](https://developer.nvidia.com/blog/accelerating-text-to-sql-inference-on-vanna-with-nvidia-nim-for-faster-analytics/)
- [Vanna AI Hands-on Guide](https://vnproductbuilder.substack.com/p/vanna-ai-hands-on-building-a-context)

---

### 1b. Wren AI

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/Canner/WrenAI |
| **Stars** | ~10K GitHub |
| **License** | AGPL-3.0 |
| **Maturity** | Production |
| **Language** | Python + TypeScript |

**What it does:** Full Generative BI platform with semantic modeling layer. Goes beyond raw text-to-SQL by maintaining a semantic model (business logic, relationships, metrics definitions) that ensures consistent query interpretation across users. Generates both SQL (Text-to-SQL) and charts (Text-to-Chart).

**Integration:** More heavyweight than Vanna -- designed as a standalone platform rather than an embeddable library. Better suited if we want to offer a full BI experience. AGPL license requires careful consideration for commercial use.

**Effort estimate:** 4-6 weeks to deploy and configure semantic model, 8+ weeks for full integration.

**Impact:** MEDIUM-HIGH. Better governance than Vanna, but heavier integration weight. Best if we want a standalone analytics product.

**References:**
- [Wren AI GitHub](https://github.com/Canner/WrenAI)
- [Wren AI vs Vanna Comparison](https://www.getwren.ai/post/wren-ai-vs-vanna-the-enterprise-guide-to-choosing-a-text-to-sql-solution)

---

### 1c. LangChain SQL Agent

| Attribute | Details |
|-----------|---------|
| **URL** | https://docs.langchain.com/oss/python/langchain/sql-agent |
| **License** | MIT |
| **Maturity** | Stable |
| **Language** | Python |

**What it does:** Agent-based approach where the LLM iteratively inspects schema, writes SQL, executes queries, and interprets results. Can self-correct on errors. Supports custom table descriptions so the agent understands field semantics without repeated schema inspection.

**Integration with our stack:**
- `langchain-community` + `SQLAlchemy` connects directly to PostgreSQL
- Agent can treat views (`mv_market_summary`) as first-class citizens
- Integrates with FastAPI via `langchain-postgres` package
- Can reduce codebase complexity by ~70% compared to hand-rolled query builders

**Effort estimate:** 2-3 weeks MVP. More flexible than Vanna but requires more prompt engineering for accuracy.

**Portuguese support:** Inherits from underlying LLM (Claude/GPT-4).

**Impact:** HIGH. Most flexible approach, supports complex multi-step queries with self-correction.

**References:**
- [LangChain SQL Agent Docs](https://docs.langchain.com/oss/python/langchain/sql-agent)
- [Conversational SQL Agent with LangChain and FastAPI](https://medium.com/@silverskytechnology/building-a-conversational-sql-agent-with-langchain-and-fastapi-7fb2c96228a5)
- [AI-Powered Q&A API with FastAPI + LangChain](https://medium.com/@joshua_briggs/building-an-ai-powered-q-a-api-with-fastapi-langchain-and-postgresql-8cffbc7f3e35)

---

### 1d. SQLCoder (Self-Hosted)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/defog-ai/sqlcoder |
| **Model** | SQLCoder-70B (93% accuracy), SQLCoder-7B (lighter) |
| **License** | Apache 2.0 |
| **Maturity** | Production |
| **Format** | HuggingFace model |

**What it does:** Purpose-built open-source LLM for text-to-SQL. SQLCoder-70B achieves 93% accuracy on unseen schemas, outperforming GPT-4. Can be fine-tuned on specific database schemas for even higher accuracy.

**Integration:** Requires GPU infrastructure for inference (A100 for 70B, T4 for 7B). Can be served via vLLM or Ollama and called from FastAPI. Best for air-gapped or cost-sensitive deployments where API costs are a concern.

**Effort estimate:** 3-4 weeks (including infrastructure setup). Fine-tuning on our schema: additional 1-2 weeks.

**Impact:** MEDIUM. Best accuracy for offline/self-hosted scenarios. No API costs after deployment.

**References:**
- [SQLCoder GitHub](https://github.com/defog-ai/sqlcoder)
- [SQLCoder-70B Announcement](https://defog.ai/blog/open-sourcing-sqlcoder-70b/)
- [SQLCoder on Ollama](https://ollama.com/library/sqlcoder)

---

### 1e. DuckDB + LLM (Analytical Acceleration)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/harshanal/duckdb-llm-agent |
| **License** | MIT |
| **Maturity** | Emerging |

**What it does:** Uses DuckDB as a local analytical engine combined with LLMs for natural language queries. DuckDB-NSQL is a specialized model trained on DuckDB SQL syntax. FlockMTL extension enables LLM function calls directly within SQL.

**Integration:** Could serve as a read-replica analytical layer. Export PostgreSQL data to Parquet, query via DuckDB + LLM for fast analytics without loading the production database.

**Effort estimate:** 2-3 weeks. Complements rather than replaces PostgreSQL.

**Impact:** MEDIUM. Fast analytical queries on exported data. Good for dashboards and batch analysis.

**References:**
- [DuckDB-NSQL-7B](https://motherduck.com/blog/duckdb-text2sql-llm/)
- [FlockMTL Extension](https://duckdb.org/community_extensions/extensions/flockmtl)
- [DuckDB + LangChain](https://medium.com/@kaushalsinh73/duckdb-langchain-querying-your-data-with-natural-language-6c2a5b2d545e)

---

### Recommendation for Text-to-SQL

**Start with Vanna.ai** for fastest time-to-value:
1. MIT license, pure Python, drops into FastAPI
2. Train on our 45+ tables with Portuguese descriptions
3. Add LangChain SQL Agent as fallback for complex multi-step queries
4. Consider SQLCoder for self-hosted fine-tuned accuracy later

---

## 2. AI Agents for Telecom Workflows

### 2a. Claude Agent SDK (Anthropic)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/anthropics/claude-agent-sdk-python |
| **PyPI** | `claude-agent-sdk` |
| **License** | Proprietary (API-based) |
| **Maturity** | Production |
| **Language** | Python + TypeScript |

**What it does:** Official SDK for building AI agents with Claude. Supports tool use, structured outputs, Agent Skills (composable expertise packages), and multi-agent coordination. Agents can orchestrate tools through code rather than individual API round-trips.

**Telecom workflow applications:**
- **RF Coverage Analysis Agent:** Takes municipality name, calls Rust gRPC for terrain analysis, coverage simulation, and returns narrative + map
- **M&A Due Diligence Agent:** Queries subscriber data, computes valuations, compares against peers, generates target profiles
- **Compliance Monitor Agent:** Checks Anatel deadlines, flags upcoming obligations, drafts response documents
- **Network Design Agent:** Given a region, runs tower optimization, fiber route planning, and cost estimation

**Integration:**
```python
from claude_agent_sdk import Agent, Tool

# Define tools that map to our existing API endpoints
subscriber_tool = Tool(
    name="query_subscribers",
    description="Query broadband subscriber data by municipality",
    function=query_subscribers_endpoint
)

rf_coverage_tool = Tool(
    name="run_rf_coverage",
    description="Run RF coverage simulation using Rust engine",
    function=call_rust_grpc_coverage
)

agent = Agent(
    model="claude-opus-4-5-20250414",
    tools=[subscriber_tool, rf_coverage_tool, ...],
    system="You are a Brazilian telecom intelligence analyst..."
)
```

**Effort estimate:** 3-4 weeks for single-agent MVP with 5-8 tools, 6-8 weeks for multi-agent system.

**Portuguese support:** Claude has excellent Portuguese support. Tested on telecom-specific agent scenarios.

**Impact:** VERY HIGH. Turns every API endpoint into an agent-callable tool. Users describe what they want; the agent orchestrates the full workflow.

**References:**
- [Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python)
- [Building Agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Claude Agent SDK Docs](https://platform.claude.com/docs/en/agent-sdk/overview)

---

### 2b. LangGraph (Multi-Agent Orchestration)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/langchain-ai/langgraph |
| **Stars** | ~38M monthly PyPI downloads |
| **License** | MIT |
| **Maturity** | Production (v1.0 stable) |
| **Language** | Python |

**What it does:** Graph-based agent orchestration framework. Agents are nodes, edges define control flow. Built-in checkpointing to PostgreSQL via `PostgresSaver`, enabling pause/resume, fault tolerance, and state inspection.

**Why it matters for Enlace:**
- **Stateful workflows:** M&A analysis that spans multiple sessions -- agent remembers context
- **Human-in-the-loop:** Agent proposes RF design, waits for human approval before running optimization
- **Fault tolerance:** If Rust gRPC call fails mid-workflow, resume from last checkpoint
- **PostgreSQL native:** Checkpoints stored in our existing PostgreSQL, no new infrastructure

**Integration with FastAPI:**
```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        graph = build_telecom_agent_graph()
        app.state.agent = graph.compile(checkpointer=checkpointer)
        yield

@router.post("/api/agent/run")
async def run_agent(request: AgentRequest):
    config = {"configurable": {"thread_id": request.session_id}}
    result = await app.state.agent.ainvoke(request.input, config)
    return result
```

**Effort estimate:** 4-6 weeks for multi-agent system with PostgreSQL persistence.

**Impact:** VERY HIGH. Production-grade multi-agent orchestration with our existing PostgreSQL.

**References:**
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [FastAPI + LangGraph Production Template](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template)
- [LangGraph PostgreSQL Checkpointing](https://dev.to/programmingcentral/unlocking-ai-resilience-mastering-state-persistence-with-langgraph-and-postgresql-50h0)

---

### 2c. CrewAI (Role-Based Multi-Agent)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/crewAI/crewAI |
| **Stars** | ~44.6K GitHub |
| **License** | MIT |
| **Maturity** | Production |
| **Language** | Python |

**What it does:** Define agents with roles, goals, and backstories. Agents collaborate on tasks in sequential or hierarchical processes. Fastest time-to-prototype for multi-agent systems.

**Telecom use case example:**
```python
from crewai import Agent, Task, Crew

market_analyst = Agent(
    role="Brazilian Telecom Market Analyst",
    goal="Analyze subscriber data and competitive dynamics",
    backstory="Expert in Brazilian ISP market with deep knowledge of Anatel data"
)

rf_engineer = Agent(
    role="RF Network Design Engineer",
    goal="Design optimal tower placements using terrain data",
    backstory="Experienced in ITU-R propagation models and SRTM terrain analysis"
)

# Task: Full M&A target assessment
mna_task = Task(
    description="Evaluate {municipality} as an M&A target: subscriber trends, competition, infrastructure gaps",
    agent=market_analyst
)

crew = Crew(agents=[market_analyst, rf_engineer], tasks=[mna_task])
result = crew.kickoff(inputs={"municipality": "Manaus"})
```

**Effort estimate:** 1-2 weeks for prototype, 3-4 weeks production. Note: teams often migrate to LangGraph when hitting CrewAI's control flow limits.

**Impact:** HIGH for rapid prototyping. Consider as stepping stone to LangGraph.

**References:**
- [CrewAI GitHub](https://github.com/crewAI/crewAI)
- [LangGraph vs CrewAI 2026 Comparison](https://particula.tech/blog/langgraph-vs-crewai-vs-openai-agents-sdk-2026)
- [Multi-Agent Framework Guide 2026](https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63)

---

### 2d. M&A Due Diligence Automation

| Attribute | Details |
|-----------|---------|
| **Approach** | Multi-agent workflow using any of the frameworks above |
| **License** | N/A (custom implementation) |
| **Maturity** | Emerging pattern |

**What it does:** Automates M&A due diligence workflows:
- Data room document analysis (contracts, financials)
- Dynamic financial modeling with real-time adjustments
- Subscriber trend analysis and valuation
- Competitive landscape assessment
- Risk flagging and anomaly detection

**Industry metrics (2025):**
- 75% efficiency savings vs. manual due diligence review
- ~20% cost reduction in M&A activities
- 30-50% faster deal cycles
- 40% higher accuracy in valuation models with automated data pipelines

**Integration with Enlace:**
Our M&A module already has subscriber data, competitive analysis, and network infrastructure data. An AI agent could:
1. Pull subscriber growth data for target municipality
2. Calculate DCF/comparable valuations using existing formulas
3. Assess network infrastructure gaps via Rust RF engine
4. Generate narrative report with risk factors
5. Compare against similar past acquisitions

**Effort estimate:** 4-6 weeks, building on existing M&A API endpoints.

**Impact:** VERY HIGH for premium clients. Transforms hours of manual analysis into minutes.

**References:**
- [AI in M&A Due Diligence 2025](https://rtslabs.com/ai-due-diligence/)
- [Gen AI in M&A - McKinsey](https://www.mckinsey.com/capabilities/m-and-a/our-insights/gen-ai-in-m-and-a-from-theory-to-practice-to-high-performance)
- [Deloitte: Multi-Agent Systems for M&A](https://www.deloitte.com/cz-sk/en/services/consulting/blogs/where-is-the-value-of-AI-in-MA-why-multi-agent-systems-needs-modern-data-architecture.html)

---

### Recommendation for AI Agents

**Phase 1:** Claude Agent SDK for single-agent tool-use (3-4 weeks)
**Phase 2:** LangGraph for stateful multi-agent workflows with PostgreSQL checkpointing (4-6 weeks)
**Phase 3:** Specialized M&A due diligence agent built on Phase 2 infrastructure

---

## 3. RAG (Retrieval Augmented Generation)

### 3a. Regulatory Document RAG (Anatel + DOU + Municipal Gazettes)

| Attribute | Details |
|-----------|---------|
| **Data Sources** | Anatel resolutions, DOU publications, Querido Diario municipal gazettes |
| **Approach** | Chunked document embedding + vector similarity search + LLM generation |
| **License** | Component-dependent |
| **Maturity** | Well-established pattern |

**What it does:** Embeds regulatory documents into a vector store, retrieves relevant passages for user queries, and generates accurate answers grounded in source material.

**Specific data sources for our platform:**

1. **Anatel Regulations:** Resolution 777/2025 (RGST -- consolidated 34 resolutions), spectrum auction rules, quality regulations. Anatel's own AI tool "Regulatron" already automates regulatory analysis.
2. **DOU (Diario Oficial da Uniao):** Federal gazette publications related to telecom. Our existing `dou_anatel` pipeline already collects these.
3. **Querido Diario:** Open-source project (MIT + CC-BY) that scrapes and structures Brazilian municipal gazettes. Has a FastAPI-based API at https://github.com/okfn-brasil/querido-diario-api. Critical for identifying municipal licensing requirements, right-of-way regulations, and local telecom incentives.

**Architecture:**
```
Documents --> Chunking --> Embedding --> pgvector --> Retrieval
                                                       |
User Query --> Embedding --> Similarity Search ---------+
                                                       |
                                          LLM Generation (with context)
                                                       |
                                              Answer + Citations
```

**Integration:**
- Use pgvector (already in our PostgreSQL) for embedding storage
- LangChain or LlamaIndex for document processing pipeline
- FastAPI endpoint: `/api/regulatory/ask`
- Sources: existing `dou_anatel` pipeline output + Querido Diario API + scraped Anatel PDFs

**Effort estimate:** 4-6 weeks for regulatory RAG MVP.

**Portuguese support:** Essential -- all regulatory documents are in Portuguese. Embedding models must handle PT-BR well (multilingual-e5-large, Cohere multilingual).

**Impact:** VERY HIGH. Compliance is a core value proposition. "Is my tower permit compliant with the new RGST?" answered in seconds.

**References:**
- [Querido Diario API](https://github.com/okfn-brasil/querido-diario-api)
- [Querido Diario Documentation](https://docs.queridodiario.ok.org.br/en/latest/)
- [Anatel RGST Reform](https://globalvalidity.com/brazil-anatel-approves-major-reform-to-modernize-telecom-regulations/)
- [RAG for Legal Research](https://www.datategy.net/2025/04/14/how-law-firms-use-rag-to-boost-legal-research/)
- [Policy Compliance Checker RAG](https://medium.com/@rameeshamalik.143/policy-compliance-checker-rag-system-1fc9f5f2f3db)

---

### 3b. Platform Documentation RAG (User Onboarding)

| Attribute | Details |
|-----------|---------|
| **Approach** | RAG over platform docs, help articles, tutorials |
| **License** | Component-dependent |
| **Maturity** | Well-established |

**What it does:** Users can ask "How do I run an RF coverage simulation?" or "What does the opportunity score mean?" and get contextual answers from platform documentation.

**Integration:** Lightweight -- embed existing docs, API descriptions, and feature explanations. Can reuse the same pgvector infrastructure as regulatory RAG.

**Effort estimate:** 1-2 weeks (after regulatory RAG infrastructure is built).

**Impact:** MEDIUM. Reduces support burden, improves onboarding.

---

### 3c. RAG Infrastructure (danny-avila/rag_api)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/danny-avila/rag_api |
| **License** | MIT |
| **Maturity** | Production |
| **Language** | Python (FastAPI) |

**What it does:** ID-based RAG API built on FastAPI + LangChain + PostgreSQL/pgvector. Provides a complete REST API for document upload, embedding, and retrieval. Designed for integration with chat applications.

**Integration:** Almost drop-in -- same tech stack (FastAPI + PostgreSQL + pgvector). Could serve as starter template for our RAG implementation.

**Effort estimate:** 1 week to adapt to our needs.

**Impact:** Accelerates RAG development.

**Reference:** [rag_api GitHub](https://github.com/danny-avila/rag_api)

---

### Recommendation for RAG

1. Install pgvector extension in our PostgreSQL (see Section 6a)
2. Build regulatory document RAG using Anatel + DOU + Querido Diario sources
3. Reuse infrastructure for platform documentation RAG
4. Consider danny-avila/rag_api as starter template

---

## 4. Generative AI for Reports

### 4a. LlamaIndex Multi-Agent Report Generation

| Attribute | Details |
|-----------|---------|
| **URL** | https://developers.llamaindex.ai/python/examples/agent/agent_workflow_multi/ |
| **License** | MIT |
| **Maturity** | Production |
| **Language** | Python |

**What it does:** Multi-agent workflow for structured report generation:
- **Researcher Agent:** Retrieves and evaluates data
- **Writer Agent:** Generates formatted content using Pydantic-defined schemas
- **Editor Agent:** Reviews and refines output

**LlamaReport** (new in 2025) transforms documents into structured reports with table of contents, sections, and citations.

**Integration with Enlace:**
```python
from pydantic import BaseModel
from typing import List

class MunicipalityReport(BaseModel):
    executive_summary: str
    subscriber_analysis: SubscriberSection
    competitive_landscape: CompetitiveSection
    infrastructure_assessment: InfrastructureSection
    opportunity_score: float
    recommendations: List[str]

# Agent generates report matching this schema
```

**Effort estimate:** 3-4 weeks for report generation pipeline.

**Impact:** HIGH. Auto-generated municipal analysis reports, M&A target profiles, and competitive intelligence briefs.

**References:**
- [Multi-Agent Report Generation](https://developers.llamaindex.ai/python/examples/agent/agent_workflow_multi/)
- [LlamaReport Preview](https://www.llamaindex.ai/blog/llamareport-preview-transform-any-documents-into-structured-reports)
- [Building Blocks of LLM Report Generation](https://www.llamaindex.ai/blog/building-blocks-of-llm-report-generation-beyond-basic-rag)

---

### 4b. Direct LLM Report Generation (Claude/GPT-4)

| Attribute | Details |
|-----------|---------|
| **Approach** | Structured prompts with data context |
| **License** | API-based |
| **Maturity** | Production |

**What it does:** Feed structured data (query results, computed metrics) to Claude/GPT-4 with report templates. Generate:
- Executive summaries: "Subscriber growth in Manaus accelerated 23% vs. peers in Q4 2025"
- Competitive intelligence narratives per municipality
- M&A target profiles with risk assessment
- Monthly market trend reports

**Integration with existing report generator:**
Our `python/reports/generator.py` already produces structured data. Adding an LLM layer transforms data into narrative:

```python
# Current: returns JSON with numbers
report_data = generate_market_report(municipality_id=1234)

# Enhanced: returns narrative + data
narrative = await claude.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{
        "role": "user",
        "content": f"""Generate an executive summary for this telecom market report.
        Data: {json.dumps(report_data)}
        Format: 3-paragraph summary in Portuguese, highlighting key trends,
        risks, and opportunities."""
    }]
)
```

**Effort estimate:** 1-2 weeks for narrative layer on existing reports.

**Impact:** HIGH. Transforms raw data into actionable intelligence narratives.

**References:**
- [LLM-Powered Reporting](https://medium.com/@mail2mhossain/llm-powered-reporting-transforming-traditional-reporting-into-ai-driven-solutions-14a188793760)
- [LLMs for Business Intelligence](https://querio.ai/articles/llms-and-the-promise-of-personalized-business-intelligence)

---

### Recommendation for Reports

**Phase 1:** Add Claude narrative layer to existing report generator (1-2 weeks)
**Phase 2:** Pydantic-structured report schemas with LlamaIndex multi-agent generation (3-4 weeks)

---

## 5. Voice & Multimodal

### 5a. Voice Queries (Field Technicians)

| Attribute | Details |
|-----------|---------|
| **Technology** | OpenAI Whisper (speech-to-text) + LLM + TTS |
| **Models** | gpt-4o-transcribe, gpt-4o-mini-transcribe, whisper-medium-portuguese |
| **Portuguese** | Full support (PT-BR trained models available on HuggingFace) |

**What it does:** Field technicians speak queries while working on towers/equipment:
- "Qual a cobertura de sinal nesta coordenada?" (What's the signal coverage at this coordinate?)
- "Registrar defeito na torre 4532" (Log defect on tower 4532)
- Hands-free data capture during inspections

**Integration:**
```
Mobile App --> Whisper (PT-BR) --> Text --> Agent (tool use) --> TTS --> Audio Response
```

**Portuguese-specific models:**
- `pierreguillou/whisper-medium-portuguese` on HuggingFace -- fine-tuned for PT-BR
- OpenAI's native Portuguese support in gpt-4o-transcribe

**Effort estimate:** 4-6 weeks (requires mobile app component or PWA).

**Impact:** MEDIUM-HIGH for field operations. Differentiator for ISP clients with field teams.

**References:**
- [OpenAI Speech-to-Text](https://developers.openai.com/api/docs/guides/speech-to-text/)
- [Whisper Portuguese Model](https://huggingface.co/pierreguillou/whisper-medium-portuguese)
- [Next-Gen Audio Models](https://openai.com/index/introducing-our-next-generation-audio-models/)
- [Voice to Form for Field Service](https://www.startuphub.ai/ai-news/ai-research/2025/voice-to-form-redefines-ai-field-service-operations/)

---

### 5b. Image Upload for Infrastructure Assessment

| Attribute | Details |
|-----------|---------|
| **Technology** | Claude Vision / GPT-4V + domain-specific models |
| **Maturity** | Production (general), Emerging (telecom-specific) |

**What it does:** Upload photo of tower/equipment, AI assesses:
- Structural condition (cracks, corrosion, vegetation encroachment)
- Equipment identification (antenna type, manufacturer)
- Compliance with installation standards
- Comparison against design specifications

**Integration:** Add image upload endpoint to FastAPI, send to multimodal LLM:
```python
@router.post("/api/infrastructure/assess")
async def assess_infrastructure(image: UploadFile, location: str):
    image_data = base64.b64encode(await image.read())
    response = await claude.messages.create(
        model="claude-opus-4-5-20250414",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "data": image_data}},
                {"type": "text", "text": f"Assess this telecom infrastructure at {location}. Identify equipment, condition, and any compliance issues."}
            ]
        }]
    )
```

**Effort estimate:** 2-3 weeks for MVP.

**Impact:** MEDIUM. Useful for due diligence and field inspections.

**References:**
- [Vision AI for Telecom](https://www.ultralytics.com/blog/vision-ai-telecom-solutions-are-driving-safer-network-operations)
- [AI Infrastructure Monitoring](https://landing.ai/industries/infrastructure)
- [WEF: AI in Telecommunications 2025](https://reports.weforum.org/docs/WEF_Artificial_Intelligence_in_Telecommunications_2025.pdf)

---

### 5c. WhatsApp Bot for ISP Operators

| Attribute | Details |
|-----------|---------|
| **Technology** | WhatsApp Business API + LLM agent |
| **Platforms** | WATI, Chakra Chat, Aurora Inbox |
| **Regulatory** | Meta reversed third-party chatbot ban in Brazil (Jan 2026) |

**What it does:** ISP operators (120M+ WhatsApp users in Brazil) interact with the platform via WhatsApp:
- "Quantos assinantes perdemos em Belem este mes?" (How many subscribers did we lose in Belem this month?)
- "Alerta: prazo Anatel vence em 5 dias" (Alert: Anatel deadline in 5 days)
- Quick competitive intelligence checks

**Key regulatory update:** Meta reversed the WhatsApp third-party AI chatbot ban for Brazil and Italy in January 2026, explicitly allowing LLM-based customer support chats.

**Integration architecture:**
```
WhatsApp API (WATI/Twilio) --> Webhook --> FastAPI --> Agent (Claude) --> Response --> WhatsApp
```

**Effort estimate:** 4-6 weeks (including WhatsApp Business API setup).

**Impact:** VERY HIGH in Brazil. WhatsApp is the primary business communication channel. This alone could be a major acquisition driver.

**References:**
- [Top WhatsApp API Tools in Brazil 2025](https://www.wati.io/en/blog/top-5-whatsapp-business-api-tools-brazil/)
- [Meta Reverses Chatbot Ban in Brazil](https://9to5mac.com/2026/01/15/meta-reverses-whatsapp-third-party-chatbot-ban-in-italy-and-brazil/)
- [WhatsApp LLM Bot Guide](https://medium.com/data-science/build-a-whatsapp-llm-bot-a-guide-for-lazy-solo-programmers-24934d8f5488)
- [Best AI Chatbots for WhatsApp 2025](https://www.aurorainbox.com/en/2026/01/25/best-chatbots-ia-whatsapp/)

---

### Recommendation for Voice & Multimodal

**Phase 1:** WhatsApp bot (highest impact in Brazil market) -- 4-6 weeks
**Phase 2:** Image upload for infrastructure assessment -- 2-3 weeks
**Phase 3:** Voice queries for field technicians -- 4-6 weeks (requires mobile app)

---

## 6. Vector Database Options

### 6a. pgvector (RECOMMENDED -- Use What We Have)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/pgvector/pgvector |
| **License** | PostgreSQL License (very permissive) |
| **Maturity** | Production |
| **Integration** | Extension to our existing PostgreSQL |

**Why pgvector is the right choice:**
- **Zero new infrastructure** -- extends our existing PostgreSQL
- ACID transactions -- embeddings participate in normal transactions
- Join vector tables with relational tables in single SQL query
- HNSW and IVF indexes for fast similarity search
- Performs well up to ~1M vectors (our regulatory corpus will be well under this)
- Works with SQLAlchemy, LangChain, LlamaIndex natively

**Setup:**
```sql
CREATE EXTENSION vector;

CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES regulatory_documents(id),
    content TEXT,
    embedding vector(1024),  -- dimension depends on model
    metadata JSONB
);

CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops);
```

**Effort estimate:** 1 day to install and configure.

**Impact:** Enables all RAG features with zero additional infrastructure cost.

**References:**
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [FastAPI + pgvector RAG Backend](https://medium.com/@fredyriveraacevedo13/building-a-fastapi-powered-rag-backend-with-postgresql-pgvector-c239f032508a)
- [pgvector RAG Guide](https://encore.dev/blog/you-probably-dont-need-a-vector-database)

---

### 6b. Pinecone (Managed Alternative)

| Attribute | Details |
|-----------|---------|
| **URL** | https://www.pinecone.io |
| **License** | Proprietary (managed service) |
| **Pricing** | Free tier --> $50/mo Starter --> $500/mo Enterprise |
| **Maturity** | Production |

**When to consider:** If vector corpus exceeds 1M+ documents, need multi-region, or want zero-ops. BYOC launch (Feb 2026) supports data sovereignty requirements. Built-in embedding generation reduces integration complexity.

**Effort estimate:** 1-2 weeks.

**Impact:** MEDIUM. Only justified at scale beyond pgvector's comfort zone.

**References:**
- [Pinecone vs Qdrant 2026](https://particula.tech/blog/pinecone-vs-qdrant-comparison)
- [Vector Database Comparison](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)

---

### 6c. Qdrant (Self-Hosted High Performance)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/qdrant/qdrant |
| **License** | Apache 2.0 |
| **Maturity** | Production |
| **Performance** | 22ms p95 (vs. 45ms Pinecone) |
| **Cost** | ~$45/mo at 10M vectors (vs. ~$70 Pinecone) |

**When to consider:** If we need dedicated vector database performance at scale. Built in Rust (matches our stack philosophy). 2x lower latency at half the cost of Pinecone, but requires engineering capacity to operate.

**Effort estimate:** 2-3 weeks (deployment + integration).

**Impact:** MEDIUM. Only if pgvector becomes a bottleneck.

**References:**
- [Qdrant GitHub](https://github.com/qdrant/qdrant)
- [Best Vector Databases for RAG 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/vector-databases-embeddings/best-vector-databases-for-rag-complete-2025-comparison-guide)

---

### Recommendation for Vector Database

**Use pgvector.** We already run PostgreSQL with PostGIS. Adding pgvector is a one-line extension install. Only consider Qdrant or Pinecone if vector corpus exceeds 1M+ documents (unlikely for regulatory documents).

---

## 7. Brazilian Portuguese LLM Support

### Current State of PT-BR in LLMs

| Model | PT-BR Quality | Notes |
|-------|--------------|-------|
| Claude Opus 4.5 / Sonnet 4 | Excellent (92%+) | Best overall for complex Portuguese tasks |
| GPT-4o | Excellent (92%+) | Strong multilingual performance |
| Llama 3.x (70B+) | Good | Open-source, can fine-tune |
| Sabia-3 (Maritaca AI) | Excellent | Brazilian company, PT-BR native |
| TeenyTinyLlama | Moderate | First open-source PT-BR trained LLMs (Apache 2.0) |
| Tucano | Good | Neural text generation optimized for Portuguese |
| Canarim-7B | Good | PT-BR fine-tuned Llama 2 (Apache 2.0) |
| SQLCoder-7B | Unknown for PT-BR | English-trained; would need fine-tuning |

**Key findings:**
- Claude and GPT-4o achieve 92%+ accuracy on PT-BR sentiment analysis and text tasks
- For self-hosted: Llama 3 70B+ with Portuguese fine-tuning is the best open option
- Maritaca AI's Sabia-3 is a Brazilian-made LLM with native PT-BR training
- Embedding models: `multilingual-e5-large` handles Portuguese well for RAG

**Recommendation:** Use Claude (API) as primary LLM. Consider Sabia-3 for cost-sensitive Portuguese-specific tasks. Use `multilingual-e5-large` for embeddings.

**References:**
- [TeenyTinyLlama](https://github.com/Nkluge-correa/TeenyTinyLlama)
- [Tucano: Neural Text Generation for Portuguese](https://www.sciencedirect.com/science/article/pii/S2666389925001734)
- [Better Open Source LLMs for Portuguese (2026)](https://arxiv.org/html/2603.03543)
- [PT-BR Sentiment Analysis Benchmarks](https://journals-sol.sbc.org.br/index.php/jbcs/article/view/5793)

---

## 8. Frontend Chat Components

### 8a. Vercel AI SDK (RECOMMENDED)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/vercel/ai |
| **npm** | `ai`, `@ai-sdk/anthropic` |
| **License** | Apache 2.0 |
| **Maturity** | Production (v6.0) |

**What it does:** TypeScript toolkit for building AI-powered UIs in Next.js. Provides React hooks (`useChat`, `useCompletion`), streaming support via SSE, and unified API across LLM providers.

**Integration with our Next.js 14 frontend:**
```tsx
// app/chat/page.tsx
'use client';
import { useChat } from 'ai/react';

export default function TelecomChat() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',  // proxies to our FastAPI backend
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {messages.map(m => (
          <div key={m.id} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            {m.content}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange}
          placeholder="Pergunte sobre o mercado de telecom..." />
      </form>
    </div>
  );
}
```

**Backend route (FastAPI):**
```python
from fastapi.responses import StreamingResponse

@router.post("/api/chat")
async def chat(request: ChatRequest):
    async def stream():
        async for chunk in agent.astream(request.messages):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```

**Effort estimate:** 1-2 weeks for chat UI component with streaming.

**Impact:** HIGH. Provides the conversational interface for all AI features.

**References:**
- [Vercel AI SDK GitHub](https://github.com/vercel/ai)
- [AI SDK Anthropic Provider](https://ai-sdk.dev/docs/getting-started/nextjs-app-router)
- [Vercel Chatbot Template](https://github.com/vercel/chatbot)
- [Streaming AI in Next.js](https://blog.logrocket.com/nextjs-vercel-ai-sdk-streaming/)

---

## 9. Prioritized Roadmap

### Phase 1: Foundation (Weeks 1-4)
| Task | Tool | Effort | Impact |
|------|------|--------|--------|
| Install pgvector extension | pgvector | 1 day | Enables all RAG |
| Chat UI component | Vercel AI SDK | 1-2 weeks | User interface for AI |
| Text-to-SQL MVP | Vanna.ai | 2-3 weeks | "Ask anything" about telecom data |
| Narrative reports | Claude API | 1-2 weeks | Executive summaries |

**Deliverable:** Users can ask natural language questions about 12M+ records and get answers + narrative summaries.

### Phase 2: Intelligence (Weeks 5-10)
| Task | Tool | Effort | Impact |
|------|------|--------|--------|
| Claude Agent with tool use | Claude Agent SDK | 3-4 weeks | Multi-tool workflows |
| Regulatory RAG (Anatel + DOU) | pgvector + LangChain | 4-6 weeks | Compliance intelligence |
| WhatsApp bot MVP | WATI/Twilio + Claude | 4-6 weeks | Brazil market penetration |

**Deliverable:** Agent that orchestrates RF coverage, subscriber analysis, and compliance checks. WhatsApp access for ISP operators.

### Phase 3: Advanced (Weeks 11-16)
| Task | Tool | Effort | Impact |
|------|------|--------|--------|
| Multi-agent M&A due diligence | LangGraph + PostgreSQL | 4-6 weeks | Premium feature |
| Image-based infrastructure assessment | Claude Vision | 2-3 weeks | Field operations |
| Querido Diario municipal gazette RAG | pgvector + Querido Diario API | 2-3 weeks | Local regulatory intelligence |

**Deliverable:** Automated M&A target assessment. Photo-based tower inspection. Municipal regulation monitoring.

### Phase 4: Differentiation (Weeks 17-22)
| Task | Tool | Effort | Impact |
|------|------|--------|--------|
| Voice queries for field technicians | Whisper PT-BR + Agent | 4-6 weeks | Field operations |
| Multi-agent report generation | LlamaIndex + Claude | 3-4 weeks | Automated BI reports |
| Self-hosted fine-tuned SQLCoder | SQLCoder-7B + Ollama | 3-4 weeks | Cost reduction + privacy |

**Deliverable:** Hands-free voice interaction. Fully automated report generation. Reduced API costs.

---

## Cost Estimates

| Component | Monthly Cost (Est.) | Notes |
|-----------|-------------------|-------|
| Claude API (Sonnet 4) | $200-500 | Primary LLM for agents + reports |
| pgvector | $0 | Extension to existing PostgreSQL |
| Whisper API | $50-100 | Pay per audio minute |
| WhatsApp Business API | $50-200 | Message-based pricing |
| Vanna.ai (self-hosted) | $0 | MIT license |
| LangGraph | $0 | MIT license |
| Vercel AI SDK | $0 | Apache 2.0 license |
| **Total** | **$300-800/mo** | Excludes compute costs |

---

## Architecture Diagram

```
                    +-------------------+
                    |   Next.js 14 UI   |
                    |  (Vercel AI SDK)  |
                    |  Chat + Dashboard |
                    +--------+----------+
                             |
                    +--------v----------+
                    |    FastAPI 8010    |
                    |                   |
          +---------+   AI Router      +----------+
          |         |  /api/chat       |          |
          |         |  /api/ask        |          |
          |         |  /api/regulatory |          |
          |         +--------+---------+          |
          |                  |                    |
+---------v-----+  +---------v--------+  +--------v--------+
| Text-to-SQL   |  | Agent Engine     |  | RAG Engine      |
| (Vanna.ai)    |  | (Claude SDK /    |  | (LangChain +    |
|               |  |  LangGraph)      |  |  pgvector)      |
+-------+-------+  +--------+---------+  +--------+--------+
        |                    |                     |
        |           +--------v---------+           |
        |           | Tool Registry    |           |
        |           | - RF Coverage    |           |
        |           | - Fiber Route    |           |
        |           | - Subscriber DB  |           |
        |           | - Compliance     |           |
        |           +--------+---------+           |
        |                    |                     |
+-------v--------------------v---------------------v-------+
|                    PostgreSQL + PostGIS + pgvector         |
|  45+ tables | 12M+ records | embeddings | checkpoints     |
+------------------------------+----------------------------+
                               |
                    +----------v-----------+
                    | Rust RF Engine       |
                    | gRPC+TLS :50051     |
                    | SRTM 1,681 tiles    |
                    +----------------------+
```

---

## Key Decision Points

1. **LLM Provider:** Claude (Anthropic) as primary -- best Portuguese support, tool use, and vision. Consider Sabia-3 (Maritaca AI) for cost optimization on Portuguese-specific tasks.

2. **Vector Database:** pgvector first. Migrate to Qdrant only if vector corpus exceeds 1M documents.

3. **Agent Framework:** Claude Agent SDK for single-agent, LangGraph for multi-agent with PostgreSQL checkpointing.

4. **Text-to-SQL:** Vanna.ai for MVP, LangChain SQL Agent for complex queries, SQLCoder-7B for self-hosted fine-tuned accuracy.

5. **WhatsApp:** Critical for Brazil market. Regulatory path is now clear (Meta reversed ban in Jan 2026).

6. **Self-Hosted vs API:** Start with APIs (Claude, Whisper) for speed. Migrate to self-hosted (SQLCoder, Whisper PT-BR) for cost reduction once usage patterns are established.

---

*Research conducted 2026-03-11. All URLs and version numbers verified at time of writing.*
