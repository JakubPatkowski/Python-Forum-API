import { QueryClient } from '@tanstack/react-query';

/**
 * Globalna konfiguracja React Query.
 *
 * - `staleTime` 30s: dane uznajemy za świeże przez pół minuty, więc przejścia
 *   między widokami nie odpalają zbędnych GET-ów (Twoja zasada: pobierać tylko
 *   to, co potrzebne). Gdy dojdzie WebSocket, świeżość wymuszać będziemy
 *   inwalidacją po konkretnym kluczu, a nie skracaniem czasu.
 * - 401 nie ponawiamy (refresh i tak obsługuje interceptor); inne błędy 1x.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error?.status === 401 || error?.status === 403) return false;
        return failureCount < 1;
      },
    },
    mutations: {
      retry: false,
    },
  },
});
