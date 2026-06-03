import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import useUIStore from '../store/uiStore';
import useAuthStore from '../store/authStore';
import LoginModal from './LoginModal';
import GlobalSearchBar from './GlobalSearchBar';

export default function Navbar() {
  const toggleAIPanel = useUIStore((s) => s.toggleAIPanel);
  const { token, logout } = useAuthStore();
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const location = useLocation();

  return (
    <>
      <nav className="navbar">
        <div className="navbar-brand">
          <div className="navbar-brand-icon">CV</div>
          <span>CricViz Intelligence</span>
        </div>

        <GlobalSearchBar />

        <div className="navbar-links">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `navbar-link ${isActive ? 'active' : ''}`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
            Pipeline
          </NavLink>
          <NavLink
            to="/matches"
            className={({ isActive }) => `navbar-link ${isActive || location.pathname.startsWith('/match/') ? 'active' : ''}`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            Matches
          </NavLink>
        </div>

        <div className="navbar-auth">
          {token ? (
            <button 
              className="btn-text"
              onClick={logout}
            >
              Logout
            </button>
          ) : (
            <button 
              className="btn-text btn-text-accent"
              onClick={() => setIsLoginOpen(true)}
            >
              Login
            </button>
          )}
          <button className="navbar-ai-btn" onClick={toggleAIPanel}>
            ✦ AI Analyst
          </button>
        </div>
      </nav>
      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </>
  );
}
