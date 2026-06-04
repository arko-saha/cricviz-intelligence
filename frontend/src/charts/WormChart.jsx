import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import EmptyState from '../components/EmptyState';
import { exportChartAsPNG } from '../utils/chartExport';

const WicketDot = (props) => {
  const { cx, cy, payload, dataKey } = props;
  if (!cx || !cy) return null;
  
  const inningsId = dataKey.replace('_runs', '');
  const wicketsKey = `${inningsId}_wickets`;
  const wicketCount = payload[wicketsKey] || 0;
  
  // Different colors for innings 1 and 2 wickets
  const fillColor = inningsId === 'innings1' ? '#ef4444' : '#a855f7'; 
  
  if (wicketCount > 0) {
    return (
      <g>
        <circle cx={cx} cy={cy} r={6} fill={fillColor} stroke="var(--bg-elevated)" strokeWidth={2} />
        {wicketCount > 1 && (
          <text x={cx} y={cy} textAnchor="middle" dy=".3em" fill="#fff" fontSize={9} fontFamily="var(--font-mono)" fontWeight="bold">
            {wicketCount}
          </text>
        )}
      </g>
    );
  }
  return null;
};

export default function WormChart({ data = [], team1 = "Innings 1", team2 = "Innings 2" }) {
  // Handle single-innings or empty data
  if (!data || data.length === 0) {
    return <EmptyState icon="📈" title="No Worm Data" description="Worm chart data is not available for this match." />;
  }

  // Check if second innings has any data
  const hasInnings2 = data.some(d => d.innings2_runs > 0);

  return (
    <div className="card" id="worm-chart-container">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="card-title">Match Worm</span>
          <span className="badge badge-muted" style={{ marginLeft: 'var(--space-2)' }}>Over-by-over</span>
        </div>
        <button 
          className="btn btn-secondary text-xs" 
          onClick={() => exportChartAsPNG('#worm-chart-container', 'match_worm.png')}
          title="Download as PNG"
        >
          🖼️ Download PNG
        </button>
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
            formatter={(value, name, props) => {
              const inningsId = props.dataKey.replace('_runs', '');
              const wicketsKey = `${inningsId}_wickets`;
              const wickets = props.payload[wicketsKey] || 0;
              return [`${value} runs` + (wickets > 0 ? ` (${wickets} W)` : ''), name];
            }}
          />
          <Legend
            wrapperStyle={{ fontFamily: 'var(--font-sans)', fontSize: '13px' }}
          />
          <Line
            type="monotone"
            dataKey="innings1_runs"
            name={team1 || "Innings 1"}
            stroke="var(--accent-teal)"
            strokeWidth={2.5}
            dot={<WicketDot />}
            activeDot={{ r: 7, fill: 'var(--accent-teal)' }}
          />
          {hasInnings2 && (
            <Line
              type="monotone"
              dataKey="innings2_runs"
              name={team2 || "Innings 2"}
              stroke="var(--accent-amber)"
              strokeWidth={2.5}
              dot={<WicketDot />}
              activeDot={{ r: 7, fill: 'var(--accent-amber)' }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
