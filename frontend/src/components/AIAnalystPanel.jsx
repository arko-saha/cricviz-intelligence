import { useState, useEffect } from 'react';
import useUIStore from '../store/uiStore';
import { fetchAIInsight } from '../api/client';

export default function AIAnalystPanel() {
  const { aiPanelOpen, setAIPanelOpen, aiContextData, aiContextType } = useUIStore();
  const [insight, setInsight] = useState('');
  const [modelUsed, setModelUsed] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (aiPanelOpen && aiContextData) {
      generateInsight();
    }
  }, [aiPanelOpen, aiContextData]);

  const generateInsight = async () => {
    if (!aiContextData) return;
    setLoading(true);
    setError(null);
    setInsight('');

    try {
      const result = await fetchAIInsight(aiContextData, aiContextType);
      if (result.error) {
        setError(result.error);
      } else {
        setInsight(result.insight);
        setModelUsed(result.model_used);
        setStatus(result.status);
      }
    } catch (err) {
      setError(
        err.response?.status === 429
          ? 'Rate limit exceeded. Please wait a moment and try again.'
          : err.code === 'ECONNABORTED'
          ? 'Request timed out. Please try again.'
          : 'AI analysis is currently unavailable. Please try again later.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div
        className={`ai-panel-overlay ${aiPanelOpen ? 'open' : ''}`}
        onClick={() => setAIPanelOpen(false)}
      />
      <aside className={`ai-panel ${aiPanelOpen ? 'open' : ''}`}>
        <div className="ai-panel-header">
          <span className="ai-panel-title">
            ✦ AI Cricket Analyst
          </span>
          <button className="ai-panel-close" onClick={() => setAIPanelOpen(false)}>
            ✕
          </button>
        </div>

        <div className="ai-panel-body">
          {loading && (
            <div className="ai-loading">
              <div className="ai-loading-dot" />
              <div className="ai-loading-dot" />
              <div className="ai-loading-dot" />
              <span>Analyzing data...</span>
            </div>
          )}

          {error && (
            <div className="ai-error">
              {error}
            </div>
          )}

          {insight && !loading && (
            <div className={`ai-insight fade-in ${status === 'fallback' ? 'ai-insight-fallback' : ''}`}>
              {status === 'fallback' && (
                <div className="ai-fallback-warning" title="Free tier model unavailable or rate-limited. All fallback models were attempted.">
                  <span style={{ marginRight: 'var(--space-2)' }}>⚠</span>
                  <span className="text-xs">Fallback Mode</span>
                </div>
              )}
              <p style={{ color: status === 'fallback' ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                {insight}
              </p>
              {status === 'ok' && modelUsed && (
                <div className="text-xs text-muted" style={{ marginTop: 'var(--space-3)', textAlign: 'right' }}>
                  via {modelUsed}
                </div>
              )}
            </div>
          )}

          {!loading && !error && !insight && (
            <div className="empty-state" style={{ padding: '2rem 0' }}>
              <div className="empty-state-icon">✦</div>
              <h3 className="empty-state-title">No Analysis Yet</h3>
              <p className="empty-state-desc">
                Navigate to a match or player to generate AI-powered insights
                using xR, xW, and shot intent data.
              </p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
