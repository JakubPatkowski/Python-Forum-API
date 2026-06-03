import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { TopBar } from './TopBar';
import { SubNav } from './SubNav';
import { Footer } from './Footer';

/**
 * Główny layout aplikacji. Renderuje stałe elementy chrome
 * (TopBar/SubNav/Footer) i podstawia trasowany widok przez `<Outlet />`.
 *
 * `key` na <main> wymusza fade-in przy zmianie języka lub trasy,
 * co jest częścią designu (klasa `fade-key` w CSS).
 */
export function Layout() {
  const { lang } = useLang();
  const { pathname } = useLocation();
  const [navOpen, setNavOpen] = useState(false);

  // Zamknij mobilne menu po zmianie trasy.
  useEffect(() => setNavOpen(false), [pathname]);

  return (
    <div className="app">
      <TopBar navOpen={navOpen} onToggleNav={() => setNavOpen((o) => !o)} />
      <SubNav mobileOpen={navOpen} onNavigate={() => setNavOpen(false)} />
      <main className="view fade-key" key={`${pathname}_${lang}`}>
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
