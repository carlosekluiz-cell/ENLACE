# Enlace — proposta de piloto para provedores regionais
### Inteligência de telemetria óptica PON, proativa e sem risco
*Pulso Technologies Limited · enlace.network · hello@enlace.network*

---

## Para quem é isto

Para o provedor regional que cresceu rápido, opera sem NOC e sustenta a rede com um ou
dois técnicos sobrecarregados. A operação é **reativa**: o cliente liga primeiro, abre-se
o chamado e sai a visita técnica — muitas vezes para descobrir que não há defeito nenhum
na casa do assinante. Cada deslocamento à toa custa combustível, hora de técnico e a
paciência de um cliente que já ficou sem serviço antes de você saber que havia problema.

A telemetria que evitaria essa corrida já existe. Suas OLTs medem a potência óptica de cada
ONU a cada poucos minutos — mas o dado fica preso, separado por fabricante, e quase nunca é
lido de forma proativa. Emendas absorvem umidade por semanas antes de o cliente reclamar;
uma única ONU defeituosa pode derrubar uma árvore PON inteira de 32 a 128 assinantes; SFPs
degradam de forma previsível antes de falhar.

## O que o Enlace faz

O Enlace é um **agente único e leve** que lê a telemetria dos equipamentos que você já opera,
normaliza os dados entre fabricantes e roda detecção contínua na borda — **fecha o ciclo**:
detectar → analisar → localizar → abrir chamado → notificar → confirmar.

| Módulo | O que ele identifica |
|---|---|
| **Detecção de falha** | Eventos de massa offline, classificados como *rompimento de fibra* vs *falta de energia* usando sinais de *dying-gasp* |
| **Predição de sinal** | Degradação óptica por ONU, com estimativa de tempo até a falha |
| **Score de churn** | Assinantes em tendência de queda de sinal/uso, antes que peçam cancelamento |
| **Detecção de "fantasma"** | Conexões que estão "up" mas não trafegam nada de real |
| **Planejamento de capacidade** | Portas de splitter PON caminhando para a saturação |
| **Diagnóstico ao vivo** | Uma visão de saúde com código de cores que o atendimento lê sem precisar de engenheiro de rede |

São **17 módulos de detecção** ao todo — incluindo classificação de rompimento, localização
de falha, ONU rogue/reflectância, predição de churn, clientes fantasma, capacidade de splitter,
degradação correlacionada ao clima, saúde de SFP e orçamento óptico. Cada achado vira uma **ação
priorizada, localizada e pronta para virar chamado**. Para degradações lentas, o agente abre um
**chamado de manutenção programada antes de o cliente ser afetado.**

## Por que o Enlace, especificamente

- **Agnóstico de fabricante — de verdade, no mercado brasileiro.** Um agente, um único modelo de
  dados, sem ferramenta separada por fabricante. Suporte às OLTs mais comuns nos provedores do
  Brasil: **Intelbras, Parks, Datacom, FiberHome, Huawei, ZTE, VSOL e BDCOM.** Se sua rede é
  mista — quase toda rede regional é — você deixa de pular entre três ou quatro consoles de
  gerência para ler o mesmo dado.
- **Leve e sem dependência.** Um único binário estático de **8,7 MB** (Rust/musl, sem runtime,
  sem dependência externa). Roda numa VM modesta, no seu próprio servidor. Nada de OSS pesado,
  nada de appliance.
- **WhatsApp é o canal.** Quando um achado vira chamado, o Enlace gera um **disparo one-tap para
  o WhatsApp do técnico** — link direto com o resumo do problema e a localização. É o canal onde
  sua operação já vive, sem trocar a ferramenta que o time usa. *(Integração via WhatsApp Business
  API está no roadmap; hoje é compartilhamento one-tap / deep-link.)*
- **Somente leitura.** O agente **nunca** envia comando de escrita ao equipamento.

## Confiança em primeiro lugar

- **Somente leitura, por design.** Apenas métodos de leitura (SNMP GET, CLI show/display, NETCONF
  get, RADIUS passivo) — nunca set/write/reboot.
- **Suas credenciais nunca saem da sua rede.** O que sai é achado estruturado por ONU e métrica
  óptica — nunca conteúdo de tráfego nem dado pessoal de assinante. Com saída self-hosted, tudo
  fica na sua infraestrutura.
- **Aderente à LGPD.** Como não trafegamos conteúdo nem PII de assinante e o dado permanece local,
  o Enlace se encaixa na sua política de tratamento de dados sem virar mais um ponto de exposição.
- **Verificável.** Mostramos ao seu técnico exatamente o que o agente faz — somente leitura,
  padrões abertos (SNMP/NETCONF) — para que ele mesmo aprove. Sem caixa-preta, sem *lock-in*.

## O valor

Provedores que adotam operação proativa relatam, no setor, **visitas técnicas em queda de 30–50%**,
**MTTR em queda de ~40%** e **ruído de alarme em queda de 60–70%**. **Não apresentamos esses números
como se fossem os seus** — são faixas de referência do setor. O piloto coloca *os seus* números —
custo de deslocamento, churn, ARPU, volume de alarme — contra essas faixas, de forma conservadora.

> Referência de ARPU residencial no Brasil hoje: tipicamente **R$ 80–120/mês**. Um único deslocamento
> evitado costuma custar mais do que a mensalidade de vários clientes — e ainda assim o custo real do
> reativo é o assinante que fica sem serviço antes de você saber. Faixas de mercado, não os seus
> resultados; o piloto mede os seus.

## O piloto — gratuito, três passos de risco zero

**Passo 1 — Auditoria offline.** Você exporta **~1 mês de telemetria óptica** (CSV) de uma OLT ou de
uma área que vem dando trabalho. Em **até 24 horas** devolvemos o que o Enlace encontrou: as falhas,
os clientes em risco, os fantasmas e os pontos quentes de capacidade daquela janela. **Nada toca a sua
rede** — é um arquivo, offline.

**Passo 2 — Revisão em conjunto.** Sentamos com o seu time e comparamos o que o Enlace achou contra os
**seus próprios números** de operação. Você confirma o que confere e mede a diferença que a antecipação
teria feito.

**Passo 3 — Agente ao vivo (opcional).** Se fizer sentido, subimos o agente contra uma OLT ao vivo,
**somente leitura**, no seu ritmo e dentro das suas ferramentas. Auditoria de um CSV roda em **menos de
100 ms** de ponta a ponta, então o retorno é imediato.

**Gratuito para parceiros de lançamento**, com condições preferenciais reservadas quando passarmos ao
modelo pago.

## Onde estamos

- Validado contra um *benchmark* de padrões reais de incidente — rompimentos, pré-falha de emenda e
  de SFP, reflectância, *flapping*, degradação correlacionada ao clima, esgotamento de capacidade e
  churn — todos detectados de ponta a ponta.
- **528 testes automatizados** passando; auditoria de um CSV em **menos de 100 ms**.
- Nascido no Brasil, um dos mercados de banda larga mais fragmentados do mundo: mais de 20 mil
  provedores regionais atendem a maior parte das ~54 milhões de linhas fixas do país, e a maioria roda
  a rede em planilha, com pouca análise de verdade. A lacuna nunca foi previsão — era **telemetria**.
  Construímos o motor que a preenche.

## O pedido

Uma conversa de 15 minutos e **um export de ~1 mês de telemetria** de uma área que vem te dando dor de
cabeça. Só isso. **hello@enlace.network.**

---
*Enlace é um produto da Pulso Technologies Limited — registrada na Inglaterra e País de Gales,
company no. 17151141. hello@enlace.network · enlace.network*
