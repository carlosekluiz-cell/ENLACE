export const SITE_NAME = 'Pulso Network';
export const SITE_DESCRIPTION = 'Plataforma de inteligência telecom para provedores de internet brasileiros.';
export const APP_URL = 'https://app.pulso.network';
export const API_URL = 'https://api.pulso.network';

export const NAV_LINKS = [
  { label: 'Mercado', href: '/mercado' },
  { label: 'Raio-X', href: '/raio-x' },
  { label: 'Mapa', href: '/mapa-brasil' },
  { label: 'Produto', href: '/produto' },
  { label: 'Dados', href: '/dados' },
  { label: 'Lista de Espera', href: '/precos' },
  { label: 'Blog', href: '/blog' },
  { label: 'Recursos', href: '/recursos' },
  { label: 'Sobre', href: '/sobre' },
] as const;

export const FOOTER_LINKS = {
  product: [
    { label: 'Mercado', href: '/mercado' },
    { label: 'Raio-X do Provedor', href: '/raio-x' },
    { label: 'Produto', href: '/produto' },
    { label: 'Dados', href: '/dados' },
    { label: 'Lista de Espera', href: '/precos' },
  ],
  company: [
    { label: 'Sobre', href: '/sobre' },
    { label: 'Blog', href: '/blog' },
    { label: 'Contato', href: '/contato' },
  ],
  recursos: [
    { label: 'Whitepaper', href: '/recursos/whitepaper' },
    { label: 'Calculadora de ROI', href: '/recursos/roi' },
    { label: 'Funcionalidades', href: '/recursos/funcionalidades' },
    { label: 'Confiança dos Dados', href: '/recursos/dados-confianca' },
  ],
  legal: [
    { label: 'Termos de Uso', href: '/termos' },
    { label: 'Privacidade', href: '/privacidade' },
  ],
};

export const BR_STATES = [
  { code: 'AC', name: 'Acre' }, { code: 'AL', name: 'Alagoas' },
  { code: 'AP', name: 'Amapá' }, { code: 'AM', name: 'Amazonas' },
  { code: 'BA', name: 'Bahia' }, { code: 'CE', name: 'Ceará' },
  { code: 'DF', name: 'Distrito Federal' }, { code: 'ES', name: 'Espírito Santo' },
  { code: 'GO', name: 'Goiás' }, { code: 'MA', name: 'Maranhão' },
  { code: 'MT', name: 'Mato Grosso' }, { code: 'MS', name: 'Mato Grosso do Sul' },
  { code: 'MG', name: 'Minas Gerais' }, { code: 'PA', name: 'Pará' },
  { code: 'PB', name: 'Paraíba' }, { code: 'PR', name: 'Paraná' },
  { code: 'PE', name: 'Pernambuco' }, { code: 'PI', name: 'Piauí' },
  { code: 'RJ', name: 'Rio de Janeiro' }, { code: 'RN', name: 'Rio Grande do Norte' },
  { code: 'RS', name: 'Rio Grande do Sul' }, { code: 'RO', name: 'Rondônia' },
  { code: 'RR', name: 'Roraima' }, { code: 'SC', name: 'Santa Catarina' },
  { code: 'SP', name: 'São Paulo' }, { code: 'SE', name: 'Sergipe' },
  { code: 'TO', name: 'Tocantins' },
] as const;
