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
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

const CHART_COLORS = [
  '#2563eb', // blue
  '#7c3aed', // purple
  '#06b6d4', // cyan
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#ec4899', // pink
  '#8b5cf6', // violet
];

interface ChartProps {
  data: Record<string, any>[];
  type?: 'bar' | 'line' | 'pie';
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
    <div className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-slate-300">{label}</p>
      {payload.map((entry: any, index: number) => (
        <p key={index} className="text-xs" style={{ color: entry.color }}>
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
      <div className={`enlace-card animate-pulse ${className || ''}`}>
        {title && <div className="mb-4 h-5 w-32 rounded bg-slate-700" />}
        <div style={{ height }} className="rounded bg-slate-700/50" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`enlace-card ${className || ''}`}>
        {title && (
          <h3 className="mb-4 text-sm font-medium text-slate-300">{title}</h3>
        )}
        <div
          style={{ height }}
          className="flex items-center justify-center text-sm text-slate-500"
        >
          No chart data available
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
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                axisLine={{ stroke: '#475569' }}
              />
              <YAxis
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                axisLine={{ stroke: '#475569' }}
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

      case 'pie':
        return (
          <ResponsiveContainer width="100%" height={height}>
            <PieChart>
              <Pie
                data={data}
                dataKey={yKey}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                outerRadius={height / 3}
                label={({ name, percent }: any) =>
                  `${name}: ${(percent * 100).toFixed(0)}%`
                }
                labelLine={{ stroke: '#64748b' }}
              >
                {data.map((_entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={CHART_COLORS[index % CHART_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ color: '#94a3b8', fontSize: 12 }}
              />
            </PieChart>
          </ResponsiveContainer>
        );

      default: // bar
        return (
          <ResponsiveContainer width="100%" height={height}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                axisLine={{ stroke: '#475569' }}
              />
              <YAxis
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                axisLine={{ stroke: '#475569' }}
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
    <div className={`enlace-card ${className || ''}`}>
      {title && (
        <h3 className="mb-4 text-sm font-medium text-slate-300">{title}</h3>
      )}
      {renderChart()}
    </div>
  );
}
