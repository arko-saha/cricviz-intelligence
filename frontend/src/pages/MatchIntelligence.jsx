import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchMatches, fetchDeliveries, fetchWormData } from '../api/client';
import useUIStore from '../store/uiStore';
import WormChart from '../charts/WormChart';
import HeatmapGrid from '../charts/HeatmapGrid';
import EmptyState from '../components/EmptyState';

/**
 * PILLAR 1 — Match Intelligence
 *
 * Shows match list or detailed match view with:
 * - MatchHeader (teams, venue, date, outcome)
 * - WormChart (over-by-over cumulative runs)
 * - DeliveryExplorer (filterable table)
 * - HeatmapGrid (SVG pitch map by xW)
 */
export default function MatchIntelligence() {
  const { id: matchId } = useParams();

  if (matchId) {
    return <MatchDetail matchId={matchId} />;
  }
  return <MatchList />;
}

function MatchList() {
  const [page, setPage] = useState(1);
  const [team, setTeam] = useState('');
  const [venue, setVenue] = useState('');
  const [year, setYear] = useState('');
  const [gender, setGender] = useState('');
  const navigate = useNavigate();
  const setAIContext = useUIStore(s => s.setAIContext);

  const { data, isLoading } = useQuery({
    queryKey: ['matches', page, team, venue, year, gender],
    queryFn: () => fetchMatches(page, 20, { team, venue, year, gender }),
  });

  if (isLoading) {
    return (
      <div className="fade-in">
        <div className="page-header">
          <h1 className="page-title">Match Intelligence</h1>
          <p className="page-subtitle">Loading matches...</p>
        </div>
        <div className="grid-3">
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton skeleton-card" />)}
        </div>
      </div>
    );
  }

  const matches = data?.matches || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="fade-in">
      <div className="page-header match-list-header border-bottom">
        <div>
          <h1 className="page-title mb-1">Match Intelligence</h1>
          <p className="page-subtitle">{total} matches loaded · Page {page} of {totalPages || 1}</p>
        </div>
        
        <div className="filter-bar filter-bar-advanced">
          <div className="filter-input-wrapper">
            <div className="filter-icon">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
            </div>
            <input 
              type="text" 
              placeholder="Team..." 
              value={team} 
              onChange={(e) => { setTeam(e.target.value); setPage(1); }}
              className="filter-input filter-input-text w-team"
            />
          </div>
          
          <div className="filter-input-wrapper">
            <div className="filter-icon">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
            </div>
            <input 
              type="text" 
              placeholder="Venue..." 
              value={venue} 
              onChange={(e) => { setVenue(e.target.value); setPage(1); }}
              className="filter-input filter-input-text w-venue"
            />
          </div>

          <div className="filter-input-wrapper">
            <div className="filter-icon">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
            </div>
            <input 
              type="text" 
              placeholder="Year..." 
              value={year} 
              onChange={(e) => { setYear(e.target.value); setPage(1); }}
              className="filter-input filter-input-text w-year"
            />
          </div>

          <div className="filter-input-wrapper">
            <div className="filter-icon">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path></svg>
            </div>
            <select 
              value={gender} 
              onChange={(e) => { setGender(e.target.value); setPage(1); }}
              className="filter-input filter-input-select"
            >
              <option value="">All Categories</option>
              <option value="male">Men's Cricket</option>
              <option value="female">Women's Cricket</option>
            </select>
          </div>
        </div>
      </div>

      {matches.length === 0 ? (
        <EmptyState
          icon="🏏"
          title="No Matches Found"
          description="Ingest Cricsheet data using the Pipeline tab to populate the database."
        />
      ) : (
        <>
          <div className="grid-3">
            {matches.map(m => (
              <div
                key={m.id}
                className="card"
                style={{ cursor: 'pointer' }}
                onClick={() => {
                  setAIContext(m, 'match');
                  navigate(`/match/${m.id}`);
                }}
              >
                <div className="match-card-header">
                  <div className="match-card-badges">
                    <span className="badge badge-teal">{m.match_type}</span>
                    {m.gender === 'female' && <span className="badge badge-purple">Women</span>}
                    {m.gender === 'male' && <span className="badge badge-muted">Men</span>}
                  </div>
                  <span className="font-mono text-xs match-date-badge">{m.date}</span>
                </div>
                <div style={{ marginBottom: 'var(--space-2)' }}>
                  <span style={{ fontWeight: 700, fontSize: 'var(--text-base)' }}>{m.team1}</span>
                  <span style={{ color: 'var(--text-muted)', margin: '0 var(--space-2)', fontSize: 'var(--text-xs)' }}>vs</span>
                  <span style={{ fontWeight: 700, fontSize: 'var(--text-base)' }}>{m.team2}</span>
                </div>
                <div className="text-sm text-muted" style={{ marginBottom: 'var(--space-2)' }}>{m.venue}</div>
                <div className="text-xs font-mono" style={{ color: 'var(--accent-amber)' }}>
                  {m.outcome}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-3)', marginTop: 'var(--space-8)' }}>
            <button
              className="btn btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              ← Previous
            </button>
            <span className="font-mono text-sm" style={{ display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>
              {page} / {totalPages || 1}
            </span>
            <button
              className="btn btn-secondary"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function MatchDetail({ matchId }) {
  const [filterInnings, setFilterInnings] = useState('');
  const [filterOver, setFilterOver] = useState('');
  const navigate = useNavigate();
  const setAIContext = useUIStore(s => s.setAIContext);

  const { data: deliveriesData, isLoading: delLoading } = useQuery({
    queryKey: ['deliveries', matchId, filterInnings, filterOver],
    queryFn: () => fetchDeliveries(
      matchId,
      filterInnings || undefined,
      filterOver !== '' ? parseInt(filterOver) : undefined,
    ),
  });

  const { data: wormData } = useQuery({
    queryKey: ['worm', matchId],
    queryFn: () => fetchWormData(matchId),
  });

  const deliveries = deliveriesData?.deliveries || [];

  // Set AI context when data loads
  if (deliveriesData && !delLoading) {
    // We pass a summary to avoid sending all deliveries
    const summary = {
      match_id: matchId,
      total_deliveries: deliveries.length,
      boundaries: deliveries.filter(d => d.runs_bat >= 4).length,
      wickets: deliveries.filter(d => d.wicket_type).length,
      avg_xR: deliveries.length ? (deliveries.reduce((s, d) => s + d.xR, 0) / deliveries.length).toFixed(3) : 0,
      avg_xW: deliveries.length ? (deliveries.reduce((s, d) => s + d.xW, 0) / deliveries.length).toFixed(3) : 0,
      false_shot_pct: deliveries.length ? ((deliveries.filter(d => d.is_false_shot).length / deliveries.length) * 100).toFixed(1) : 0,
    };
    // Use setTimeout to avoid state update during render
    setTimeout(() => setAIContext(summary, 'match'), 0);
  }

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 'var(--space-4)' }}>
        <button className="btn btn-secondary text-sm" onClick={() => navigate('/')}>
          ← Back to Matches
        </button>
      </div>

      {/* Worm Chart + Heatmap side by side */}
      <div className="grid-2" style={{ marginBottom: 'var(--space-6)' }}>
        <WormChart data={wormData?.data || []} />
        <HeatmapGrid deliveries={deliveries} />
      </div>

      {/* Delivery Explorer */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Delivery Explorer</span>
          <span className="badge badge-muted">{deliveries.length} deliveries</span>
        </div>

        <div className="filter-bar">
          <select
            className="filter-select"
            value={filterInnings}
            onChange={e => setFilterInnings(e.target.value)}
          >
            <option value="">All Innings</option>
            <option value="1">Innings 1</option>
            <option value="2">Innings 2</option>
          </select>
          <input
            type="number"
            className="form-input"
            placeholder="Filter by over..."
            value={filterOver}
            onChange={e => setFilterOver(e.target.value)}
            min="0"
            max="50"
            style={{ maxWidth: '160px', minHeight: '36px', padding: 'var(--space-2) var(--space-3)' }}
          />
          {filterOver !== '' && deliveries.length > 0 && (
            <button 
              className="btn btn-ai-action"
              onClick={() => {
                const overSummary = {
                  match_id: matchId,
                  over: filterOver,
                  deliveries: deliveries.map(d => ({
                    ball: d.ball,
                    bowler: d.bowler,
                    batter: d.batter,
                    runs: d.runs_bat + d.runs_extras,
                    wicket: d.wicket_type,
                    intent: d.shot_intent,
                    xR: d.xR,
                    xW: d.xW
                  }))
                };
                setAIContext(overSummary, 'over');
                useUIStore.getState().setAIPanelOpen(true);
              }}
            >
              ✦ Ask AI about Over {filterOver}
            </button>
          )}
        </div>

        {deliveries.length === 0 ? (
          <EmptyState icon="📋" title="No Deliveries" description="No delivery data available for the selected filters." />
        ) : (
          <div className="data-table-container" style={{ maxHeight: '500px', overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Over.Ball</th>
                  <th>Bowler</th>
                  <th>Batter</th>
                  <th>Intent</th>
                  <th>Zone</th>
                  <th>False?</th>
                  <th>xR</th>
                  <th>xW</th>
                  <th>Runs</th>
                  <th>Wicket</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map(d => (
                  <tr key={d.id}>
                    <td>{d.over}.{d.ball}</td>
                    <td className="col-text">{d.bowler}</td>
                    <td
                      className="col-text"
                      style={{ color: 'var(--accent-teal)', cursor: 'pointer' }}
                      onClick={() => {/* Navigate to player in future */}}
                    >
                      {d.batter}
                    </td>
                    <td>
                      <span className={`badge ${d.shot_intent === 'ATTACKING' ? 'badge-teal' : d.shot_intent === 'DEFENSIVE' ? 'badge-muted' : 'badge-amber'}`}>
                        {d.shot_intent}
                      </span>
                    </td>
                    <td className="text-xs">{d.pitch_zone}</td>
                    <td>{d.is_false_shot ? <span className="badge badge-red">YES</span> : '—'}</td>
                    <td style={{ color: d.xR > 1.2 ? 'var(--color-success)' : d.xR < 0.3 ? 'var(--color-danger)' : 'var(--text-primary)' }}>
                      {d.xR.toFixed(2)}
                    </td>
                    <td style={{ color: d.xW > 0.08 ? 'var(--color-danger)' : 'var(--text-primary)' }}>
                      {d.xW.toFixed(3)}
                    </td>
                    <td>{d.runs_bat + d.runs_extras}</td>
                    <td className="col-text">{d.wicket_type || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
