import { createContext, useCallback, useContext, useEffect, useMemo } from 'react';
import { useLocalStorage } from '../hooks/useLocalStorage';

const STORAGE_KEY = 'fw.theme';
const THEMES = ['dark', 'light'];

const ThemeContext = createContext(null);

/**
 * Provider trzyma motyw (dark/light) i synchronizuje atrybut `data-theme` na <html>,
 * z którego korzystają zmienne CSS w `styles/globals.css`.
 */
export function ThemeProvider({ children }) {
  const [theme, setThemeRaw] = useLocalStorage(STORAGE_KEY, 'dark');

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (THEMES.includes(next)) setThemeRaw(next);
  }, [setThemeRaw]);

  const toggleTheme = useCallback(() => {
    setThemeRaw((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, [setThemeRaw]);

  const value = useMemo(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>');
  return ctx;
}
