import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchModelInfo, fetchTrainingStats, retrainModels } from '../api/client';

export default function MLModelStatus() {
  const queryClient = useQueryClient();
  const [retrainTarget, setRetrainTarget] = useState('both');
  const [toast, setToast] = useState(null);

  const isAdmin = import.meta.env.VITE_ADMIN_MODE === 'true';

  const { data: models } = useQuery({
    queryKey: ['modelInfo'],
    queryFn: fetchModelInfo,
    refetchInterval: 5000,
  });

  const { data: stats } = useQuery({
    queryKey: ['trainingStats'],
    queryFn: fetchTrainingStats,
  });

  const mutation = useMutation({
    mutationFn: (target) => retrainModels(target),
    onSuccess: () => {
      setToast({ message: "Retraining job started in background.", type: "success" });
      setTimeout(() => setToast(null), 3000);
    },
    onError: (err) => {
      setToast({ message: err.response?.data?.detail || "Failed to start retraining", type: "error" });
      setTimeout(() => setToast(null), 3000);
    }
  });

  const formatDate = (isoStr) => {
    if (!isoStr) return 'Never';
    return new Date(isoStr).toLocaleString();
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">ML Model Status</span>
        {isAdmin && (
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <select 
              className="filter-select text-xs" 
              style={{ minHeight: '32px' }}
              value={retrainTarget}
              onChange={(e) => setRetrainTarget(e.target.value)}
            >
              <option value="both">Both Models</option>
              <option value="xR">xR Model Only</option>
              <option value="xW">xW Model Only</option>
            </select>
            <button 
              className="btn btn-primary text-xs"
              style={{ minHeight: '32px', padding: 'var(--space-1) var(--space-4)' }}
              onClick={() => mutation.mutate(retrainTarget)}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? 'Starting...' : 'Retrain'}
            </button>
          </div>
        )}
      </div>

      {toast && (
        <div className={`ai-error mb-4 ${toast.type === 'success' ? 'badge-teal' : 'badge-red'}`} style={{background: 'var(--bg-elevated)', padding: 'var(--space-2)'}}>
          {toast.message}
        </div>
      )}

      <div className="grid-2 mb-6">
        {/* xR Card */}
        <div className={`metric-card ${models?.xR?.exists ? 'state-green' : 'state-red'}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <div className="metric-label">xR Regressor</div>
            <span className={`badge ${models?.xR?.exists ? 'badge-teal' : 'badge-red'}`}>
              {models?.xR?.exists ? 'Active' : 'Missing'}
            </span>
          </div>
          <div className="text-xs text-muted font-mono">
            <div>Last Trained: {formatDate(models?.xR?.mtime)}</div>
            <div>Size: {models?.xR?.file_size_kb || 0} KB</div>
          </div>
        </div>

        {/* xW Card */}
        <div className={`metric-card ${models?.xW?.exists ? 'state-green' : 'state-red'}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <div className="metric-label">xW Classifier</div>
            <span className={`badge ${models?.xW?.exists ? 'badge-teal' : 'badge-red'}`}>
              {models?.xW?.exists ? 'Active' : 'Missing'}
            </span>
          </div>
          <div className="text-xs text-muted font-mono">
            <div>Last Trained: {formatDate(models?.xW?.mtime)}</div>
            <div>Size: {models?.xW?.file_size_kb || 0} KB</div>
          </div>
        </div>
      </div>

      {stats && (
        <div style={{ marginTop: 'var(--space-6)', paddingTop: 'var(--space-4)', borderTop: '1px solid var(--border-subtle)' }}>
          <div className="text-xs text-secondary font-semibold uppercase tracking-wide mb-3">
            Training Data Availability
          </div>
          <div className="grid-3 font-mono text-xs text-muted">
            <div>
              <div className="mb-1">Total Deliveries</div>
              <div className="text-primary text-base font-bold">{stats.total_deliveries.toLocaleString()}</div>
            </div>
            <div>
              <div className="mb-1">Commentary Coverage</div>
              <div className="text-primary text-base font-bold">
                {stats.total_deliveries ? Math.round((stats.deliveries_with_commentary / stats.total_deliveries) * 100) : 0}%
              </div>
              <div>({stats.deliveries_with_commentary.toLocaleString()})</div>
            </div>
            <div>
              <div className="mb-1">Shot Intent Labeled</div>
              <div className="text-primary text-base font-bold">
                {stats.total_deliveries ? Math.round((stats.deliveries_with_shot_intent / stats.total_deliveries) * 100) : 0}%
              </div>
              <div>({stats.deliveries_with_shot_intent.toLocaleString()})</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
