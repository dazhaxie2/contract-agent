import React from 'react';
import { Empty } from 'antd';

export interface SimpleChartPoint {
  label: string;
  value: number;
  group?: string;
}

function finiteValues(data: SimpleChartPoint[]) {
  return data.map((item) => (Number.isFinite(item.value) ? item.value : 0));
}

function formatValue(value: number) {
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

export const SimpleLineChart: React.FC<{ data: SimpleChartPoint[]; height?: number }> = ({ data, height = 220 }) => {
  if (!data.length) {
    return <Empty description="暂无趋势样本" />;
  }

  const width = 640;
  const padding = { left: 44, right: 16, top: 18, bottom: 34 };
  const values = finiteValues(data);
  const min = Math.min(0, ...values);
  const max = Math.max(1, ...values);
  const span = max - min || 1;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const points = data.map((item, index) => {
    const x = padding.left + (data.length === 1 ? innerWidth : (index / (data.length - 1)) * innerWidth);
    const y = padding.top + (1 - ((item.value - min) / span)) * innerHeight;
    return { ...item, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="趋势图">
      <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#d9d9d9" />
      <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#d9d9d9" />
      <text x={8} y={padding.top + 4} fontSize={11} fill="#8c8c8c">
        {formatValue(max)}
      </text>
      <text x={8} y={height - padding.bottom} fontSize={11} fill="#8c8c8c">
        {formatValue(min)}
      </text>
      <path d={path} fill="none" stroke="#1677ff" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      {points.map((point) => (
        <g key={`${point.label}-${point.x}`}>
          <circle cx={point.x} cy={point.y} r={3} fill="#1677ff" />
          <title>{`${point.label}: ${formatValue(point.value)}`}</title>
        </g>
      ))}
      {points.length ? (
        <>
          <text x={padding.left} y={height - 10} fontSize={11} fill="#8c8c8c">
            {points[0].label}
          </text>
          <text x={width - padding.right} y={height - 10} fontSize={11} fill="#8c8c8c" textAnchor="end">
            {points[points.length - 1].label}
          </text>
        </>
      ) : null}
    </svg>
  );
};

export const SimpleBarChart: React.FC<{ data: SimpleChartPoint[]; height?: number }> = ({ data, height = 260 }) => {
  if (!data.length) {
    return <Empty description="暂无对比样本" />;
  }

  const width = 640;
  const padding = { left: 44, right: 16, top: 18, bottom: 58 };
  const values = finiteValues(data);
  const max = Math.max(1, ...values);
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const slot = innerWidth / data.length;
  const barWidth = Math.max(12, Math.min(46, slot * 0.58));
  const palette = ['#1677ff', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96'];

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="柱状图">
      <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#d9d9d9" />
      <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#d9d9d9" />
      <text x={8} y={padding.top + 4} fontSize={11} fill="#8c8c8c">
        {formatValue(max)}
      </text>
      {data.map((item, index) => {
        const value = Number.isFinite(item.value) ? item.value : 0;
        const barHeight = Math.max(1, (value / max) * innerHeight);
        const x = padding.left + index * slot + (slot - barWidth) / 2;
        const y = height - padding.bottom - barHeight;
        const label = item.group ? `${item.label} / ${item.group}` : item.label;
        return (
          <g key={`${label}-${index}`}>
            <rect x={x} y={y} width={barWidth} height={barHeight} rx={4} fill={palette[index % palette.length]} />
            <text x={x + barWidth / 2} y={Math.max(12, y - 6)} fontSize={11} fill="#595959" textAnchor="middle">
              {formatValue(value)}
            </text>
            <text x={x + barWidth / 2} y={height - 38} fontSize={10} fill="#8c8c8c" textAnchor="middle">
              {item.label.slice(0, 8)}
            </text>
            {item.group ? (
              <text x={x + barWidth / 2} y={height - 20} fontSize={10} fill="#8c8c8c" textAnchor="middle">
                {item.group.slice(0, 8)}
              </text>
            ) : null}
            <title>{`${label}: ${formatValue(value)}`}</title>
          </g>
        );
      })}
    </svg>
  );
};
