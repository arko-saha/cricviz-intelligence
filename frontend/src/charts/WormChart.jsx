import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import EmptyState from '../components/EmptyState';

export default function WormChart({ data = [] }) {
  // Handle single-innings or empty data
  if (!data || data.length === 0) {
    return <EmptyState icon="📈" title="No Worm Data" description="Worm chart data is not available for this match." />;
  }

  // Check if second innings has any data
  const hasInnings2 = data.some(d => d.innings2_runs > 0);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Match Worm</span>
        <span className="badge badge-muted">Over-by-over</span>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis
            dataKey="over"
            stroke="var(--text-muted)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
            label={{ value: 'Over', position: 'insideBottom', offset: -5, fill: 'var(--text-muted)' }}
          />
          <YAxis
            stroke="var(--text-muted)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
            label={{ value: 'Runs', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)' }}
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
          <Legend
            wrapperStyle={{ fontFamily: 'var(--font-sans)', fontSize: '13px' }}
          />
          <Line
            type="monotone"
            dataKey="innings1_runs"
            name="Innings 1"
            stroke="var(--accent-teal)"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: 'var(--accent-teal)' }}
          />
          {hasInnings2 && (
            <Line
              type="monotone"
              dataKey="innings2_runs"
              name="Innings 2"
              stroke="var(--accent-amber)"
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5, fill: 'var(--accent-amber)' }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
