/**
 * frontend/web/src/lib/tokenStorage.js
 *
 * Secure token storage strategy:
 *
 *   Access token  → sessionStorage only
 *                   Survives page refresh (F5), lost on tab close.
 *                   NOT accessible across tabs.
 *                   Never in localStorage (reduces XSS exposure window).
 *
 *   Refresh token → localStorage
 *                   Survives browser close (enables "remember me").
 *                   Set USE_COOKIE_REFRESH=true if your backend sets
 *                   an httpOnly cookie — the cookie is sent automatically
 *                   and you don't need to store the refresh token at all.
 *
 * In-memory copies (_accessToken / _refreshToken) are always used by
 * axiosClient — storage is only for persistence across page loads.
 */

const USE_COOKIE_REFRESH = false;

let _accessToken  = null;
let _refreshToken = null;

// Restore on page load
if (typeof window !== 'undefined') {
  _accessToken  = sessionStorage.getItem('_at') || null;
  _refreshToken = USE_COOKIE_REFRESH
    ? null
    : localStorage.getItem('_rt') || null;
}

export function getTokens() {
  return { accessToken: _accessToken, refreshToken: _refreshToken };
}

export function setTokens({ accessToken, refreshToken }) {
  _accessToken  = accessToken  ?? _accessToken;
  _refreshToken = refreshToken ?? _refreshToken;

  if (typeof window === 'undefined') return;

  if (accessToken != null) sessionStorage.setItem('_at', accessToken);
  else                     sessionStorage.removeItem('_at');

  if (!USE_COOKIE_REFRESH) {
    if (refreshToken != null) localStorage.setItem('_rt', refreshToken);
    else                      localStorage.removeItem('_rt');
  }
}

export function clearTokens() {
  _accessToken  = null;
  _refreshToken = null;
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem('_at');
  localStorage.removeItem('_rt');
}

export function hasTokens() {
  return Boolean(_accessToken || _refreshToken);
}