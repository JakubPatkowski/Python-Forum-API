import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  bare,
  setAccessToken,
  setSessionExpiredHandler,
} from '../api/client';
import { authApi } from '../api/resources';
import { normalizeError } from '../api/client';

/**
 * Źródło prawdy o sesji użytkownika.
 *
 * status:
 *   'loading'        – trwa próba odtworzenia sesji z cookie refresh
 *   'authenticated'  – mamy access token + profil użytkownika
 *   'anonymous'      – brak sesji
 *
 * Access token żyje w pamięci (client.js). Po odświeżeniu strony bootstrap
 * woła /auth/refresh (cookie httpOnly) i jeśli się uda, dociąga /users/me.
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState('loading');
  const [user, setUser] = useState(null);
  const bootstrapped = useRef(false);

  const applyUser = useCallback((profile) => {
    setUser(profile);
    setStatus(profile ? 'authenticated' : 'anonymous');
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus('anonymous');
    qc.clear(); // dane prywatne nie powinny zostać w cache po wylogowaniu
  }, [qc]);

  // Gdy interceptor ostatecznie nie odświeży sesji — sprzątamy stan UI
  // ORAZ cache zapytań (żeby prywatne dane nie zostały w pamięci po wygaśnięciu).
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setStatus('anonymous');
      qc.clear();
    });
    return () => setSessionExpiredHandler(null);
  }, [qc]);

  // Bootstrap: spróbuj odtworzyć sesję raz, przy starcie aplikacji.
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    (async () => {
      try {
        const res = await bare.post('/auth/refresh');
        const token = res.data?.access_token;
        if (!token) throw new Error('no token');
        setAccessToken(token);
        const profile = await authApi.me();
        applyUser(profile);
      } catch {
        clearSession();
        setStatus('anonymous');
      }
    })();
  }, [applyUser, clearSession]);

  const login = useCallback(
    async ({ login: loginField, password }) => {
      try {
        const tokens = await authApi.login({ login: loginField, password });
        setAccessToken(tokens.access_token);
        const profile = await authApi.me();
        applyUser(profile);
        return { ok: true };
      } catch (error) {
        const e = error.code ? error : normalizeError(error);
        return { ok: false, error: e };
      }
    },
    [applyUser],
  );

  const register = useCallback(
    async ({ username, email, password }) => {
      try {
        await authApi.register({ username, email, password });
        // backend zwraca profil (bez tokenów) — logujemy automatycznie
        return await login({ login: username, password });
      } catch (error) {
        const e = error.code ? error : normalizeError(error);
        return { ok: false, error: e };
      }
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* nawet jeśli backend zawiedzie, czyścimy stan lokalnie */
    }
    clearSession();
  }, [clearSession]);

  const permissions = useMemo(
    () => new Set(user?.permissions ?? []),
    [user],
  );
  const roles = useMemo(() => new Set(user?.roles ?? []), [user]);

  const hasPermission = useCallback(
    (code) => permissions.has(code),
    [permissions],
  );
  const hasRole = useCallback((role) => roles.has(role), [roles]);

  const value = useMemo(
    () => ({
      status,
      user,
      isAuthenticated: status === 'authenticated',
      isLoading: status === 'loading',
      login,
      register,
      logout,
      hasPermission,
      hasRole,
    }),
    [status, user, login, register, logout, hasPermission, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
