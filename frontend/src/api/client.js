import axios from 'axios';

/**
 * Centralny klient HTTP.
 *
 * Strategia sesji (bezpieczna wg dobrych praktyk):
 *  - access token trzymamy WYŁĄCZNIE w pamięci JS (zmienna modułu), nigdy w
 *    localStorage — dzięki temu nie jest wykradalny prostym XSS-em.
 *  - refresh token żyje w cookie httpOnly ustawianym przez backend (ścieżka
 *    /api/v1/auth), więc JS go nie widzi. Po twardym odświeżeniu strony
 *    odtwarzamy sesję wołając POST /auth/refresh (patrz AuthContext.bootstrap).
 *
 * Na 401 robimy pojedynczy (single-flight) refresh i ponawiamy żądanie.
 */

const BASE_URL = '/api/v1';

// --- pamięć tokenu --------------------------------------------------------- //
let accessToken = null;
// Callback rejestrowany przez AuthContext — wywoływany gdy odświeżenie sesji
// ostatecznie się nie powiedzie (czyść stan zalogowania w UI).
let onSessionExpired = null;

export function setAccessToken(token) {
  accessToken = token ?? null;
}

export function getAccessToken() {
  return accessToken;
}

export function setSessionExpiredHandler(fn) {
  onSessionExpired = fn;
}

// --- instancje ------------------------------------------------------------- //
// `api` — z interceptorami (zwykłe żądania aplikacji).
// `bare` — bez interceptora refresh (używane do samego /auth/refresh, żeby
// uniknąć nieskończonej pętli odświeżania).
export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // cookie refresh
});

export const bare = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// --- single-flight refresh ------------------------------------------------- //
let refreshPromise = null;

async function refreshAccessToken() {
  // Współdzielimy jedną obietnicę między równoległe 401, żeby nie odpalać
  // wielu rotacji refresh tokenu naraz (reuse-detection na backendzie by je ubił).
  if (!refreshPromise) {
    refreshPromise = bare
      .post('/auth/refresh')
      .then((res) => {
        const token = res.data?.access_token ?? null;
        setAccessToken(token);
        return token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error;
    if (!response || !config) return Promise.reject(normalizeError(error));

    const isAuthCall = config.url?.includes('/auth/');
    if (response.status === 401 && !config._retry && !isAuthCall) {
      config._retry = true;
      try {
        const token = await refreshAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
          return api(config);
        }
      } catch {
        /* refresh padł — przejdź do wylogowania poniżej */
      }
      setAccessToken(null);
      if (onSessionExpired) onSessionExpired();
    }
    return Promise.reject(normalizeError(error));
  },
);

// --- normalizacja błędów --------------------------------------------------- //
/**
 * Backend zwraca kopertę błędu: { error: { code, message, field } } albo
 * { detail: [...] } (walidacja FastAPI). Sprowadzamy to do jednego kształtu,
 * żeby UI miał spójny `message`/`code`/`field`.
 */
export function normalizeError(error) {
  const status = error.response?.status ?? 0;
  const data = error.response?.data;

  if (data?.error) {
    return {
      status,
      code: data.error.code ?? 'error',
      message: data.error.message ?? 'Wystąpił błąd.',
      field: data.error.field ?? null,
      raw: error,
    };
  }

  // walidacja pydantic/FastAPI (422): detail to lista obiektów
  if (Array.isArray(data?.detail)) {
    const first = data.detail[0];
    return {
      status,
      code: 'validation_error',
      message: first?.msg ?? 'Niepoprawne dane.',
      field: Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : null,
      raw: error,
    };
  }

  return {
    status,
    code: 'error',
    message:
      (typeof data?.detail === 'string' && data.detail) ||
      error.message ||
      'Wystąpił nieoczekiwany błąd.',
    field: null,
    raw: error,
  };
}
