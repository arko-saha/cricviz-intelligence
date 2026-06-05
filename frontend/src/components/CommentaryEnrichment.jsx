import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';

export default function CommentaryEnrichment() {
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [matchId, setMatchId] = useState('');
  const [daysBack, setDaysBack] = useState(7);
  const [message, setMessage] = useState('');

  const fetchUsage = async () => {
    try {
      const response = await apiClient.get('/pipeline/commentary-usage');
      setUsage(response.data);
    } catch (err) {
      console.error("Failed to fetch usage:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, []);

  const handleEnrich = async () => {
    if (!usage || usage.remaining < 2) return;
    
    setEnriching(true);
    setMessage('');
    try {
      await apiClient.post('/pipeline/enrich-commentary', {
        match_id: matchId || null,
        days_back: Number(daysBack)
      });
      setMessage('Enrichment task started in background.');
      // Refresh usage after a short delay since it's background
      setTimeout(fetchUsage, 2000);
    } catch (err) {
      setMessage(`Error: ${err.response?.data?.detail || err.message}`);
    } finally {
      setEnriching(false);
    }
  };

  if (loading) return <div className="panel">Loading commentary usage...</div>;

  const budgetPercent = usage ? (usage.today_used / usage.daily_limit) * 100 : 0;
  const isExhausted = usage?.remaining < 2;

  return (
    <div className="panel" style={{ marginTop: '1rem', border: '1px solid #444', padding: '1rem', borderRadius: '8px' }}>
      <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Commentary Enrichment</h3>
      
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
          <span>API Budget:</span>
          <span>{usage?.today_used} / {usage?.daily_limit}</span>
        </div>
        <div style={{ width: '100%', height: '10px', backgroundColor: '#333', borderRadius: '5px', overflow: 'hidden' }}>
          <div style={{ 
            height: '100%', 
            width: `${Math.min(100, budgetPercent)}%`, 
            backgroundColor: isExhausted ? '#e74c3c' : '#3498db',
            transition: 'width 0.3s ease'
          }} />
        </div>
        <div style={{ fontSize: '0.85rem', color: '#aaa', marginTop: '0.25rem' }}>
          Today's remaining: <strong>{usage?.remaining}</strong> calls
        </div>
        {usage?.last_call && (
          <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '0.25rem' }}>
            Last call: {new Date(usage.last_call).toLocaleString()}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>Match ID (optional)</label>
          <input 
            type="text" 
            value={matchId} 
            onChange={(e) => setMatchId(e.target.value)} 
            placeholder="Specific Match UUID"
            style={{ padding: '0.4rem', borderRadius: '4px', border: '1px solid #555', background: '#222', color: '#fff' }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>Days back</label>
          <select 
            value={daysBack} 
            onChange={(e) => setDaysBack(e.target.value)}
            style={{ padding: '0.4rem', borderRadius: '4px', border: '1px solid #555', background: '#222', color: '#fff' }}
          >
            <option value="1">1</option>
            <option value="3">3</option>
            <option value="7">7</option>
            <option value="14">14</option>
            <option value="30">30</option>
          </select>
        </div>
      </div>

      <button 
        onClick={handleEnrich} 
        disabled={isExhausted || enriching}
        style={{
          padding: '0.5rem 1rem',
          borderRadius: '4px',
          border: 'none',
          backgroundColor: isExhausted ? '#555' : '#2ecc71',
          color: '#fff',
          cursor: (isExhausted || enriching) ? 'not-allowed' : 'pointer',
          fontWeight: 'bold'
        }}
      >
        {enriching ? 'Starting...' : 'Enrich Commentary'}
      </button>

      {isExhausted && <span style={{ color: '#e74c3c', marginLeft: '1rem', fontSize: '0.9rem' }}>Daily limit reached</span>}
      {message && <div style={{ marginTop: '0.5rem', color: '#3498db', fontSize: '0.9rem' }}>{message}</div>}
    </div>
  );
}
