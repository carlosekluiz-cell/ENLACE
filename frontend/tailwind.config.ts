import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        enlace: {
          primary: '#2563eb',
          secondary: '#7c3aed',
          accent: '#06b6d4',
          bg: '#0f172a',
          surface: '#1e293b',
          text: '#f8fafc',
        },
      },
    },
  },
  plugins: [],
};

export default config;
