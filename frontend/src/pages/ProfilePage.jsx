import { useState } from 'react';
import { useTranslation } from '../i18n/LangContext';
import { Icon } from '../components/Icon';
import { SectionHead } from '../components/SectionHead';
import { TopUsersPanel, TagsPanel } from './HomePage';

const TABS = ['act', 'about', 'badges'];

export function ProfilePage() {
  const t = useTranslation();
  const p = t.profile;
  const [tab, setTab] = useState(TABS[0]);

  const tabLabels = { act: p.tabsAct, about: p.tabsAbout, badges: p.tabsBadges };

  return (
    <div className="shell">
      <ProfileHead p={p} />
      <ProfileStats stats={p.stats} />

      <div className="profile-grid">
        <div>
          <SectionHead
            title={tabLabels[tab]}
            meta="UID 0xA482"
            right={
              <div className="seg" style={{ height: 32 }}>
                {TABS.map((id) => (
                  <button
                    key={id}
                    type="button"
                    className={tab === id ? 'on' : ''}
                    onClick={() => setTab(id)}
                  >
                    {tabLabels[id]}
                  </button>
                ))}
              </div>
            }
          />
          {tab === 'act'    && <ActivityPanel activity={p.activity} />}
          {tab === 'about'  && <AboutCard p={p} />}
          {tab === 'badges' && <BadgesPanel badges={p.badges} />}
        </div>

        <aside className="sidebar">
          <TopUsersPanel
            title={t.sections.trending}
            meta={t.sections.trendingMeta}
            users={t.topUsers.slice(0, 4)}
          />
          <TagsPanel
            title={t.sections.tags}
            meta={t.sections.tagsMeta}
            tags={t.tags.slice(0, 8)}
          />
        </aside>
      </div>
    </div>
  );
}

function ProfileHead({ p }) {
  return (
    <div className="profile-head bracketed">
      <span className="br-tr" />
      <span className="br-bl" />
      <div className="profile-av">JP</div>
      <div className="profile-info">
        <h1>{p.name}</h1>
        <div className="handle">{p.handle}</div>
        <div className="profile-meta">
          <span className="badge accent">{p.role}</span>
          <span className="badge">⌖ {p.location}</span>
          <span className="badge">{p.specialty}</span>
        </div>
      </div>
      <div className="profile-actions">
        <div className="uid">{p.uid}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" className="btn">
            <Icon name="mail" size={12} /> {p.message}
          </button>
          <button type="button" className="btn primary">
            <Icon name="edit" size={12} /> {p.edit}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProfileStats({ stats }) {
  return (
    <div className="profile-stats">
      <Stat k={stats.posts}     v="1 482" />
      <Stat k={stats.threads}   v="37" />
      <Stat k={stats.reactions} v={<>3 921 <span className="small">↑ 124 / 30d</span></>} />
      <Stat k={stats.rep}       v={<>8.7 <span className="small">/ 10.0</span></>} />
    </div>
  );
}

function Stat({ k, v }) {
  return (
    <div className="pstat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}

function ActivityPanel({ activity }) {
  return (
    <div className="panel">
      {activity.map((a, i) => (
        // Treść `a.html` pochodzi ze statycznego słownika i18n (zaufane źródło).
        // W przyszłości, gdy aktywność będzie z backendu, należy przejść na strukturalny model
        // (np. tablica tokenów) zamiast surowego HTML.
        // eslint-disable-next-line react/no-array-index-key
        <div className="activity-line" key={i}>
          <span className="time mono">{a.time}</span>
          <span
            className="what"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: a.html }}
          />
          <span className="kind">{a.kind}</span>
        </div>
      ))}
    </div>
  );
}

function AboutCard({ p }) {
  return (
    <div className="card bracketed">
      <span className="br-tr" />
      <span className="br-bl" />
      <p
        style={{
          margin: 0,
          fontSize: 14,
          lineHeight: 1.7,
          color: 'var(--text-dim)',
          maxWidth: '70ch',
        }}
      >
        {p.about}
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 24,
          marginTop: 24,
          paddingTop: 24,
          borderTop: '1px dashed var(--border)',
        }}
      >
        <AboutCell k={p.side.joined} v="2024.03.14" />
        <AboutCell k={p.side.last}   v="14:22 UTC+1" />
        <AboutCell k="specialty"     v={p.specialty} />
      </div>
    </div>
  );
}

function AboutCell({ k, v }) {
  return (
    <div>
      <div className="mono up" style={{ fontSize: 10, color: 'var(--text-mute)' }}>
        {k}
      </div>
      <div className="mono" style={{ fontSize: 14, marginTop: 6 }}>
        {v}
      </div>
    </div>
  );
}

function BadgesPanel({ badges }) {
  return (
    <div className="panel">
      <div className="badge-grid">
        {badges.map((b) => (
          <div
            key={b.name}
            className={'badge-cell' + (b.unlocked ? '' : ' locked')}
          >
            <div className="badge-icon">{b.code}</div>
            <div className="badge-name">{b.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
