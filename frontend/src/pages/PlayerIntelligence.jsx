import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchPlayerProfile } from '../api/client';
import useUIStore from '../store/uiStore';
import MetricCard, { getMetricState } from '../components/MetricCard';
import ShotIntentDonut from '../charts/ShotIntentDonut';
import PitchZoneBar from '../charts/PitchZoneBar';
import EmptyState from '../components/EmptyState';

/**
 * PILLAR 2 — Player Intelligence
 *
 * Components:
 * - PlayerHeader (name, role, country, handedness)
 * - MetricRow (avg_xR, avg_xW, false_shot_pct, dominant_intent)
 * - ShotIntentDonut (PieChart)
 * - PitchZoneBar (BarChart)
 */
export default function PlayerIntelligence() {
  const { id: playerId } = useParams();
  const navigate = useNavigate();
  const setAIContext = useUIStore(s => s.setAIContext);

  const { data, isLoading, error } = useQuery({
    queryKey: ['player', playerId],
    queryFn: () => fetchPlayerProfile(playerId),
    enabled: !!playerId,
  });

  if (!playerId) {
    return (
      <EmptyState
        icon="👤"
        title="Select a Player"
        description="Click on a batter's name in the Delivery Explorer to view their profile."
      />
    );
  }

  if (isLoading) {
    return (
      <div className="fade-in">
        <div className="page-header">
          <h1 className="page-title">Player Intelligence</h1>
          <p className="page-subtitle">Loading player data...</p>
        </div>
        <div className="grid-4">
          {[1,2,3,4].map(i => <div key={i} className="skeleton skeleton-card" />)}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return <EmptyState icon="❌" title="Player Not Found" description="Could not load player profile." />;
  }

  // Set AI context
  setTimeout(() => setAIContext(data, 'player'), 0);

  const p = data.player;
  const initials = p.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 'var(--space-4)' }}>
        <button className="btn btn-secondary text-sm" onClick={() => navigate(-1)}>
          ← Back
        </button>
      </div>

      {/* Player Header */}
      <div className="player-header">
        <div className="player-avatar">{initials}</div>
        <div className="player-info">
          <h1>{p.name}</h1>
          <div className="player-info-meta">
            {p.country && <span className="badge badge-muted">{p.country}</span>}
            {p.handedness && <span className="badge badge-muted">{p.handedness}</span>}
            {p.bowling_style && <span className="badge badge-muted">{p.bowling_style}</span>}
            <span className="badge badge-teal">{data.total_deliveries_faced} balls faced</span>
          </div>
        </div>
      </div>

      {/* Metric Row */}
      <div className="grid-4" style={{ marginBottom: 'var(--space-6)' }}>
        <MetricCard
          label="Avg xR"
          value={data.avg_xR.toFixed(3)}
          state={getMetricState('xR', data.avg_xR)}
          delta="Expected runs per ball"
        />
        <MetricCard
          label="Avg xW"
          value={data.avg_xW.toFixed(4)}
          state={getMetricState('xW', data.avg_xW)}
          delta="Expected wicket probability"
        />
        <MetricCard
          label="False Shot %"
          value={`${data.false_shot_pct.toFixed(1)}%`}
          state={getMetricState('false_shot_pct', data.false_shot_pct)}
          delta="Proportion of false shots"
        />
        <MetricCard
          label="Dominant Intent"
          value={data.dominant_shot_intent}
          state={data.dominant_shot_intent === 'ATTACKING' ? 'green' : 'amber'}
          delta="Most frequent shot type"
        />
      </div>

      {/* Charts */}
      <div className="grid-2">
        <ShotIntentDonut distribution={data.shot_intent_distribution} />
        <PitchZoneBar distribution={data.pitch_zone_distribution} />
      </div>
    </div>
  );
}
