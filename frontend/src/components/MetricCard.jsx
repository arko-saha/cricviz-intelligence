/**
 * Reusable metric card with contextual colour state.
 * Green  → above expected (xR > 1.2, xW < 0.05)
 * Amber  → at expected
 * Red    → below expected / high false shot rate
 */
export default function MetricCard({ label, value, state = 'amber', delta = null }) {
  return (
    <div className={`metric-card state-${state}`}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value state-${state}`}>{value}</div>
      {delta !== null && (
        <div className="metric-delta">{delta}</div>
      )}
    </div>
  );
}

/**
 * Determine colour state for a metric value.
 */
export function getMetricState(metricType, value) {
  switch (metricType) {
    case 'xR':
      if (value > 1.2) return 'green';
      if (value > 0.6) return 'amber';
      return 'red';
    case 'xW':
      if (value < 0.05) return 'green';
      if (value < 0.1) return 'amber';
      return 'red';
    case 'false_shot_pct':
      if (value < 15) return 'green';
      if (value < 30) return 'amber';
      return 'red';
    default:
      return 'amber';
  }
}
