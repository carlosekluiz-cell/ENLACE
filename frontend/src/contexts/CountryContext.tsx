'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface CountryConfig {
  countryCode: string;
  currency: string;
  currencyLocale: string;
  defaultLocale: string;
  regulatoryBody: string;
}

const COUNTRY_CONFIGS: Record<string, CountryConfig> = {
  BR: {
    countryCode: 'BR',
    currency: 'BRL',
    currencyLocale: 'pt-BR',
    defaultLocale: 'pt-BR',
    regulatoryBody: 'Anatel',
  },
  CO: {
    countryCode: 'CO',
    currency: 'COP',
    currencyLocale: 'es-CO',
    defaultLocale: 'es',
    regulatoryBody: 'CRC',
  },
};

export function getCountryCode(): string {
  if (typeof window === 'undefined') return 'BR';
  return localStorage.getItem('pulso_country') || 'BR';
}

const CountryContext = createContext<CountryConfig>(COUNTRY_CONFIGS.BR);

export function CountryProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<CountryConfig>(COUNTRY_CONFIGS.BR);

  useEffect(() => {
    const code = localStorage.getItem('pulso_country') || 'BR';
    if (COUNTRY_CONFIGS[code]) setConfig(COUNTRY_CONFIGS[code]);
  }, []);

  return (
    <CountryContext.Provider value={config}>
      {children}
    </CountryContext.Provider>
  );
}

export function useCountry(): CountryConfig {
  return useContext(CountryContext);
}
