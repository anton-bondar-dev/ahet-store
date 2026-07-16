import axios from 'axios';
import {
  clearAuth,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
} from '../lib/authToken';
import { getImpersonationToken, stopImpersonation } from '../lib/impersonation';
import { getSessionId } from '../lib/session';

// Single source of truth for the backend origin.
export const API_BASE_URL = 'http://127.0.0.1:8000';

// The Orval-generated client calls the global axios instance with relative
// paths (e.g. `/api/catalog/products`), so we set the backend origin here once.
axios.defaults.baseURL = API_BASE_URL;

// Attach the anonymous cart session id (always) and the JWT access token (when
// logged in) to every request.
axios.interceptors.request.use((config) => {
  config.headers.set('X-Session-Id', getSessionId());
  // While impersonating, the scoped storefront token wins so the app runs as
  // the customer; otherwise use the staff/customer's own access token.
  const token = getImpersonationToken() ?? getAccessToken();
  if (token) config.headers.set('Authorization', `Bearer ${token}`);
  return config;
});

// On a 401, try a single silent refresh and replay the request; if that fails,
// the session is truly gone → clear auth (AuthContext resets to logged-out).
let refreshing: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  if (!refreshing) {
    refreshing = axios
      .post('/api/auth/refresh', { refresh })
      .then((res) => {
        const access = res.data.access as string;
        setAccessToken(access);
        return access;
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url: string = original?.url ?? '';
    // An expired impersonation token → drop impersonation and fall back to the
    // staff session rather than trying to refresh a token that has no refresh.
    if (status === 401 && getImpersonationToken()) {
      stopImpersonation();
      return Promise.reject(error);
    }
    if (
      status === 401 &&
      original &&
      !original._retried &&
      !url.includes('/auth/refresh') &&
      !url.includes('/auth/login') &&
      !url.includes('/auth/register')
    ) {
      original._retried = true;
      const access = await refreshAccess();
      if (access) {
        original.headers = original.headers ?? {};
        original.headers['Authorization'] = `Bearer ${access}`;
        return axios(original);
      }
      clearAuth();
    }
    return Promise.reject(error);
  },
);

// Build an absolute URL for a media path returned by the API
// (e.g. "/media/products/images/x.jpg"). Returns null when there's no image.
export function productImageUrl(image: string | null): string | null {
  if (!image) return null;
  return image.startsWith('http') ? image : `${API_BASE_URL}${image}`;
}
