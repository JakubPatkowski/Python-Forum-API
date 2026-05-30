import { createContext, useCallback, useContext, useMemo } from 'react';
import { useLocalStorage } from '../hooks/useLocalStorage';
import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  TRANSLATIONS,
} from './translations';

const STORAGE_KEY = 'fw.lang';

const LangContext = createContext(null);

/**
 * Provider trzyma aktualny język i wystawia słownik `t` (już zwrócony dla wybranego języka),
 * żeby komponenty nie musiały same wybierać między `TRANSLATIONS.pl` a `TRANSLATIONS.en`.
 */
export function LangProvider({ children }) {
  const [lang, setLangRaw] = useLocalStorage(STORAGE_KEY, DEFAULT_LANGUAGE);

  const setLang = useCallback((next) => {
    if (SUPPORTED_LANGUAGES.includes(next)) setLangRaw(next);
  }, [setLangRaw]);

  const value = useMemo(() => ({
    lang,
    setLang,
    t: TRANSLATIONS[lang] ?? TRANSLATIONS[DEFAULT_LANGUAGE],
    supported: SUPPORTED_LANGUAGES,
  }), [lang, setLang]);

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error('useLang must be used within <LangProvider>');
  return ctx;
}

/** Skrót — najczęściej komponenty potrzebują tylko `t`. */
export function useTranslation() {
  return useLang().t;
}
