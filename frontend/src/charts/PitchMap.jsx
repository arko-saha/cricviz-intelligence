import { useState, useMemo } from 'react';
import EmptyState from '../components/EmptyState';

// ═══════════════════════════════════════════════════════════════════════
// PITCH MAP COMPONENT (TABULAR)
// ═══════════════════════════════════════════════════════════════════════
export default function PitchMap({ deliveries = [] }) {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [filterText, setFilterText] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 20;

  // ── Edge case: no data ───────────────────────────────────────────────
  if (!deliveries || deliveries.length === 0) {
    return <EmptyState icon="🎯" title="No Pitch Data" description="Pitch zone data is not available for this match." />;
  }

  // ── Sorting handler ──────────────────────────────────────────────────
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // ── Prepare data (Filter & Sort) ─────────────────────────────────────
  const processedData = useMemo(() => {
    let data = [...deliveries];

    // Filter
    if (filterText) {
      const lowerFilter = filterText.toLowerCase();
      data = data.filter((d) => 
        (d.batter?.toLowerCase() || '').includes(lowerFilter) ||
        (d.bowler?.toLowerCase() || '').includes(lowerFilter)
      );
    }

    // Sort
    if (sortConfig.key) {
      data.sort((a, b) => {
        let valA = a[sortConfig.key];
        let valB = b[sortConfig.key];

        // Composite keys
        if (sortConfig.key === 'over_ball') {
          valA = (a.over || 0) * 10 + (a.ball || 0);
          valB = (b.over || 0) * 10 + (b.ball || 0);
        }

        if (valA === valB) return 0;
        
        // Handle nulls
        if (valA == null) return 1;
        if (valB == null) return -1;

        if (typeof valA === 'string') {
          return sortConfig.direction === 'asc' 
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        }

        return sortConfig.direction === 'asc' ? valA - valB : valB - valA;
      });
    }

    return data;
  }, [deliveries, filterText, sortConfig]);

  // ── Pagination ───────────────────────────────────────────────────────
  const totalPages = Math.ceil(processedData.length / rowsPerPage);
  const paginatedData = processedData.slice(
    (currentPage - 1) * rowsPerPage,
    currentPage * rowsPerPage
  );

  const handlePrev = () => setCurrentPage((p) => Math.max(1, p - 1));
  const handleNext = () => setCurrentPage((p) => Math.min(totalPages, p + 1));

  // Reset page when filter changes
  useMemo(() => setCurrentPage(1), [filterText]);

  // ── CSV Download ─────────────────────────────────────────────────────
  const downloadCsv = () => {
    if (processedData.length === 0) return;

    const headers = ['Over.Ball', 'Batsman', 'Bowler', 'Pitch Zone', 'Landing X', 'Landing Y', 'Runs', 'Wicket'];
    const rows = processedData.map(d => [
      `${d.over || 0}.${d.ball || 0}`,
      d.batter || '',
      d.bowler || '',
      d.pitch_zone || '',
      d.pitch_map_x != null ? Number(d.pitch_map_x).toFixed(2) : '',
      d.pitch_map_y != null ? Number(d.pitch_map_y).toFixed(2) : '',
      (d.runs?.total ?? d.runs_bat ?? 0),
      d.wicket_type ? 'Yes' : 'No'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(r => r.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    // Attempt to extract matchId from the first delivery
    const matchId = processedData[0]?.match_id || 'unknown';
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `pitch_data_${matchId}_${timestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getSortIndicator = (key) => {
    if (sortConfig.key !== key) return ' ↕';
    return sortConfig.direction === 'asc' ? ' ↑' : ' ↓';
  };

  const thStyle = { 
    cursor: 'pointer', 
    padding: 'var(--space-2)', 
    borderBottom: '1px solid var(--border-subtle)',
    textAlign: 'left',
    color: 'var(--text-secondary)',
    fontWeight: 'var(--weight-medium)',
    fontSize: 'var(--text-xs)',
    userSelect: 'none'
  };

  const tdStyle = { 
    padding: 'var(--space-2)', 
    borderBottom: '1px solid var(--border-subtle)',
    fontSize: 'var(--text-sm)',
    color: 'var(--text-primary)'
  };

  return (
    <div className="card" style={{ minWidth: 0 }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
        <div>
          <span className="card-title">Pitch Map</span>
          <div style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
            marginTop: '2px',
          }}>
            Ball-by-ball pitch data — visual map coming soon
          </div>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <input 
            type="text" 
            placeholder="Filter batsman/bowler..." 
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            style={{
              padding: '4px 8px',
              fontSize: '12px',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-input, var(--bg-primary))',
              color: 'var(--text-primary)'
            }}
          />
          <button 
            onClick={downloadCsv}
            className="btn btn-secondary text-xs"
            style={{ padding: '4px 8px' }}
          >
            Download CSV
          </button>
        </div>
      </div>

      {/* ── Table ─────────────────────────────────────────────────── */}
      <div style={{ overflowX: 'auto', padding: '0 var(--space-3)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle} onClick={() => handleSort('over_ball')}>Over.Ball{getSortIndicator('over_ball')}</th>
              <th style={thStyle} onClick={() => handleSort('batter')}>Batsman{getSortIndicator('batter')}</th>
              <th style={thStyle} onClick={() => handleSort('bowler')}>Bowler{getSortIndicator('bowler')}</th>
              <th style={thStyle} onClick={() => handleSort('pitch_zone')}>Pitch Zone{getSortIndicator('pitch_zone')}</th>
              <th style={thStyle} onClick={() => handleSort('pitch_map_x')}>Landing X{getSortIndicator('pitch_map_x')}</th>
              <th style={thStyle} onClick={() => handleSort('pitch_map_y')}>Landing Y{getSortIndicator('pitch_map_y')}</th>
              <th style={thStyle} onClick={() => handleSort('runs_bat')}>Runs{getSortIndicator('runs_bat')}</th>
              <th style={thStyle} onClick={() => handleSort('wicket_type')}>Wicket{getSortIndicator('wicket_type')}</th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ ...tdStyle, textAlign: 'center', padding: 'var(--space-4)', color: 'var(--text-muted)' }}>
                  No deliveries match the filter.
                </td>
              </tr>
            ) : (
              paginatedData.map((d) => (
                <tr key={d.id || `${d.over}_${d.ball}_${d.batter}_${d.bowler}`}>
                  <td style={tdStyle}>{d.over || 0}.{d.ball || 0}</td>
                  <td style={tdStyle}>{d.batter || '—'}</td>
                  <td style={tdStyle}>{d.bowler || '—'}</td>
                  <td style={tdStyle}>{d.pitch_zone ? d.pitch_zone.replace('_', ' ') : '—'}</td>
                  <td style={tdStyle}>{d.pitch_map_x != null ? Number(d.pitch_map_x).toFixed(2) : '—'}</td>
                  <td style={tdStyle}>{d.pitch_map_y != null ? Number(d.pitch_map_y).toFixed(2) : '—'}</td>
                  <td style={tdStyle}>{(d.runs?.total ?? d.runs_bat ?? 0)}</td>
                  <td style={tdStyle}>
                    {d.wicket_type ? (
                      <span style={{ color: 'var(--color-danger)', fontWeight: 'bold' }}>Yes</span>
                    ) : 'No'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ─────────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          padding: 'var(--space-3)',
          borderTop: '1px solid var(--border-subtle)'
        }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            Page {currentPage} of {totalPages}
          </span>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button 
              onClick={handlePrev} 
              disabled={currentPage === 1}
              className="btn btn-secondary text-xs"
              style={{ padding: '4px 8px', opacity: currentPage === 1 ? 0.5 : 1 }}
            >
              Prev
            </button>
            <button 
              onClick={handleNext} 
              disabled={currentPage === totalPages}
              className="btn btn-secondary text-xs"
              style={{ padding: '4px 8px', opacity: currentPage === totalPages ? 0.5 : 1 }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
