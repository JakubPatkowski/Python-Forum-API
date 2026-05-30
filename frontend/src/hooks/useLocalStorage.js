import { useCallback, useEffect, useState } from 'react';

/**
 * Stan zsynchronizowany z localStorage. Bezpieczny dla SSR (sprawdza `window`).
 * Wartości są serializowane jako JSON, więc działa dla stringów, liczb, obiektów.
 */
export function useLocalStorage(key, initialValue) {
  const readValue = useCallback(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const raw = window.localStorage.getItem(key);
      if (raw === null) return initialValue;
      return JSON.parse(raw);
    } catch {
      // jeśli ktoś zapisał gołego stringa (np. ze starszej wersji szablonu) — zwróć surową wartość
      return window.localStorage.getItem(key) ?? initialValue;
    }
  }, [key, initialValue]);

  const [value, setValue] = useState(readValue);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* quota / private mode — milcząco ignorujemy */
    }
  }, [key, value]);

  return [value, setValue];
}
