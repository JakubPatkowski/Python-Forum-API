import { useRef, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { useClickOutside } from '../hooks/useClickOutside';
import { Icon } from './Icon';

/**
 * Pasek nawigacyjny u góry: logo, search, przełącznik języka i motywu,
 * powiadomienia, wiadomości, menu profilu.
 *
 * Stan UI (otwarte menu) trzymany lokalnie — globalne preferencje
 * (lang/theme) pobierane z kontekstów.
 */
export function TopBar() {
  const { t, lang, setLang } = useLang();
  const { theme, toggleTheme } = useTheme();

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  useClickOutside(menuRef, () => setMenuOpen(false), menuOpen);

  const [brandFirst, brandSecond] = t.brand.split('://');

  return (
    <header className="topbar">
      <div className="shell row">
        <div className="logo">
          <div className="logo-mark" aria-hidden="true" />
          <div className="logo-text fade-key" key={lang}>
            {brandFirst}
            <span>://</span>
            {brandSecond}
          </div>
        </div>

        <label className="search">
          <Icon name="search" />
          <input placeholder={t.search} />
          <kbd>⌘K</kbd>
        </label>

        <div className="controls">
          <div className="seg" role="group" aria-label="language">
            <button
              type="button"
              className={lang === 'pl' ? 'on' : ''}
              onClick={() => setLang('pl')}
            >
              PL
            </button>
            <button
              type="button"
              className={lang === 'en' ? 'on' : ''}
              onClick={() => setLang('en')}
            >
              EN
            </button>
          </div>

          <button
            type="button"
            className="icon-btn"
            onClick={toggleTheme}
            aria-label="theme"
            title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>

          <button type="button" className="icon-btn" aria-label="notifications">
            <Icon name="bell" />
            <span className="dot" />
          </button>

          <button type="button" className="icon-btn" aria-label="messages">
            <Icon name="mail" />
          </button>

          <div style={{ position: 'relative' }} ref={menuRef}>
            <button
              type="button"
              className="avatar-btn"
              onClick={() => setMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <div className="avatar">JP</div>
              <span className="avatar-name">kuba_p</span>
              <Icon name="chev" size={12} />
            </button>
            {menuOpen && <UserMenu t={t} />}
          </div>
        </div>
      </div>
    </header>
  );
}

function UserMenu({ t }) {
  return (
    <div className="menu" role="menu">
      <div className="menu-head">
        <div className="mono up" style={{ fontSize: 10, color: 'var(--text-mute)' }}>
          {t.menu.signedAs}
        </div>
        <div style={{ fontSize: 13, marginTop: 4 }}>Jakub Patkowski</div>
        <div className="mono dim" style={{ fontSize: 11, marginTop: 2 }}>
          kuba_p@forum.local
        </div>
      </div>
      <MenuItem icon="user"   label={t.menu.profile}  shortcut="P" />
      <MenuItem icon="gear"   label={t.menu.settings} shortcut="," />
      <MenuItem icon="doc"    label={t.menu.drafts}   shortcut="D" />
      <MenuItem icon="bm"     label={t.menu.saved}    shortcut="S" />
      <MenuItem icon="logout" label={t.menu.logout}   shortcut="⇧Q" danger />
    </div>
  );
}

function MenuItem({ icon, label, shortcut, danger = false }) {
  return (
    <div className={'menu-item' + (danger ? ' danger' : '')} role="menuitem">
      <Icon name={icon} /> {label}
      <span className="key">{shortcut}</span>
    </div>
  );
}
