import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Navbar from './components/Navbar';
import ErrorBoundary from './components/ErrorBoundary';
import AIAnalystPanel from './components/AIAnalystPanel';
import MatchIntelligence from './pages/MatchIntelligence';
import PlayerIntelligence from './pages/PlayerIntelligence';
import PipelineControl from './pages/PipelineControl';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

import { useEffect } from 'react';
import { prewarmAI } from './api/client';

export default function App() {
  useEffect(() => {
    prewarmAI();
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-layout">
          <Navbar />
          <main className="app-main">
            <Routes>
              {/* Pillar 1: Pipeline Control */}
              <Route
                path="/"
                element={
                  <ErrorBoundary>
                    <PipelineControl />
                  </ErrorBoundary>
                }
              />

              {/* Pillar 2: Match Intelligence */}
              <Route
                path="/matches"
                element={
                  <ErrorBoundary>
                    <MatchIntelligence />
                  </ErrorBoundary>
                }
              />
              <Route
                path="/match/:id"
                element={
                  <ErrorBoundary>
                    <MatchIntelligence />
                  </ErrorBoundary>
                }
              />

              {/* Pillar 3: Player Intelligence */}
              <Route
                path="/player/:id"
                element={
                  <ErrorBoundary>
                    <PlayerIntelligence />
                  </ErrorBoundary>
                }
              />
            </Routes>
          </main>
          <AIAnalystPanel />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
