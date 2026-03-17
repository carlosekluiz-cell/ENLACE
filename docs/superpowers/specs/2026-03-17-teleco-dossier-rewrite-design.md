# Pulso x Teleco Final Dossier — Readability Rewrite

**Date:** 2026-03-17
**Source file:** `docs/pulso-teleco-final.py`
**Output:** `docs/Pulso_x_Teleco_Final.pdf`

## Context

The existing dossier was reviewed by an 80-year-old telecom specialist (user's father-in-law), who said it was "muito boa" but felt lost — "me sentisse perdido no meio de tantas siglas." The father-in-law will forward the document to the CEO of Teleco.

The document's purpose is an **overlap and synergy analysis** between Teleco and Pulso Network. A separate partnership proposal document will follow.

## Problem Diagnosis

The issue is **density**, not content:
- Developer jargon mixed with telecom terminology confuses the audience (telecom people, not developers)
- Non-telecom acronyms (PGFN, CEIS, QSA) appear without explanation
- Raw number dumps (783K, 261K, 463K) blur together without context
- The Rust section uses compiler theory instead of business language

The structure, visual design, and section order are all correct — the document is 90% there.

## Approach: Light Edit

Keep the exact same 8-section structure and WeasyPrint visual design. Edit paragraph by paragraph for readability. No structural changes.

## Changes by Section

Note: Section numbers below match the source file's numbering (01-08), not page numbers.

### Executive Summary (before Section 01)
- Replace "28 milhões de registros cruzados de 38+ fontes públicas" with a contextual statement about what the platform does (e.g., "plataforma que cruza automaticamente dados de dezenas de fontes públicas")
- Keep the 4%/40%/56% metrics — those are clear and self-explanatory
- Keep the table of contents as-is

### Section 01: Side-by-side comparison
- Clean up dense table cells. Example: replace "DCF automático, due diligence digital (783K vínculos, 261K dívidas, 463K reclamações)" with "Valuation automático e due diligence digital — cruzando dívidas fiscais, vínculos societários e reclamações de consumidores para milhares de provedores"
- Max 2 acronyms per sentence in body text

### Section 2: Joint capabilities (pages 3-4)
- Replace raw numbers in the four boxes with contextual statements
- Example: "783K vínculos, 261K dívidas, DCF, grafo" becomes "due diligence digital: dívidas fiscais, vínculos societários, valuation automático"

### Section 3: Teleco exclusives (page 5)
- No changes. Already clean and well-structured.

### Section 4: Pulso exclusives (pages 5-8)

**4.1 Motor RF:**
- Minor cleanup only. Drop "gRPC+TLS porta 50051" (dev detail)
- Keep the model table and engenheiro responsável callout

**4.2 Agente de Telemetria:**
- Drop dev details: "binário único", "buffer SQLite", "RFC 2866"
- Keep the business point: "roda dentro da rede do ISP (edge, não cloud)"
- Keep Calix comparison callout as-is
- SNMP/RouterOS/RADIUS/TR-069 table stays (telecom vocabulary)

**4.3 Plataforma de Inteligência:**
- Reframe as "tech that produces intelligence" — Pulso is a tech company, the intelligence is output of engineering, not a competing consulting practice
- Break the dense ID-systems paragraph (8 systems in one sentence) into a short bulleted list
- Replace raw cross-reference numbers with contextual descriptions. Example: "783K vínculos, 777 donos multi-ISP, 1.709 participações cruzadas" becomes "Grafo societário: identifica donos que controlam múltiplos provedores e participações cruzadas"

### Section 04b: SaaS para Provedores
Note: This is the second half of Section 04 in the source (reuses `<div class="num">04</div>`).
- Replace "4 bases legais LGPD" with "framework jurídico implementado conforme LGPD"
- Drop both occurrences of "audit log" (access levels table line 411 AND callout line 429)

### Section 05: Software sob Medida para Grandes Empresas
- The enterprise products table has ticket estimates (R$200K-3M) and stack descriptions — keep the tickets, simplify the stack column to business language (e.g., "agente + motor RF + dashboard" is fine, but drop any dev terms if present)
- No other changes needed — this section is already business-oriented

### Section 06: Rust
- Keep the business moat argument: "Python: 833 vCPUs. Rust: 1 servidor"
- Keep the green callout "Por que ninguém mais fez" (already business language)
- Drop entirely: "sem null pointers, sem data races, sem memory leaks"
- Drop the blue callout about "correção em tempo de compilação" — delete it, don't replace (the two cards + green callout still fill the section)

### Section 07: IA em Telecom
- Drop "pyod" (library name, dev detail)
- Rest stays as-is

### Section 08: LatAm
- No changes. Already written in business language.

### Conclusion
- Keep the 4%/40%/56% metrics — clear and self-explanatory
- In the Pulso card, replace "28.4M registros, 38+ fontes, 150+ APIs" with contextual version (e.g., "plataforma que cruza automaticamente dezenas de fontes públicas")
- Keep the Teleco card as-is (already business language)
- Keep the green integration callout as-is (already clean)

## Global Rules

1. **Keep all telecom acronyms** (ONT, PON, SNMP, OLT, BGP, PPPoE, etc.) — the audience knows these
2. **Explain non-telecom acronyms on first use:**
   - PGFN (Procuradoria-Geral da Fazenda Nacional — dívidas fiscais)
   - CEIS/CNEP (cadastros de sanções do governo federal)
   - QSA (Quadro de Sócios e Administradores — Receita Federal)
   - LGPD (Lei Geral de Proteção de Dados)
   - DCF (Fluxo de Caixa Descontado — método de valuation)
   - HHI (Índice Herfindahl-Hirschman — concentração de mercado)
   - WACC (custo médio ponderado de capital)
   - NDA, CREA, ANM — assumed known by the audience (legal/engineering/mining terms common in Brazilian business)
3. **Drop developer jargon:** gRPC, TLS, SQLite, RFC numbers, null pointers, data races, memory leaks, compile-time, pyod, audit log, binário
4. **Numbers with context:** Don't dump raw counts. Say what the number means for the reader. Summary statistics like "38+ fontes" are OK in tables/metrics boxes but should have context in body text.
5. **Max 2 technical acronyms per sentence** in body text. Tables are exempt but should still be scannable.
6. **Keep the visual design** — all CSS, section headers, metrics boxes, cards, callouts unchanged
7. **Framing:** Pulso = tech company whose technology produces intelligence. Teleco = consulting/editorial/relationships. They don't compete; they complement.
8. **Maintain HTML entity encoding style** — the source uses `&eacute;`, `&atilde;` etc. Keep this convention for consistency.

## Implementation

Edit `docs/pulso-teleco-final.py` inline — modify the HTML string content only. No CSS changes. No structural changes. Regenerate the PDF after editing.

## Success Criteria

- An 80-year-old telecom specialist can read it without feeling lost
- A telecom CEO gets the overlap/synergy argument in one sitting
- All technical substance is preserved — nothing dumbed down, just clarified
- Rust moat argument lands without requiring dev knowledge
- **Verifiable:** Zero occurrences of banned developer terms (gRPC, TLS, SQLite, RFC, null pointer, data race, memory leak, pyod, compile-time, binário) in body text after edit
