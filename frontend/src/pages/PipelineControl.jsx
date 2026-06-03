import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { triggerIngest, fetchJobStatus, fetchStats, fetchHealth } from '../api/client';
import MetricCard from '../components/MetricCard';

/**
 * PILLAR 3 — Pipeline Control
 *
 * Components:
 * - IngestForm (text input + submit)
 * - JobStatusFeed (polls every 3s)
 * - DatabaseStats (counts)
 */
export default function PipelineControl() {
  const [source, setSource] = useState('');
  const [jobId, setJobId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Database stats
  const { data: stats, refetch: refetchStats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 5000,
  });

  // Health check
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 3000,
  });

  // Job status polling
  const { data: jobStatus } = useQuery({
    queryKey: ['jobStatus', jobId],
    queryFn: () => fetchJobStatus(jobId),
    enabled: !!jobId,
    refetchInterval: jobId ? 3000 : false,
  });

  // Stop polling when job completes
  useEffect(() => {
    if (jobStatus?.status === 'completed' || jobStatus?.status === 'error') {
      refetchStats();
    }
  }, [jobStatus?.status]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!source.trim() || submitting) return;

    setSubmitting(true);
    setError(null);

    try {
      const result = await triggerIngest(source.trim());
      setJobId(result.job_id);
      setSource('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start ingestion');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Pipeline Control</h1>
        <p className="page-subtitle">Ingest Cricsheet data and monitor database health</p>
      </div>

      {/* Database Stats */}
      <div className="grid-4" style={{ marginBottom: 'var(--space-8)' }}>
        <MetricCard
          label="Matches"
          value={stats?.matches?.toLocaleString() || '0'}
          state="teal"
        />
        <MetricCard
          label="Players"
          value={stats?.players?.toLocaleString() || '0'}
          state="teal"
        />
        <MetricCard
          label="Deliveries"
          value={stats?.deliveries?.toLocaleString() || '0'}
          state="amber"
        />
        <MetricCard
          label="Enriched"
          value={stats?.enriched_metrics?.toLocaleString() || '0'}
          state="green"
        />
      </div>

      <div className="grid-2">
        {/* Ingest Form */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Ingest Data</span>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="ingest-source">
                Source Path or URL
              </label>
              <input
                id="ingest-source"
                type="text"
                className="form-input"
                placeholder="e.g., C:\path\to\t20s_json.zip or https://cricsheet.org/downloads/t20s_json.zip"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                disabled={submitting}
              />
            </div>

            {error && (
              <div className="ai-error" style={{ marginBottom: 'var(--space-4)' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={!source.trim() || submitting}
              style={{ width: '100%' }}
            >
              {submitting ? '⏳ Submitting...' : '🚀 Start Ingestion'}
            </button>
          </form>

          {/* Quick Actions (Data Sources) */}
          <div style={{ marginTop: 'var(--space-6)' }}>
            <div className="text-xs text-muted mb-2 font-mono uppercase" style={{ letterSpacing: '0.05em' }}>
              Data Sources Catalog
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--space-2)' }}>
              {[
                { name: 'Tests', url: 'https://cricsheet.org/downloads/tests_json.zip' },
                { name: 'ODIs', url: 'https://cricsheet.org/downloads/odis_json.zip' },
                { name: 'T20Is', url: 'https://cricsheet.org/downloads/t20s_json.zip' },
                { name: 'Big Bash League', url: 'https://cricsheet.org/downloads/bbl_json.zip' },
                { name: 'Bangladesh Premier League', url: 'https://cricsheet.org/downloads/bpl_json.zip' },
                { name: 'Caribbean Premier League', url: 'https://cricsheet.org/downloads/cpl_json.zip' },
                { name: 'The Hundred', url: 'https://cricsheet.org/downloads/hnd_json.zip' },
                { name: 'Indian Premier League', url: 'https://cricsheet.org/downloads/ipl_json.zip' },
                { name: 'Lanka Premier League', url: 'https://cricsheet.org/downloads/lpl_json.zip' },
                { name: 'Pakistan Super League', url: 'https://cricsheet.org/downloads/psl_json.zip' },
              ].map(source => (
                <button
                  key={source.name}
                  className="btn btn-secondary text-xs"
                  style={{ justifyContent: 'flex-start', padding: 'var(--space-2)' }}
                  onClick={() => setSource(source.url)}
                >
                  <svg className="w-4 h-4 mr-1 text-teal" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ width: '14px', height: '14px', marginRight: '6px', color: 'var(--accent-teal)' }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                  {source.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Job Status Feed */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Job Status</span>
            <span className={`badge ${
              health?.db === 'connected' ? 'badge-teal' : 'badge-red'
            }`}>
              DB: {health?.db || 'unknown'}
            </span>
          </div>

          {!jobId ? (
            <div className="empty-state" style={{ padding: '2rem 0' }}>
              <div className="empty-state-icon">📡</div>
              <h3 className="empty-state-title">No Active Jobs</h3>
              <p className="empty-state-desc">Submit a data source to begin ingestion</p>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-4)', flexWrap: 'wrap' }}>
                <div>
                  <div className="text-xs text-muted" style={{ marginBottom: 'var(--space-1)' }}>Status</div>
                  <span className={`badge ${
                    jobStatus?.status === 'completed' ? 'badge-teal' :
                    jobStatus?.status === 'error' ? 'badge-red' :
                    'badge-amber'
                  }`}>
                    {jobStatus?.status || 'pending'}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-muted" style={{ marginBottom: 'var(--space-1)' }}>Matches</div>
                  <span className="font-mono">{jobStatus?.matches_processed || 0}</span>
                </div>
                <div>
                  <div className="text-xs text-muted" style={{ marginBottom: 'var(--space-1)' }}>Failed</div>
                  <span className="font-mono" style={{ color: 'var(--color-danger)' }}>
                    {jobStatus?.matches_failed || 0}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-muted" style={{ marginBottom: 'var(--space-1)' }}>Deliveries</div>
                  <span className="font-mono">{jobStatus?.total_deliveries?.toLocaleString() || 0}</span>
                </div>
              </div>

              {/* Progress Bar */}
              {jobStatus?.total_matches > 0 && (
                <div style={{ marginBottom: 'var(--space-4)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-1)' }}>
                    <span className="text-xs text-muted">Ingestion Progress</span>
                    <span className="text-xs font-mono text-teal">
                      {Math.round(((jobStatus.matches_processed + jobStatus.matches_failed) / jobStatus.total_matches) * 100)}%
                    </span>
                  </div>
                  <div style={{ 
                    width: '100%', 
                    height: '6px', 
                    background: 'var(--bg-hover)', 
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      height: '100%',
                      width: `${Math.round(((jobStatus.matches_processed + jobStatus.matches_failed) / jobStatus.total_matches) * 100)}%`,
                      background: 'linear-gradient(90deg, var(--accent-teal), var(--accent-amber))',
                      transition: 'width 0.3s ease'
                    }} />
                  </div>
                </div>
              )}

              {/* Log feed */}
              <div style={{
                maxHeight: '300px', overflowY: 'auto',
                background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)',
                padding: 'var(--space-3)', border: '1px solid var(--border-subtle)',
              }}>
                {(jobStatus?.logs || []).slice(-20).map((log, i) => (
                  <div key={i} className="font-mono text-xs" style={{
                    padding: 'var(--space-1) 0',
                    color: log.status === 'error' ? 'var(--color-danger)' :
                           log.status === 'skipped' ? 'var(--text-muted)' :
                           'var(--accent-teal)',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}>
                    [{log.status}] {log.file}
                    {log.deliveries_parsed !== undefined && ` · ${log.deliveries_parsed} balls`}
                    {log.duration_ms !== undefined && ` · ${log.duration_ms}ms`}
                    {log.reason && ` · ${log.reason}`}
                    {log.error && ` · ${log.error}`}
                  </div>
                ))}
                {(!jobStatus?.logs || jobStatus.logs.length === 0) && (
                  <span className="text-muted text-xs">Waiting for logs...</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
