import { NavLink } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';

/**
 * Sub-nawigacja. FORUM i PROFIL to realne trasy (NavLink — `active` z routera).
 * MAPA ŁOWISK / SPRZĘT / ARTYKUŁY / RANKINGI to placeholdery (oznaczone „wkrótce")
 * — sekcje jeszcze nie istnieją w API/routingu.
 *
 * Na mobile pasek staje się rozwijanym menu (sterowanym hamburgerem w TopBar):
 * `mobileOpen` pokazuje listę pionowo, `onNavigate` zamyka ją po kliknięciu.
 */
export function SubNav({ mobileOpen = false, onNavigate }) {
  const { t } = useLang();
  const items = [
    { to: '/', label: t.tabs.home, code: '01', end: true },
    { label: t.tabs.map, code: '02', soon: true },
    { label: t.tabs.gear, code: '03', soon: true },
    { label: t.tabs.articles, code: '04', soon: true },
    { label: t.tabs.rankings, code: '05', soon: true },
    { to: '/profile', label: t.tabs.profile, code: '06' },
  ];

  return (
    <nav className={'subnav' + (mobileOpen ? ' open' : '')}>
      <div className="shell">
        <div className="tabs">
          {items.map((it) =>
            it.soon ? (
              <span key={it.code} className="tab soon" title={t.common.soon}>
                <span className="tab-id">{it.code}</span>
                <span>{it.label}</span>
                <span className="tab-soon">{t.common.soon}</span>
              </span>
            ) : (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                onClick={onNavigate}
                className={({ isActive }) => 'tab' + (isActive ? ' active' : '')}
              >
                <span className="tab-id">{it.code}</span>
                <span>{it.label}</span>
              </NavLink>
            ),
          )}
        </div>
      </div>
    </nav>
  );
}
