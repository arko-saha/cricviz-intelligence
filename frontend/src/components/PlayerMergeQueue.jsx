import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMergeQueue, resolveMerge } from '../api/client';

export default function PlayerMergeQueue() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState(null);

  const { data: queue, isLoading } = useQuery({
    queryKey: ['mergeQueue'],
    queryFn: getMergeQueue,
  });

  const mutation = useMutation({
    mutationFn: ({ queueId, action, canonical }) => resolveMerge(queueId, action, canonical),
    onMutate: async ({ queueId }) => {
      await queryClient.cancelQueries({ queryKey: ['mergeQueue'] });
      const previousQueue = queryClient.getQueryData(['mergeQueue']);
      queryClient.setQueryData(['mergeQueue'], (old) => old.filter(item => item.id !== queueId));
      return { previousQueue };
    },
    onError: (err, newTodo, context) => {
      queryClient.setQueryData(['mergeQueue'], context.previousQueue);
      setToast({ message: "Error resolving merge", type: 'error' });
      setTimeout(() => setToast(null), 3000);
    },
    onSuccess: (data) => {
      setToast({ message: `Successfully processed as ${data.action}`, type: 'success' });
      setTimeout(() => setToast(null), 3000);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['mergeQueue'] });
    },
  });

  if (isLoading) return <div className="text-muted text-sm">Loading queue...</div>;

  if (!queue || queue.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">✅</div>
        <h3 className="empty-state-title">No merge candidates</h3>
        <p className="empty-state-desc">All players resolved</p>
      </div>
    );
  }

  const getScoreBadge = (score) => {
    if (score >= 85) return "badge-teal";
    if (score >= 70) return "badge-amber";
    return "badge-red";
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Player Merge Queue ({queue.length})</span>
      </div>

      {toast && (
        <div className={`ai-error mb-4 ${toast.type === 'success' ? 'badge-teal' : 'badge-red'}`} style={{background: 'var(--bg-elevated)', padding: 'var(--space-2)'}}>
          {toast.message}
        </div>
      )}

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Raw Name</th>
              <th>Best Match</th>
              <th>Confidence</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {queue.map(item => (
              <tr key={item.id}>
                <td className="col-text font-medium">{item.raw_name}</td>
                <td className="col-text text-muted">{item.matched_canonical || 'N/A'}</td>
                <td>
                  {item.fuzzy_score ? (
                    <span className={`badge ${getScoreBadge(item.fuzzy_score)}`}>
                      {item.fuzzy_score.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="badge badge-muted">N/A</span>
                  )}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button 
                      className="btn btn-secondary text-xs"
                      style={{ minHeight: '32px', padding: 'var(--space-1) var(--space-3)' }}
                      onClick={() => mutation.mutate({ queueId: item.id, action: 'merge', canonical: item.matched_canonical })}
                      disabled={!item.matched_canonical || mutation.isPending}
                    >
                      Merge
                    </button>
                    <button 
                      className="btn btn-secondary text-xs"
                      style={{ minHeight: '32px', padding: 'var(--space-1) var(--space-3)' }}
                      onClick={() => mutation.mutate({ queueId: item.id, action: 'new' })}
                      disabled={mutation.isPending}
                    >
                      New Player
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
