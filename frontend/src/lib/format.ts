/**
 * Shared formatting utilities — null-safe, pt-BR locale.
 * Single source of truth; replaces per-page local formatters.
 */

export function formatBRL(value: number | undefined | null): string {
  if (value == null) return 'R$ --';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function formatNumber(value: number | undefined | null): string {
  if (value == null) return '--';
  return value.toLocaleString('pt-BR');
}

export function formatCompact(value: number | undefined | null): string {
  if (value == null) return '--';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString('pt-BR');
}

export function formatPct(
  value: number | undefined | null,
  decimals = 1,
): string {
  if (value == null) return '--%';
  return `${value.toFixed(decimals)}%`;
}

export function formatDecimal(
  value: number | undefined | null,
  decimals = 1,
): string {
  if (value == null) return '--';
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
