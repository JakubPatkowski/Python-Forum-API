import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';
import { Icon } from '../components/Icon';
import { SectionHead } from '../components/SectionHead';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import { NewPostModal } from '../components/compose/NewPostModal';
import { Avatar } from '../components/Avatar';
import { useCategories, useInfinitePosts } from '../hooks/useContentQueries';
import { excerptOf, timeAgo } from '../utils/format';

/**
 * Przeglądarka wątków z filtrem kategorii (keyset „pokaż więcej”).
 * Pierwotny szablon „opinii/ocen” nie ma odpowiednika w API (brak modelu
 * recenzji), więc renderujemy realne posty jako karty.
 */
export function OpinionsPage() {
  const { t, lang } = useLang();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [categoryId, setCategoryId] = useState(null);
  const [composing, setComposing] = useState(false);

  const categoriesQ = useCategories();
  const postsQ = useInfinitePosts(categoryId ? { category_id: categoryId } : {});
  const posts = postsQ.data?.pages.flatMap((p) => p.items) ?? [];

  const openCompose = () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setComposing(true);
  };

  return (
    <div className="shell">
      <SectionHead title={t.opinions.title} meta={t.opinions.meta} />

      <div className="opinions-head">
        <div className="pill-row">
          <button
            type="button"
            className={'pill' + (categoryId === null ? ' on' : '')}
            onClick={() => setCategoryId(null)}
          >
            {t.opinions.filters?.[0] ?? 'All'}
          </button>
          {(categoriesQ.data ?? []).map((c) => (
            <button
              key={c.id}
              type="button"
              className={'pill' + (categoryId === c.id ? ' on' : '')}
              onClick={() => setCategoryId(c.id)}
            >
              {c.name}
            </button>
          ))}
        </div>
        <span className="filler" />
        <button type="button" className="btn primary" onClick={openCompose}>
          <Icon name="plus" size={12} /> {t.compose.newPost}
        </button>
      </div>

      {postsQ.isLoading && <LoadingState />}
      {postsQ.isError && <ErrorState error={postsQ.error} onRetry={postsQ.refetch} />}
      {postsQ.isSuccess && posts.length === 0 && <EmptyState />}

      <div className="opinions-grid">
        {posts.map((p) => (
          <PostCard key={p.id} post={p} lang={lang} t={t} />
        ))}
      </div>

      {postsQ.hasNextPage && (
        <div className="center-row">
          <button
            type="button"
            className="btn"
            onClick={() => postsQ.fetchNextPage()}
            disabled={postsQ.isFetchingNextPage}
          >
            {postsQ.isFetchingNextPage ? t.common.loading : t.common.retry}
          </button>
        </div>
      )}

      {composing && <NewPostModal onClose={() => setComposing(false)} />}
    </div>
  );
}

function PostCard({ post, lang, t }) {
  const navigate = useNavigate();
  return (
    <div
      className="review clickable"
      onClick={() => navigate(`/posts/${post.id}`)}
      role="link"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && navigate(`/posts/${post.id}`)}
    >
      <div className="review-body">
        <div className="review-meta">
          {post.category && <span className="cat">{post.category.name}</span>}
          <span>·</span>
          <span>{timeAgo(post.created_at, lang)}</span>
        </div>
        <h3>{post.title}</h3>
        <p className="quote">{excerptOf(post.content, 160)}</p>
        <div className="review-foot">
          <div className="review-author">
            <Avatar userId={post.author?.public_id} username={post.author?.username} size="sm" />
            <span>@{post.author?.username ?? '???'}</span>
          </div>
          <span className="badge">
            {post.comment_count} {t.compose.commentsTitle.toLowerCase()}
          </span>
        </div>
      </div>
    </div>
  );
}
