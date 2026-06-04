import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Avatar } from '../components/Avatar';
import { SectionHead } from '../components/SectionHead';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import { authApi } from '../api/resources';
import { usePosts } from '../hooks/useContentQueries';
import { useUserStats } from '../hooks/useEngagement';
import { qk } from '../query/keys';
import { timeAgo } from '../utils/format';

/** Publiczny profil dowolnego użytkownika (/users/:id). */
export function UserProfilePage() {
  const { id } = useParams();
  const { t, lang } = useLang();
  const p = t.profile;

  const userQ = useQuery({
    queryKey: qk.users.detail(id),
    queryFn: () => authApi.userById(id),
    enabled: Boolean(id),
  });
  const statsQ = useUserStats(id);

  if (userQ.isLoading) return <div className="shell"><LoadingState /></div>;
  if (userQ.isError) {
    return (
      <div className="shell">
        <ErrorState error={userQ.error} onRetry={userQ.refetch} />
      </div>
    );
  }

  const u = userQ.data;
  const s = statsQ.data;

  return (
    <div className="shell">
      <Link to="/" className="link-btn post-back">← {t.common.back}</Link>

      <div className="profile-head bracketed">
        <span className="br-tr" />
        <span className="br-bl" />
        <div className="profile-av-wrap">
          <Avatar userId={u.public_id ?? id} username={u.username} size="xl" />
        </div>
        <div className="profile-info">
          <h1>{u.username}</h1>
          <div className="handle">@{u.username}</div>
          <div className="profile-meta">
            {(u.roles ?? []).map((r) => (
              <span className="badge accent" key={r}>{r}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="profile-stats">
        <Stat k={p.stats.posts} v={s?.posts_count ?? 0} />
        <Stat k={p.stats.comments} v={s?.comments_count ?? 0} />
        <Stat k={p.stats.likes} v={s?.likes_received ?? 0} />
        <Stat
          k={p.stats.joined}
          v={s?.joined_at ? new Date(s.joined_at).toISOString().slice(0, 10) : '—'}
        />
      </div>

      <SectionHead title={p.tabsAct} meta={`@${u.username}`} />
      <UserThreads userId={u.public_id ?? id} lang={lang} t={t} />
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

function UserThreads({ userId, lang, t }) {
  const navigate = useNavigate();
  const query = usePosts({ author_id: userId });

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
          <span className="kind">
            {post.comment_count} {t.compose.commentsTitle.toLowerCase()}
          </span>
        </div>
      ))}
    </div>
  );
}
