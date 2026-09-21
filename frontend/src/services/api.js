import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';
const api = axios.create({ baseURL: API_BASE, timeout: 15000, headers: { 'Content-Type': 'application/json' } });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('campusshield_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// A production client must surface a backend outage instead of fabricating
// authentication, sessions, alerts, or reports in browser storage.
export const isDemoMode = () => false;
export const login = (username, password) => api.post('/auth/login', new URLSearchParams({ username, password }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
export const signup = (userData) => api.post('/auth/signup', userData);
export const getMe = () => api.get('/auth/me');
export const simulateTraffic = (scenario, packetCount = 2000) => api.post(`/traffic/simulate/${scenario}`, { packet_count: packetCount });
export const inspectUrl = (data) => api.post('/traffic/inspect-url', data);
export const getSessions = () => api.get('/traffic/sessions');
export const getSession = (id) => api.get(`/traffic/sessions/${id}`);
export const getScenarios = () => api.get('/traffic/scenarios');
export const getDetectionConfig = () => api.get('/detection/config');
export const updateDetectionConfig = (data) => api.put('/detection/config', data);
export const getDetectionResults = (sessionId) => api.get(`/detection/results/${sessionId}`);
export const getAnomalousResults = (sessionId) => api.get(`/detection/results/${sessionId}/anomalies`);
export const getContributingFactors = (detectionId) => api.get(`/detection/factors/${detectionId}`);
export const getAlerts = (params = {}) => api.get('/alerts', { params });
export const getAlert = (id) => api.get(`/alerts/${id}`);
export const getAlertStats = () => api.get('/alerts/stats');
export const acknowledgeAlert = (id) => api.put(`/alerts/${id}/acknowledge`);
export const generateReport = (sessionId) => api.post(`/reports/generate/${sessionId}`);
export const getReports = () => api.get('/reports');
export const downloadReport = (id) => api.get(`/reports/${id}/download`, { responseType: 'blob' });
export default api;
