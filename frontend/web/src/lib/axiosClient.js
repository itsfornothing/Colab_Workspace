/**
 * frontend/web/src/lib/axiosClient.js
 *
 * Production-ready Axios instance.
 *
 * Features:
 *  - Attaches Bearer token to every request automatically
 *  - Attaches X-Workspace-ID header from localStorage
 *  - Intercepts 401 responses and auto-refreshes the access token
 *  - Queues ALL requests that arrive during an ongoing refresh
 *    (prevents multiple simultaneous refresh calls — the classic race condition)
 *  - Retries every queued request after refresh succeeds
 *  - Fires global "auth:logout" event + redirects on refresh failure
 *
 * Usage:
 *   import api from '@/lib/axiosClient';
 *   const { data } = await api.get('/api/users/me/');
 *   const { data } = await api.post('/api/auth/login/', { email, password });
 */

import axios from 'axios';
import { getTokens, setTokens, clearTokens } from './tokenStorage';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Axios instance ────────────────────────────────────────────────
const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor ───────────────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const { accessToken } = getTokens();
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    const workspaceId = localStorage.getItem('current_workspace_id');
    if (workspaceId) {
      config.headers['X-Workspace-ID'] = workspaceId;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// ── Refresh queue ─────────────────────────────────────────────────
// Prevents multiple simultaneous refresh calls when several requests
// get 401 at the same time (e.g. on app load after token expiry).
let isRefreshing = false;
let failedQueue  = [];   // [{ resolve, reject }]

function processQueue(error, newAccessToken = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else       resolve(newAccessToken);
  });
  failedQueue = [];
}

// ── Response interceptor ──────────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    // Only handle 401; _retry flag prevents infinite retry loops
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    // Never try to refresh on auth endpoints themselves
    const skipPaths = [
      '/api/auth/login/',
      '/api/auth/refresh/',
      '/api/auth/register/',
    ];
    if (skipPaths.some((p) => original.url?.includes(p))) {
      return Promise.reject(error);
    }

    original._retry = true;

    if (isRefreshing) {
      // Another refresh is already in progress — queue this request
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((newAccessToken) => {
          original.headers.Authorization = `Bearer ${newAccessToken}`;
          return api(original);
        })
        .catch((err) => Promise.reject(err));
    }

    isRefreshing = true;
    const { refreshToken } = getTokens();

    if (!refreshToken) {
      processQueue(new Error('No refresh token'));
      isRefreshing = false;
      handleLogout();
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post(`${BASE_URL}/api/auth/refresh/`, {
        refresh: refreshToken,
      });

      const { access, refresh } = data;
      setTokens({ accessToken: access, refreshToken: refresh });

      // Resolve all queued requests with the new token
      processQueue(null, access);

      // Retry the original failed request
      original.headers.Authorization = `Bearer ${access}`;
      return api(original);
    } catch (refreshError) {
      processQueue(refreshError);
      handleLogout();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

// ── Global logout ─────────────────────────────────────────────────
function handleLogout() {
  clearTokens();
  localStorage.removeItem('current_workspace_id');
  window.dispatchEvent(new CustomEvent('auth:logout'));
  window.location.href = '/login';
}

export default api;