/**
 * Pulso i18n — lightweight client-side translation system.
 *
 * Uses inline message dictionaries to avoid JSON import path issues.
 * Supports pt-BR, en, and es locales with localStorage persistence.
 */

const ptBR: Record<string, Record<string, string>> = {
  common: {
    loading: 'Carregando...',
    error: 'Ocorreu um erro',
    save: 'Salvar',
    cancel: 'Cancelar',
    delete: 'Excluir',
    edit: 'Editar',
    create: 'Criar',
    search: 'Buscar',
    export: 'Exportar',
    back: 'Voltar',
    next: 'Próximo',
    previous: 'Anterior',
    close: 'Fechar',
    noData: 'Nenhum dado disponível',
    showing: 'Exibindo',
  },
  sidebar: {
    map: 'Mapa',
    expansion: 'Expansão',
    competition: 'Concorrência',
    design: 'Projeto RF',
    compliance: 'Conformidade',
    health: 'Saúde',
    rural: 'Rural',
    reports: 'Relatórios',
    admin: 'Admin',
    settings: 'Configurações',
    logout: 'Sair',
    platform: 'Pulso',
    subtitle: 'Inteligência Telecom Brasil',
  },
  pages: {
    dashboard: 'Painel',
    coverageMap: 'Mapa de Cobertura',
    expansion: 'Expansão',
    competition: 'Concorrência',
    rfDesign: 'Projeto de Cobertura RF',
    regulatoryCompliance: 'Conformidade Regulatória',
    networkHealth: 'Saúde da Rede',
    ruralConnectivity: 'Conectividade Rural',
    reportGenerator: 'Gerador de Relatórios',
    settings: 'Configurações',
    adminPanel: 'Painel Administrativo',
  },
};

const en: Record<string, Record<string, string>> = {
  common: {
    loading: 'Loading...',
    error: 'An error occurred',
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    edit: 'Edit',
    create: 'Create',
    search: 'Search',
    export: 'Export',
    back: 'Back',
    next: 'Next',
    previous: 'Previous',
    close: 'Close',
    noData: 'No data available',
    showing: 'Showing',
  },
  sidebar: {
    map: 'Map',
    expansion: 'Expansion',
    competition: 'Competition',
    design: 'RF Design',
    compliance: 'Compliance',
    health: 'Health',
    rural: 'Rural',
    reports: 'Reports',
    admin: 'Admin',
    settings: 'Settings',
    logout: 'Logout',
    platform: 'Pulso',
    subtitle: 'Telecom Intelligence Brazil',
  },
  pages: {
    dashboard: 'Dashboard',
    coverageMap: 'Coverage Map',
    expansion: 'Expansion',
    competition: 'Competition',
    rfDesign: 'RF Coverage Design',
    regulatoryCompliance: 'Regulatory Compliance',
    networkHealth: 'Network Health',
    ruralConnectivity: 'Rural Connectivity',
    reportGenerator: 'Report Generator',
    settings: 'Settings',
    adminPanel: 'Admin Panel',
  },
};

const es: Record<string, Record<string, string>> = {
  common: {
    loading: 'Cargando...',
    error: 'Ocurrió un error',
    save: 'Guardar',
    cancel: 'Cancelar',
    delete: 'Eliminar',
    edit: 'Editar',
    create: 'Crear',
    search: 'Buscar',
    export: 'Exportar',
    back: 'Volver',
    next: 'Siguiente',
    previous: 'Anterior',
    close: 'Cerrar',
    noData: 'No hay datos disponibles',
    showing: 'Mostrando',
  },
  sidebar: {
    map: 'Mapa',
    expansion: 'Expansión',
    competition: 'Competencia',
    design: 'Diseño RF',
    compliance: 'Cumplimiento',
    health: 'Salud',
    rural: 'Rural',
    reports: 'Reportes',
    admin: 'Admin',
    settings: 'Configuración',
    logout: 'Salir',
    platform: 'Pulso',
    subtitle: 'Inteligencia Telecom Colombia',
  },
  pages: {
    dashboard: 'Panel',
    coverageMap: 'Mapa de Cobertura',
    expansion: 'Expansión',
    competition: 'Competencia',
    rfDesign: 'Diseño de Cobertura RF',
    regulatoryCompliance: 'Cumplimiento Regulatorio',
    networkHealth: 'Salud de la Red',
    ruralConnectivity: 'Conectividad Rural',
    reportGenerator: 'Generador de Reportes',
    settings: 'Configuración',
    adminPanel: 'Panel Administrativo',
  },
};

const messages: Record<string, Record<string, Record<string, string>>> = {
  'pt-BR': ptBR,
  en,
  es,
  'es-CO': es,
};

export const SUPPORTED_LOCALES = ['pt-BR', 'en', 'es'] as const;

export function getLocale(): string {
  if (typeof window === 'undefined') return 'pt-BR';
  return localStorage.getItem('pulso_language') || 'pt-BR';
}

export function setLocale(locale: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('pulso_language', locale);
}

export function t(key: string): string {
  const locale = getLocale();
  const msgs = messages[locale] || messages['pt-BR'];

  const parts = key.split('.');
  if (parts.length === 2) {
    return msgs[parts[0]]?.[parts[1]] || key;
  }
  return key;
}
