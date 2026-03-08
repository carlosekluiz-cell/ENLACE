'use client';

import { clsx } from 'clsx';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  change?: number;
  icon?: React.ReactNode;
  loading?: boolean;
  className?: string;
}

export default function StatsCard({
  title,
  value,
  subtitle,
  change,
  icon,
  loading,
  className,
}: StatsCardProps) {
  const trendIcon =
    change === undefined ? null : change > 0 ? (
      <TrendingUp size={14} />
    ) : change < 0 ? (
      <TrendingDown size={14} />
    ) : (
      <Minus size={14} />
    );

  const trendColor =
    change === undefined
      ? ''
      : change > 0
        ? 'text-green-400'
        : change < 0
          ? 'text-red-400'
          : 'text-slate-400';

  if (loading) {
    return (
      <div
        className={clsx('enlace-card animate-pulse', className)}
      >
        <div className="h-4 w-24 rounded bg-slate-700" />
        <div className="mt-3 h-8 w-32 rounded bg-slate-700" />
        <div className="mt-2 h-3 w-20 rounded bg-slate-700" />
      </div>
    );
  }

  return (
    <div className={clsx('enlace-card', className)}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-400">{title}</p>
        {icon && <span className="text-slate-500">{icon}</span>}
      </div>
      <p className="mt-2 text-2xl font-bold text-slate-100">
        {typeof value === 'number' ? value.toLocaleString('pt-BR') : value}
      </p>
      <div className="mt-1 flex items-center gap-2">
        {change !== undefined && (
          <span className={clsx('flex items-center gap-1 text-xs', trendColor)}>
            {trendIcon}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
        {subtitle && (
          <span className="text-xs text-slate-500">{subtitle}</span>
        )}
      </div>
    </div>
  );
}
