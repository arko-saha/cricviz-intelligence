import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import EmptyState from '../components/EmptyState';

const COLORS = {
  ATTACKING: '#00e5cc',
  ROTATING: '#ffb84d',
  DEFENSIVE: '#4d8bff',
  UNKNOWN: '#5a6380',
};

export default function ShotIntentDonut({ distribution = [] }) {
  // Handle empty or all-UNKNOWN data
  if (!distribution || distribution.length === 0) {
    return <EmptyState icon="🍩" title="No Shot Data" description="Shot intent distribution is not available." />;
  }

  // Filter out zero-count entries
  const data = distribution
    .filter(d => d.count > 0)
    .map(d => ({ name: d.intent, value: d.count }));

  // If all shots are UNKNOWN, show a meaningful message instead of empty chart
  if (data.length === 0 || (data.length === 1 && data[0].name === 'UNKNOWN')) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Shot Intent</span>
        </div>
        <EmptyState icon="🍩" title="All Unknown" description="All deliveries have unknown shot intent — commentary data needed for classification." />
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Shot Intent</span>
        <span className="badge badge-muted">Distribution</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={3}
            dataKey="value"
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={COLORS[entry.name] || COLORS.UNKNOWN} />
            ))}
          </Pie>
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
          <Legend
            formatter={(value) => <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
