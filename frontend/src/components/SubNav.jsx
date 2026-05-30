import { NavLink } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';

/**
 * Sub-nawigacja używa React Router `NavLink` — `active` jest zarządzany przez router,
 * dzięki czemu URL = stan widoku (back/forward, refresh, linki).
 */
export function SubNav() {
  const { t } = useLang();
  const items = [
    { to: '/',         label: t.tabs.home,     code: '01', end: true },
    { to: '/profile',  label: t.tabs.profile,  code: '02' },
    { to: '/opinions', label: t.tabs.opinions, code: '03' },
  ];

  return (
    <nav className="subnav">
      <div className="shell">
        <div className="tabs">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) => 'tab' + (isActive ? ' active' : '')}
            >
              <span className="tab-id">{it.code}</span>
              <span>{it.label}</span>
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
