'use client';

import { useMemo } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

interface TrendChartProps {
  data: Array<{ period: string; value: number; forecast?: boolean }>;
  label?: string;
  color?: string;
  height?: number;
  formatValue?: (v: number) => string;
}

export default function TrendChart({ data, label, color = '#0f766e', height = 200, formatValue }: TrendChartProps) {
  // Split actual vs forecast data for different line styles
  const { actualData, forecastData } = useMemo(() => {
    const actual = data.filter(d => !d.forecast);
    const forecast = data.filter(d => d.forecast);
    // Connect forecast to last actual point
    if (actual.length && forecast.length) {
      forecast.unshift(actual[actual.length - 1]);
    }
    return { actualData: actual, forecastData: forecast };
  }, [data]);

  return (
    <div>
      {label && (
        <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>{label}</h4>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} tickFormatter={formatValue} />
          <Tooltip
            contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: 'var(--text-primary)' }}
            formatter={(value: any) => [formatValue ? formatValue(Number(value)) : Number(value).toLocaleString('pt-BR'), label || 'Valor']}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
