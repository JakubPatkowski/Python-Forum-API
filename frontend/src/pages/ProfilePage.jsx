import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';
import { Icon } from '../components/Icon';
import { Avatar } from '../components/Avatar';
import { SectionHead } from '../components/SectionHead';
import { TagsPanel, TopUsersPanel } from '../components/Panels';
import { LoadingState, EmptyState, ErrorState, NotSupportedTag } from '../components/States';
import { usePosts } from '../hooks/useContentQueries';
import { useSetAvatar } from '../hooks/useFiles';
import { useUserStats } from '../hooks/useEngagement';
import { timeAgo } from '../utils/format';

const TABS = ['act', 'about'];

/** Profil zalogowanego użytkownika — realne dane z /users/me + jego posty. */
export function ProfilePage() {
  const { t, lang } = useLang();
  const p = t.profile;
  const { user } = useAuth();
  const [tab, setTab] = useState(TABS[0]);

  // ProtectedRoute gwarantuje, że user istnieje, ale dla bezpieczeństwa:
  if (!user) return <div className="shell"><LoadingState /></div>;

  const tabLabels = { act: p.tabsAct, about: p.tabsAbout };

  return (
    <div className="shell">
      <ProfileHead user={user} p={p} />
      <ProfileStats userId={user.id} p={p} lang={lang} />

      <div className="profile-grid">
        <div>
          <SectionHead
            title={tabLabels[tab]}
            meta={`@${user.username}`}
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
          {tab === 'act' && <MyPosts user={user} lang={lang} t={t} />}
          {tab === 'about' && <AboutCard user={user} t={t} />}
        </div>

        <aside className="sidebar">
          <TopUsersPanel title={t.sections.trending} meta={t.sections.trendingMeta} />
          <TagsPanel title={t.sections.tags} meta={t.sections.tagsMeta} limit={8} />
        </aside>
      </div>
    </div>
  );
}

function ProfileHead({ user, p }) {
  const { t } = useLang();
  const inputRef = useRef(null);
  const setAvatar = useSetAvatar();
  const [version, setVersion] = useState(0);
  const [error, setError] = useState(null);

  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError(null);
    try {
      await setAvatar.mutateAsync(file);
      setVersion((v) => v + 1); // bust cache awatara
    } catch (err) {
      setError(err?.message ?? t.common.error);
    }
  };

  return (
    <div className="profile-head bracketed">
      <span className="br-tr" />
      <span className="br-bl" />
      <div className="profile-av-wrap">
        <Avatar userId={user.id} username={user.username} size="xl" version={version} />
        <button
          type="button"
          className="avatar-edit"
          onClick={() => inputRef.current?.click()}
          title={t.files.changeAvatar}
          disabled={setAvatar.isPending}
        >
          <Icon name="edit" size={12} />
        </button>
        <input ref={inputRef} type="file" accept="image/*" hidden onChange={onPick} />
      </div>
      <div className="profile-info">
        <h1>{user.username}</h1>
        <div className="handle">{user.email}</div>
        <div className="profile-meta">
          {(user.roles ?? []).map((r) => (
            <span className="badge accent" key={r}>{r}</span>
          ))}
          <span className={'badge ' + (user.is_active ? 'ok' : 'warn')}>
            {user.is_active ? 'active' : 'blocked'}
          </span>
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
      </div>
      <div className="profile-actions">
        <div className="uid mono dim">{shortId(user.id)}</div>
      </div>
    </div>
  );
}

function ProfileStats({ userId, p, lang }) {
  const { data, isLoading } = useUserStats(userId);
  const cell = (k, v) => (
    <div className="pstat">
      <div className="k">{k}</div>
      <div className="v">{isLoading ? '…' : v}</div>
    </div>
  );
  return (
    <div className="profile-stats">
      {cell(p.stats.posts, data?.posts_count ?? 0)}
      {cell(p.stats.comments, data?.comments_count ?? 0)}
      {cell(p.stats.likes, data?.likes_received ?? 0)}
      {cell(p.stats.joined, data?.joined_at ? fmtDate(data.joined_at) : '—')}
    </div>
  );
}

function fmtDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toISOString().slice(0, 10);
}

function MyPosts({ user, lang, t }) {
  const navigate = useNavigate();
  const query = usePosts({ author_id: user.id });

  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} onRetry={query.refetch} />;
  const posts = query.data?.items ?? [];
  if (posts.length === 0) return <EmptyState />;

  return (
    <div className="panel">
      {posts.map((post) => (
        <div
          className="activity-line clickable"
          key={post.id}
          onClick={() => navigate(`/posts/${post.id}`)}
        >
          <span className="time mono">{timeAgo(post.created_at, lang)}</span>
          <span className="what">{post.title}</span>
          <span className="kind">{post.comment_count} {t.compose.commentsTitle.toLowerCase()}</span>
        </div>
      ))}
    </div>
  );
}

function AboutCard({ user, t }) {
  return (
    <div className="card bracketed">
      <span className="br-tr" />
      <span className="br-bl" />
      <div className="about-grid">
        <AboutCell k="username" v={`@${user.username}`} />
        <AboutCell k="email" v={user.email} />
        <AboutCell k="id" v={shortId(user.id)} />
        <AboutCell k="roles" v={(user.roles ?? []).join(', ') || '—'} />
        <AboutCell
          k="permissions"
          v={`${(user.permissions ?? []).length} ${t.common.soon ? '' : ''}`.trim() || '0'}
        />
        <div>
          <div className="mono up about-k">reputation</div>
          <div className="mono about-v"><NotSupportedTag /></div>
        </div>
      </div>
    </div>
  );
}

function AboutCell({ k, v }) {
  return (
    <div>
      <div className="mono up about-k">{k}</div>
      <div className="mono about-v">{v}</div>
    </div>
  );
}

function shortId(id) {
  if (!id) return '—';
  return `UID ${id.slice(0, 8)}`;
}
