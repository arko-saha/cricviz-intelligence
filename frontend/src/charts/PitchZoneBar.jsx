import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import EmptyState from '../components/EmptyState';

export default function PitchZoneBar({ distribution = [] }) {
  if (!distribution || distribution.length === 0) {
    return <EmptyState icon="📊" title="No Pitch Zone Data" description="Pitch zone distribution is not available." />;
  }

  const data = distribution
    .filter(d => d.count > 0)
    .map(d => ({ name: d.zone.replace('_', ' '), count: d.count }));

  if (data.length === 0) {
    return <EmptyState icon="📊" title="No Data" description="No pitch zone data to display." />;
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Pitch Zones Faced</span>
        <span className="badge badge-muted">Frequency</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis
            dataKey="name"
            stroke="var(--text-muted)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
          />
          <YAxis
            stroke="var(--text-muted)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
            }}
          />
          <Bar
            dataKey="count"
            fill="var(--accent-teal)"
            radius={[4, 4, 0, 0]}
            maxBarSize={50}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
