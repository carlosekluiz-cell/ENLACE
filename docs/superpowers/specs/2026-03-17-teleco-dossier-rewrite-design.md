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

### Section 1: Side-by-side comparison (pages 2-3)
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

### Section 5: SaaS para Provedores (pages 8-9)
- Replace "4 bases legais LGPD" with "framework jurídico implementado conforme LGPD"
- Drop "audit log" from access levels table (dev detail)

### Section 6: Rust (page 10)
- Keep the business moat argument: "Python: 833 vCPUs. Rust: 1 servidor"
- Keep the green callout "Por que ninguém mais fez" (already business language)
- Drop entirely: "sem null pointers, sem data races, sem memory leaks"
- Drop the blue callout about "correção em tempo de compilação"

### Section 7: IA em Telecom (page 11)
- Drop "pyod" (library name, dev detail)
- Rest stays as-is

### Section 8: LatAm (pages 11-12)
- No changes. Already written in business language.

### Conclusion
- Replace raw metrics numbers with contextual versions consistent with the rest of the document

## Global Rules

1. **Keep all telecom acronyms** (ONT, PON, SNMP, OLT, BGP, PPPoE, etc.) — the audience knows these
2. **Explain non-telecom acronyms on first use:**
   - PGFN (Procuradoria-Geral da Fazenda Nacional — dívidas fiscais)
   - CEIS/CNEP (cadastros de sanções do governo federal)
   - QSA (Quadro de Sócios e Administradores — Receita Federal)
   - LGPD (Lei Geral de Proteção de Dados)
3. **Drop developer jargon:** gRPC, TLS, SQLite, RFC numbers, null pointers, data races, memory leaks, compile-time, pyod, audit log, binário
4. **Numbers with context:** Don't dump raw counts. Say what the number means for the reader.
5. **Max 2 technical acronyms per sentence** in body text (tables can be denser)
6. **Keep the visual design** — all CSS, section headers, metrics boxes, cards, callouts unchanged
7. **Framing:** Pulso = tech company whose technology produces intelligence. Teleco = consulting/editorial/relationships. They don't compete; they complement.

## Implementation

Edit `docs/pulso-teleco-final.py` inline — modify the HTML string content only. No CSS changes. No structural changes. Regenerate the PDF after editing.

## Success Criteria

- An 80-year-old telecom specialist can read it without feeling lost
- A telecom CEO gets the overlap/synergy argument in one sitting
- All technical substance is preserved — nothing dumbed down, just clarified
- Rust moat argument lands without requiring dev knowledge
