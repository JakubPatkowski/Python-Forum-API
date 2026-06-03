import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';
import { useClickOutside } from '../hooks/useClickOutside';
import { Avatar } from './Avatar';
import { Icon } from './Icon';

/**
 * Pasek nawigacyjny u góry. Prawa strona zależy od stanu sesji:
 *  - anonim  → przycisk „Zaloguj”
 *  - zalogowany → avatar (inicjały z username) + menu z wylogowaniem
 *
 * Stan UI (otwarte menu) trzymany lokalnie; preferencje (lang/theme) z kontekstów;
 * sesja z AuthContext.
 */
export function TopBar({ navOpen = false, onToggleNav }) {
  const { t, lang, setLang } = useLang();
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, user } = useAuth();

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  useClickOutside(menuRef, () => setMenuOpen(false), menuOpen);

  const [brandFirst, brandSecond] = t.brand.split('://');

  return (
    <header className="topbar">
      <div className="shell row">
        <button
          type="button"
          className="hamburger"
          onClick={onToggleNav}
          aria-label="menu"
          aria-expanded={navOpen}
        >
          <Icon name={navOpen ? 'close' : 'menu'} size={18} />
        </button>

        <Link to="/" className="logo" style={{ textDecoration: 'none' }}>
          <div className="logo-mark" aria-hidden="true" />
          <div className="logo-text fade-key" key={lang}>
            {brandFirst}
            <span>://</span>
            {brandSecond}
          </div>
        </Link>

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

          {isAuthenticated ? (
            <>
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
                  <Avatar userId={user?.id} username={user?.username} size="sm" />
                  <span className="avatar-name">{user?.username}</span>
                  <Icon name="chev" size={12} />
                </button>
                {menuOpen && (
                  <UserMenu
                    t={t}
                    user={user}
                    onClose={() => setMenuOpen(false)}
                  />
                )}
              </div>
            </>
          ) : (
            <Link to="/login" className="btn primary">
              {t.menu.login}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

function initials(username) {
  if (!username) return '??';
  return username.slice(0, 2).toUpperCase();
}

function UserMenu({ t, user, onClose }) {
  const navigate = useNavigate();
  const { logout, hasPermission } = useAuth();
  const isAdmin = hasPermission('user.read.any');

  const handleLogout = async () => {
    onClose();
    await logout();
    navigate('/');
  };

  return (
    <div className="menu" role="menu">
      <div className="menu-head">
        <div className="mono up" style={{ fontSize: 10, color: 'var(--text-mute)' }}>
          {t.menu.signedAs}
        </div>
        <div style={{ fontSize: 13, marginTop: 4 }}>{user?.username}</div>
        <div className="mono dim" style={{ fontSize: 11, marginTop: 2 }}>
          {user?.email}
        </div>
      </div>
      <div
        className="menu-item"
        role="menuitem"
        onClick={() => {
          onClose();
          navigate('/profile');
        }}
      >
        <Icon name="user" /> {t.menu.profile}
        <span className="key">P</span>
      </div>
      {isAdmin && (
        <div
          className="menu-item"
          role="menuitem"
          onClick={() => {
            onClose();
            navigate('/admin');
          }}
        >
          <Icon name="gear" /> {t.admin.menu}
        </div>
      )}
      <div
        className="menu-item danger"
        role="menuitem"
        onClick={handleLogout}
      >
        <Icon name="logout" /> {t.menu.logout}
        <span className="key">⇧Q</span>
      </div>
    </div>
  );
}
