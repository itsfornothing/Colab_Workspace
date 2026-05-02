/**
 * frontend/web/src/hooks/useAuth.js
 *
 * React auth context + hooks.
 *
 * Provides:
 *   AuthProvider        — wraps the app, restores session on mount
 *   useAuth()           — { user, login, logout, isLoading, isAuthenticated }
 *   ProtectedRoute      — redirects to /login if not authenticated
 *
 * Usage in App.jsx:
 *   import { AuthProvider } from '@/hooks/useAuth';
 *   <AuthProvider><App /></AuthProvider>
 *
 * Usage in any component:
 *   const { user, login, logout, isAuthenticated } = useAuth();
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import { Navigate } from 'react-router-dom';
import api from '../lib/axiosClient';
import { setTokens, clearTokens, getTokens, hasTokens } from '../lib/tokenStorage';

const AuthContext = createContext(null);

// ── AuthProvider ──────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [user,      setUser]      = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: restore session using stored refresh token
  useEffect(() => {
    const restore = async () => {
      if (!hasTokens()) {
        setIsLoading(false);
        return;
      }
      try {
        // axiosClient will auto-refresh the access token if needed
        const { data } = await api.get('/api/auth/profile/');
        setUser(data);
      } catch {
        clearTokens();
      } finally {
        setIsLoading(false);
      }
    };

    restore();

    // Listen for global logout events (fired by axiosClient on 401)
    const onLogout = () => setUser(null);
    window.addEventListener('auth:logout', onLogout);
    return () => window.removeEventListener('auth:logout', onLogout);
  }, []);

  // ── Login ──────────────────────────────────────────────
  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/api/auth/login/', { email, password });
    setTokens({ accessToken: data.access, refreshToken: data.refresh });
    setUser(data.user);
    return data;
  }, []);

  // ── Register ───────────────────────────────────────────
  const register = useCallback(async (fields) => {
    const { data } = await api.post('/api/auth/register/', fields);
    return data;
  }, []);

  // ── Logout (current device) ────────────────────────────
  const logout = useCallback(async () => {
    const { refreshToken } = getTokens();
    try {
      await api.post('/api/auth/logout/', { refresh: refreshToken });
    } catch {
      // Best-effort — clear locally regardless
    }
    clearTokens();
    setUser(null);
  }, []);

  // ── Logout all devices ─────────────────────────────────
  const logoutAll = useCallback(async () => {
    try {
      await api.post('/api/auth/logout-all/');
    } catch {
      /* ignore */
    }
    clearTokens();
    setUser(null);
  }, []);

  const value = {
    user,
    isLoading,
    isAuthenticated: Boolean(user),
    login,
    register,
    logout,
    logoutAll,
    setUser,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// ── useAuth hook ──────────────────────────────────────────────────
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

// ── ProtectedRoute ────────────────────────────────────────────────
export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        style={{
          display:        'flex',
          alignItems:     'center',
          justifyContent: 'center',
          height:         '100vh',
        }}
      >
        <div className="spinner" aria-label="Loading..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}