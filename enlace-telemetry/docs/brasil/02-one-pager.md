# Enlace — enxergue sua rede de fibra antes do seu cliente

**Um agente de telemetria somente leitura para provedores PON/FTTH.** Pela Pulso Technologies Limited.
enlace.network · hello@enlace.network

---

## O problema

Suas OLTs já sabem quando o sinal de um cliente está morrendo, quando um ramal PON ficou no escuro
e quando uma conexão parou de trafegar sem avisar. Esse dado fica preso, separado por fabricante,
sem ninguém ler. Então a operação segue **reativa**: o cliente liga primeiro, o chamado abre, o
técnico se desloca — muitas vezes para não encontrar defeito algum na casa do assinante.

Operação reativa custa duas vezes: nas **visitas técnicas** (combustível, hora de técnico, veículo)
e no **churn** de clientes que ficaram sem serviço antes de você saber que havia problema. Para o
provedor regional sem NOC, com um ou dois técnicos correndo atrás do prejuízo, é o gargalo do dia a dia.

## O que o Enlace faz

O Enlace é um **agente único e leve** que lê a telemetria dos equipamentos que você já opera,
normaliza os dados entre fabricantes e roda detecção contínua na borda:

| Módulo | O que ele identifica |
|---|---|
| **Detecção de falha** | Eventos de massa offline, classificados como *rompimento de fibra* vs *falta de energia* usando sinais de *dying-gasp* |
| **Predição de sinal** | Degradação óptica por ONU, com estimativa de tempo até a falha |
| **Score de churn** | Assinantes em tendência de queda de sinal/uso, antes de cancelar |
| **Detecção de "fantasma"** | Conexões "up" que não trafegam nada de real |
| **Planejamento de capacidade** | Portas de splitter PON caminhando para a saturação |
| **Diagnóstico ao vivo** | Visão de saúde com código de cores que o atendimento lê sem engenheiro de rede |

São **17 módulos de detecção** ao todo. Os achados saem como **chamados priorizados** e um **score
de saúde** executivo, prontos para entrar no fluxo que você já usa.

## WhatsApp: o canal da sua operação

Quando um achado vira chamado, o Enlace gera um **disparo one-tap para o WhatsApp do técnico** —
link direto com o resumo do problema e a localização. É onde a operação do provedor brasileiro já
acontece; não trocamos a ferramenta do seu time. *(WhatsApp Business API está no roadmap; hoje é
compartilhamento one-tap / deep-link.)*

## Feito para merecer confiança

- **Somente leitura.** O Enlace nunca envia comando de escrita ao seu equipamento.
- **Suas credenciais nunca saem da sua rede.** O que sai são achados estruturados por ONU e métricas
  ópticas — nunca conteúdo de tráfego nem PII de assinante. Saída self-hosted mantém tudo na sua
  infraestrutura.
- **Aderente à LGPD.** Sem conteúdo, sem PII, dado local: o Enlace se encaixa na sua política de
  tratamento de dados sem criar novo ponto de exposição.
- **Verificável.** Mostramos ao seu técnico exatamente o que o agente faz — somente leitura, padrões
  abertos (SNMP/NETCONF) — para ele mesmo aprovar. Sem caixa-preta, sem *lock-in*.
- **Agnóstico de fabricante.** **Intelbras, Parks, Datacom, FiberHome, Huawei, ZTE, VSOL, BDCOM** e
  outros — um agente, um modelo de dados, sem ferramenta por fabricante. Numa rede mista, você para
  de pular entre consoles de gerência.

## Onde estamos

- Validado contra um *benchmark* de padrões reais de incidente — rompimentos, pré-falha de emenda e
  de SFP, reflectância, *flapping*, degradação correlacionada ao clima, esgotamento de capacidade e
  churn — todos detectados de ponta a ponta.
- **528 testes automatizados** passando; um único binário estático de **8,7 MB** (Rust/musl, sem
  dependências); auditoria de um CSV em **menos de 100 ms** de ponta a ponta.
- Nascido no Brasil, para a realidade do provedor regional.

## O valor

Provedores em operação proativa relatam, no setor, **visitas técnicas em queda de 30–50%**, **MTTR
em queda de ~40%** e **ruído de alarme em queda de 60–70%**. São **faixas de referência do setor —
não os seus números.** O piloto coloca *o seu* custo de deslocamento, churn, ARPU e volume de alarme
contra essas faixas, de forma conservadora. (Referência de ARPU residencial no Brasil: tipicamente
**R$ 80–120/mês** — um deslocamento evitado costuma valer mais que várias mensalidades.)

## O piloto — gratuito para parceiros de lançamento

Estamos convidando um pequeno número de provedores a validar o Enlace na própria rede.

1. **Envie um CSV.** Exporte ~1 mês de telemetria óptica de uma OLT (ou envie em enlace.network/upload).
   Sem instalação; **nada toca a sua rede**.
2. **Mostramos o que tem nele.** Em até 24 horas: as falhas, os clientes em risco, os fantasmas e os
   pontos quentes de capacidade que o Enlace encontrou naquela janela.
3. **Suba ao vivo se for útil.** Rode o agente contra uma OLT ao vivo, **somente leitura**, durante o
   piloto — **gratuito**, com condição preferencial reservada aos parceiros de lançamento quando
   passarmos ao modelo pago.

> **O pedido:** um export de CSV, ou uma conversa de 15 minutos. Só isso.

---

*Enlace é um produto da Pulso Technologies Limited — registrada na Inglaterra e País de Gales,
company no. 17151141. hello@enlace.network · enlace.network*
