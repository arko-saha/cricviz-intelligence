import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cricviz_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auth ─────────────────────────────────────────────────────────
export const login = (username, password) => {
  const params = new URLSearchParams();
  params.append('username', username);
  params.append('password', password);
  return api.post('/auth/token', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }).then(r => r.data);
};

export const register = (username, password) =>
  api.post('/auth/register', { username, password }).then(r => r.data);


// ── Search ───────────────────────────────────────────────────────
export const globalSearch = (q) =>
  api.get('/search', { params: { q } }).then(r => r.data);

// ── Matches ──────────────────────────────────────────────────────
export const fetchMatches = (page = 1, limit = 20, filters = {}) => {
  const params = { page, limit, ...filters };
  // Remove empty filters
  Object.keys(params).forEach(key => {
    if (params[key] === '' || params[key] === null || params[key] === undefined) {
      delete params[key];
    }
  });
  return api.get('/matches', { params }).then(r => r.data);
};

export const fetchDeliveries = (matchId, innings, over) =>
  api.get(`/matches/${matchId}/deliveries`, {
    params: { ...(innings && { innings }), ...(over !== undefined && over !== null && { over }) },
  }).then(r => r.data);

// ── Players ──────────────────────────────────────────────────────
export const fetchPlayerProfile = (playerId) =>
  api.get(`/players/${playerId}/profile`).then(r => r.data);

// ── Analytics ────────────────────────────────────────────────────
export const fetchWormData = (matchId) =>
  api.get(`/analytics/match/${matchId}/worm`).then(r => r.data);

// ── Stats & Health ───────────────────────────────────────────────
export const fetchStats = () =>
  api.get('/stats').then(r => r.data);

export const fetchHealth = () =>
  api.get('/health').then(r => r.data);

// ── Ingestion ────────────────────────────────────────────────────
export const triggerIngest = (source, eventFilter = null) =>
  api.post('/ingest', { source, event_filter: eventFilter }).then(r => r.data);

export const fetchJobStatus = (jobId) =>
  api.get(`/ingest/status/${jobId}`).then(r => r.data);

// ── AI Insight ───────────────────────────────────────────────────
export const fetchAIInsight = (contextData, contextType = 'match') =>
  api.post('/ai/insight', { context_data: contextData, context_type: contextType })
    .then(r => r.data);

export const prewarmAI = () =>
  api.post('/ai/prewarm').then(r => r.data).catch(() => {});

// ── Admin ────────────────────────────────────────────────────────
export const getMergeQueue = () =>
  api.get('/admin/merge-queue').then(r => r.data);

export const resolveMerge = (queueId, action, canonical = null) =>
  api.patch(`/admin/merge-queue/${queueId}/resolve`, { action, canonical }).then(r => r.data);

// ── ML ───────────────────────────────────────────────────────────
export const fetchModelInfo = () =>
  api.get('/v1/ml/model-info').then(r => r.data);

export const fetchTrainingStats = () =>
  api.get('/v1/ml/training-data-stats').then(r => r.data);

export const retrainModels = (target) =>
  api.post('/v1/ml/retrain', { target }).then(r => r.data);

export default api;
