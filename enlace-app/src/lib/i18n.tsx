"use client";

// ── Enlace i18n — lightweight client-side translations ──
// Same pattern as frontend/src/i18n.ts: inline dictionaries, localStorage
// persistence. English is the default and the fallback; pt-BR is a stub to
// be filled as views stabilize.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  localStorageGet,
  localStorageSet,
  subscribeLocalStorage,
} from "@/lib/clientStore";

export type Locale = "en" | "pt-BR";

const en: Record<string, string> = {
  "app.name": "Enlace Operations",
  "nav.noc": "NOC Board",
  "nav.onts": "ONT Fleet",
  "nav.field": "My Tickets",
  "nav.supervisor": "Ticket Queue",
  "nav.exec": "Executive KPIs",
  "nav.admin": "Admin",
  "nav.logout": "Log out",
  "common.loading": "Loading…",
  "common.noData": "No data available",
  "common.notMeasured": "not measured",
  "source.live": "LIVE — Elasticsearch feed",
  "source.audit": "AUDIT — uploaded CSV, real agent output",
  "source.demo": "DEMO — bundled sample, real agent output",
  "source.liveDown": "live feed not connected — showing audit data",
  "status.Online": "Online",
  "status.Offline": "Offline",
  "status.LowSignal": "Low signal",
  "status.Dying": "Dying",
  "status.PowerFail": "Power fail",
  "status.FiberCut": "Fiber cut",
  "status.Unknown": "Unknown",
};

// pt-BR — complete translation. Missing keys still fall back to English.
const ptBR: Record<string, string> = {
  "app.name": "Enlace Operações",
  "nav.noc": "Painel NOC",
  "nav.onts": "Frota ONT",
  "nav.field": "Meus Chamados",
  "nav.supervisor": "Fila de Chamados",
  "nav.exec": "KPIs Executivos",
  "nav.admin": "Administração",
  "nav.logout": "Sair",
  "common.loading": "Carregando…",
  "common.noData": "Nenhum dado disponível",
  "common.notMeasured": "não medido",
  "source.live": "AO VIVO — feed Elasticsearch",
  "source.audit": "AUDITORIA — CSV enviado, saída real do agente",
  "source.demo": "DEMO — amostra incluída, saída real do agente",
  "source.liveDown": "feed ao vivo não conectado — exibindo dados de auditoria",
  "status.Online": "Online",
  "status.Offline": "Offline",
  "status.LowSignal": "Sinal baixo",
  "status.Dying": "Em falha",
  "status.PowerFail": "Falha de energia",
  "status.FiberCut": "Fibra rompida",
  "status.Unknown": "Desconhecido",
};

const DICTIONARIES: Record<Locale, Record<string, string>> = {
  en,
  "pt-BR": ptBR,
};

const STORAGE_KEY = "enlace.locale";

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  // localStorage read through useSyncExternalStore: the server snapshot is
  // null (English), and the client value applies right after hydration.
  const stored = useSyncExternalStore(
    subscribeLocalStorage,
    () => localStorageGet(STORAGE_KEY),
    () => null,
  );
  const locale: Locale = stored === "pt-BR" ? "pt-BR" : "en";

  const setLocale = useCallback((l: Locale) => {
    localStorageSet(STORAGE_KEY, l);
  }, []);

  const t = useCallback(
    (key: string) => DICTIONARIES[locale][key] ?? en[key] ?? key,
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
