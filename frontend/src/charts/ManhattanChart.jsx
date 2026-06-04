import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LabelList } from 'recharts';
import EmptyState from '../components/EmptyState';
import { exportChartAsPNG } from '../utils/chartExport';

const makeWicketMarker = (chartData, inningsId) => (props) => {
  const { x, y, width, index } = props;
  if (x === undefined || y === undefined || index === undefined) return null;

  const row = chartData[index];
  if (!row) return null;

  const wicketCount = row[`${inningsId}_wickets`] || 0;
  if (wicketCount === 0) return null;

  const fillColor = inningsId === 'innings1' ? '#ef4444' : '#f59e0b';
  const radius = 5;
  const spacing = 14;
  const startY = y - 8;

  return (
    <g>
      {Array.from({ length: wicketCount }, (_, i) => (
        <circle
          key={i}
          cx={x + width / 2}
          cy={startY - i * spacing}
          r={radius}
          fill={fillColor}
          stroke="#ffffff"
          strokeWidth={1.5}
        >
          <title>{`Over ${row.over} — ${wicketCount} wicket(s) in this over`}</title>
        </circle>
      ))}
    </g>
  );
};

export default function ManhattanChart({ data = [], team1 = "Innings 1", team2 = "Innings 2" }) {
  if (!data || data.length === 0) {
    return <EmptyState icon="📊" title="No Manhattan Data" description="Manhattan chart data is not available for this match." />;
  }

  if (data.length > 0) {
    const sample = data[0];
    if (sample.innings1_wickets === undefined) {
      console.warn(
        '[ManhattanChart] innings1_wickets missing from data. ' +
        'Wicket circles will not render. Check the data ' +
        'transformation in MatchPage or useMatchData.'
      );
    }
  }

  const hasInnings2 = data.some(d => d.innings2_marginal_runs > 0);

  const WicketMarkerInnings1 = useMemo(() => makeWicketMarker(data, 'innings1'), [data]);
  const WicketMarkerInnings2 = useMemo(() => makeWicketMarker(data, 'innings2'), [data]);

  return (
    <div className="card" id="manhattan-chart-container">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="card-title">Manhattan Chart</span>
          <span className="badge badge-muted" style={{ marginLeft: 'var(--space-2)' }}>Runs per over</span>
        </div>
        <button 
          className="btn btn-secondary text-xs" 
          onClick={() => exportChartAsPNG('#manhattan-chart-container', 'manhattan_chart.png')}
          title="Download as PNG"
        >
          🖼️ Download PNG
        </button>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
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
              const inningsId = props.dataKey.replace('_marginal_runs', '');
              const wicketsKey = `${inningsId}_wickets`;
              const wickets = props.payload[wicketsKey] || 0;
              return [`${value} runs` + (wickets > 0 ? ` (${wickets} W)` : ''), name];
            }}
          />
          <Legend
            wrapperStyle={{ fontFamily: 'var(--font-sans)', fontSize: '13px' }}
          />
          <Bar
            dataKey="innings1_marginal_runs"
            name={team1 || "Innings 1"}
            fill="var(--accent-teal)"
            radius={[2, 2, 0, 0]}
          >
            <LabelList dataKey="innings1_marginal_runs" content={WicketMarkerInnings1} />
          </Bar>
          {hasInnings2 && (
            <Bar
              dataKey="innings2_marginal_runs"
              name={team2 || "Innings 2"}
              fill="var(--accent-amber)"
              radius={[2, 2, 0, 0]}
            >
               <LabelList dataKey="innings2_marginal_runs" content={WicketMarkerInnings2} />
            </Bar>
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
