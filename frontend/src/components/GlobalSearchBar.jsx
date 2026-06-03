import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { globalSearch } from '../api/client';

export default function GlobalSearchBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ players: [], matches: [] });
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const delayDebounceFn = setTimeout(async () => {
      if (query.trim().length > 2) {
        setLoading(true);
        try {
          const data = await globalSearch(query);
          setResults(data);
          setIsOpen(true);
        } catch (error) {
          console.error("Search failed", error);
        } finally {
          setLoading(false);
        }
      } else {
        setResults({ players: [], matches: [] });
        setIsOpen(false);
      }
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [query]);

  const handlePlayerClick = (id) => {
    navigate(`/player/${id}`);
    setIsOpen(false);
    setQuery('');
  };

  const handleMatchClick = (id) => {
    navigate(`/match/${id}`);
    setIsOpen(false);
    setQuery('');
  };

  return (
    <div ref={wrapperRef} className="search-bar-container">
      <div className="search-input-wrapper">
        <div className="search-icon">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search players, teams, venues..."
          className="search-input"
        />
        {loading ? (
          <div className="search-action-icon search-loading">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
        ) : query && (
          <button 
            onClick={() => setQuery('')}
            className="search-action-icon search-clear"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {isOpen && (results.players.length > 0 || results.matches.length > 0) && (
        <div className="search-dropdown">
          {results.players.length > 0 && (
            <div className="search-group">
              <div className="search-group-title text-teal">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                Players
              </div>
              {results.players.map(p => (
                <button
                  key={p.id}
                  onClick={() => handlePlayerClick(p.id)}
                  className="search-result-item"
                >
                  <div className="search-result-title">{p.name}</div>
                  <div className="search-result-subtitle badge-dark">{p.country || 'Unknown'}</div>
                </button>
              ))}
            </div>
          )}
          
          {results.matches.length > 0 && (
            <div className="search-group border-top group-alt">
              <div className="search-group-title text-amber">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                Matches
              </div>
              {results.matches.map(m => (
                <button
                  key={m.id}
                  onClick={() => handleMatchClick(m.id)}
                  className="search-result-item"
                >
                  <div className="search-result-header">
                    <span className="search-result-title">
                      {m.team1} <span className="search-result-vs">vs</span> {m.team2}
                    </span>
                    <span className="search-result-badge">{m.match_type}</span>
                  </div>
                  <div className="search-result-meta">
                    <span>{m.date}</span>
                    <span className="search-result-dot"></span>
                    <span className="truncate">{m.venue}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
