import EmptyState from '../components/EmptyState';

const ZONES = ['YORKER', 'FULL', 'GOOD_LENGTH', 'SHORT', 'BOUNCER'];
const ZONE_Y = { YORKER: 280, FULL: 220, GOOD_LENGTH: 150, SHORT: 80, BOUNCER: 20 };

function xwToOpacity(xw) {
  // Map xW (0-0.2) to opacity (0.15-0.9)
  return Math.min(0.15 + (xw / 0.2) * 0.75, 0.9);
}

function xwToColor(xw) {
  // Low xW = teal (safe), High xW = red (dangerous)
  if (xw < 0.04) return `rgba(0, 229, 204, ${xwToOpacity(xw)})`;
  if (xw < 0.08) return `rgba(255, 184, 77, ${xwToOpacity(xw)})`;
  return `rgba(255, 77, 106, ${xwToOpacity(xw)})`;
}

export default function HeatmapGrid({ deliveries = [] }) {
  if (!deliveries || deliveries.length === 0) {
    return <EmptyState icon="🎯" title="No Pitch Data" description="Pitch zone data is not available for this match." />;
  }

  // Group deliveries by pitch zone
  const zoneData = {};
  for (const zone of ZONES) {
    const zoneDels = deliveries.filter(d => d.pitch_zone === zone);
    const avgXW = zoneDels.length
      ? zoneDels.reduce((sum, d) => sum + (d.xW || 0), 0) / zoneDels.length
      : 0;
    zoneData[zone] = { count: zoneDels.length, avgXW };
  }

  // Scatter points
  const points = deliveries
    .filter(d => ZONE_Y[d.pitch_zone] !== undefined)
    .map((d, i) => ({
      x: 40 + Math.random() * 170,
      y: ZONE_Y[d.pitch_zone] + (Math.random() - 0.5) * 30,
      xw: d.xW || 0,
      zone: d.pitch_zone,
      key: i,
    }));

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Pitch Map</span>
        <span className="badge badge-muted">xW Heatmap</span>
      </div>
      <div className="heatmap-container" style={{ display: 'flex', justifyContent: 'center' }}>
        <svg viewBox="0 0 250 320" width="250" height="320">
          {/* Pitch rectangle */}
          <rect x="30" y="5" width="190" height="310" rx="8"
            fill="var(--bg-elevated)" stroke="var(--border-default)" strokeWidth="1" />

          {/* Zone labels */}
          {ZONES.map(zone => (
            <g key={zone}>
              <line
                x1="30" y1={ZONE_Y[zone] + 15} x2="220" y2={ZONE_Y[zone] + 15}
                stroke="var(--border-subtle)" strokeDasharray="3 3"
              />
              <text x="125" y={ZONE_Y[zone] + 8}
                textAnchor="middle"
                fill="var(--text-muted)"
                fontSize="9"
                fontFamily="var(--font-mono)"
              >
                {zone.replace('_', ' ')}
              </text>
            </g>
          ))}

          {/* Delivery dots */}
          {points.map(p => (
            <circle
              key={p.key}
              cx={p.x}
              cy={p.y}
              r={4}
              fill={xwToColor(p.xw)}
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="0.5"
            >
              <title>{`${p.zone} | xW: ${p.xw.toFixed(3)}`}</title>
            </circle>
          ))}
        </svg>
      </div>
      <div style={{
        display: 'flex', justifyContent: 'center', gap: '1rem',
        padding: 'var(--space-3) 0', fontSize: 'var(--text-xs)', color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
      }}>
        <span>● <span style={{color:'var(--accent-teal)'}}>Low xW</span></span>
        <span>● <span style={{color:'var(--accent-amber)'}}>Med xW</span></span>
        <span>● <span style={{color:'var(--color-danger)'}}>High xW</span></span>
      </div>
    </div>
  );
}
