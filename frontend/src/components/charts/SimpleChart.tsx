'use client';

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const CHART_COLORS = [
  '#0f766e', // teal (accent)
  '#0d9488', // teal lighter
  '#059669', // success green
];

interface ChartProps {
  data: Record<string, any>[];
  type?: 'bar' | 'line';
  xKey?: string;
  yKey?: string;
  yKeys?: string[];
  title?: string;
  loading?: boolean;
  height?: number;
  className?: string;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;

  return (
    <div
      className="rounded-md border px-3 py-2 text-xs"
      style={{
        background: 'var(--bg-surface)',
        borderColor: 'var(--border)',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
      }}
    >
      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{label}</p>
      {payload.map((entry: any, index: number) => (
        <p key={index} style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString('pt-BR') : entry.value}
        </p>
      ))}
    </div>
  );
};

export default function SimpleChart({
  data,
  type = 'bar',
  xKey = 'name',
  yKey = 'value',
  yKeys,
  title,
  loading,
  height = 300,
  className,
}: ChartProps) {
  if (loading) {
    return (
      <div className={`pulso-card ${className || ''}`}>
        {title && <div className="mb-4 text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{title}</div>}
        <div style={{ height }} className="flex items-center justify-center">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando...</p>
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`pulso-card ${className || ''}`}>
        {title && (
          <h3 className="mb-4 text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
        )}
        <div
          style={{ height, color: 'var(--text-muted)' }}
          className="flex items-center justify-center text-sm"
        >
          Sem dados para o gráfico
        </div>
      </div>
    );
  }

  const keys = yKeys || [yKey];

  const renderChart = () => {
    switch (type) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={height}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                axisLine={{ stroke: 'var(--border-strong)' }}
              />
              <YAxis
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                axisLine={{ stroke: 'var(--border-strong)' }}
              />
              <Tooltip content={<CustomTooltip />} />
              {keys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      default: // bar
        return (
          <ResponsiveContainer width="100%" height={height}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                axisLine={{ stroke: 'var(--border-strong)' }}
              />
              <YAxis
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                axisLine={{ stroke: 'var(--border-strong)' }}
              />
              <Tooltip content={<CustomTooltip />} />
              {keys.map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={CHART_COLORS[i % CHART_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
    }
  };

  return (
    <div className={`pulso-card ${className || ''}`}>
      {title && (
        <h3 className="mb-4 text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
      )}
      {renderChart()}
    </div>
  );
}
