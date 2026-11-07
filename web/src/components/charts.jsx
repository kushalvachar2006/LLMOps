import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const axis = { stroke: 'var(--text-3)', fontSize: 12, tickLine: false, axisLine: { stroke: 'var(--border)' } }
const tip = {
  contentStyle: { background: 'var(--surface-3)', border: '1px solid var(--border-strong)', borderRadius: 8, color: 'var(--text)' },
  labelStyle: { color: 'var(--text-2)' }, cursor: { fill: 'var(--glow)' },
}
export const COLORS = ['var(--accent)', 'var(--accent-2)', 'var(--accent-3)', 'var(--warning)', 'var(--danger)', 'var(--info)']

export function BarSeries({ data, xKey, series, height = 240, stacked }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} {...axis} /><YAxis {...axis} allowDecimals={false} /><Tooltip {...tip} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.label || s.key} stackId={stacked ? 'a' : undefined}
          fill={s.color || COLORS[i % COLORS.length]} radius={stacked ? 0 : [4, 4, 0, 0]} />)}
      </BarChart>
    </ResponsiveContainer>
  )
}

export function LineSeries({ data, xKey, series, height = 240 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} {...axis} /><YAxis {...axis} /><Tooltip {...tip} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => <Line key={s.key} dataKey={s.key} name={s.label || s.key} type="monotone" strokeWidth={2.2}
          stroke={s.color || COLORS[i % COLORS.length]} dot={{ r: 3 }} connectNulls />)}
      </LineChart>
    </ResponsiveContainer>
  )
}
