import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';
import {
  usePost,
  usePosts,
  useComments,
  useDeletePost,
} from '../hooks/useContentQueries';
import { usePostFiles } from '../hooks/useFiles';
import { useLikeState, useUserStats } from '../hooks/useEngagement';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { Avatar } from '../components/Avatar';
import { ThreadGlyph } from '../components/ThreadGlyph';
import { LikeButton } from '../components/LikeButton';
import { Icon } from '../components/Icon';
import { Markdown } from '../components/Markdown';
import { Attachments } from '../components/files/Attachments';
import { CommentForm } from '../components/comments/CommentForm';
import { CommentNode } from '../components/comments/CommentNode';
import { NewPostModal } from '../components/compose/NewPostModal';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import { buildCommentTree } from '../utils/commentTree';
import { timeAgo } from '../utils/format';

/** Strona pojedynczego wątku: panel autora + treść/komentarze + meta wątku. */
export function PostPage() {
  const { id } = useParams();
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const { isAuthenticated, user, hasPermission } = useAuth();

  const postQ = usePost(id);
  const commentsQ = useComments(id);
  const filesQ = usePostFiles(id);
  const deletePost = useDeletePost();
  const [editing, setEditing] = useState(false);
  const [leftOpen, setLeftOpen] = useLocalStorage('post.leftPanel', true);
  const [rightOpen, setRightOpen] = useLocalStorage('post.rightPanel', true);

  const tree = useMemo(
    () => buildCommentTree(commentsQ.data?.items ?? []),
    [commentsQ.data],
  );

  if (postQ.isLoading) return <div className="shell"><LoadingState /></div>;
  if (postQ.isError) {
    return (
      <div className="shell">
        <ErrorState error={postQ.error} onRetry={postQ.refetch} />
      </div>
    );
  }

  const post = postQ.data;
  const isAuthor = user && post.author?.public_id === user.id;
  const canEdit = isAuthor || hasPermission('post.update.any');
  const canDelete = isAuthor || hasPermission('post.delete.any');
  const authorHref = post.author?.public_id ? `/users/${post.author.public_id}` : null;

  const onDelete = async () => {
    if (!window.confirm(t.compose.confirmDelete)) return;
    await deletePost.mutateAsync(post.id);
    navigate('/');
  };

  const layoutClass =
    'post-layout' +
    (leftOpen ? '' : ' left-collapsed') +
    (rightOpen ? '' : ' right-collapsed');

  return (
    <div className="post-wrap">
      <div className={layoutClass}>
        {/* ---- LEWY PANEL: autor + jego wątki ---- */}
        <aside className="post-side left">
          <AuthorPanel author={post.author} href={authorHref} t={t} lang={lang} />
        </aside>
        <button
          type="button"
          className="panel-collapse left"
          title={t.common.close}
          onClick={() => setLeftOpen(false)}
        >
          <Icon name="chevLeft" size={14} />
        </button>
        <button
          type="button"
          className="panel-reveal left"
          title={t.post.author}
          onClick={() => setLeftOpen(true)}
        >
          <Icon name="chevRight" size={16} />
        </button>

        {/* ---- ŚRODEK: treść + komentarze ---- */}
        <div className="post-center">
          {/* WRÓĆ wewnątrz środkowej kolumny — żeby nie pchało post-full w dół.
              Styl `position: absolute` w CSS, więc nie zajmuje pionowej przestrzeni. */}
          <Link to="/" className="link-btn post-back">← {t.common.back}</Link>
          <article className="post-full bracketed">
            <span className="br-tr" />
            <span className="br-bl" />
            <div className="post-top">
              {post.category && <span className="thread-cat">{post.category.name}</span>}
              <span className="mono dim">{timeAgo(post.created_at, lang)}</span>
              <span className="filler" />
              {canEdit && (
                <button type="button" className="link-btn" onClick={() => setEditing(true)}>
                  {t.compose.edit}
                </button>
              )}
              {canDelete && (
                <button type="button" className="link-btn danger" onClick={onDelete}>
                  {t.compose.delete}
                </button>
              )}
            </div>

            <div className="post-titlebar">
              <span className="post-glyph">
                <ThreadGlyph postId={post.id} category={post.category} name={post.title} />
              </span>
              <h1 className="post-title">{post.title}</h1>
            </div>

            <AuthorLink author={post.author} href={authorHref} className="post-author" />

            <Markdown source={post.content} format={post.content_format} className="post-content" />

            {filesQ.data?.length > 0 && <Attachments files={filesQ.data} />}

            {post.tags?.length > 0 && (
              <div className="tagline">
                {post.tags.map((tag) => (
                  <span className="taglet" key={tag.public_id ?? tag.slug}>#{tag.name}</span>
                ))}
              </div>
            )}

            <div className="post-engagement">
              <LikeButton target="posts" publicId={post.id} />
            </div>
          </article>

          <section className="comments-section">
            <h2 className="section-head-lite">
              {t.compose.commentsTitle}
              <span className="head-id">{post.comment_count ?? 0}</span>
            </h2>

            {isAuthenticated ? (
              <CommentForm postId={id} />
            ) : (
              <div className="state-box mono mute">
                <Link to="/login" className="link-btn">{t.auth.loginRequired}</Link>
              </div>
            )}

            {commentsQ.isLoading && <LoadingState />}
            {commentsQ.isError && <ErrorState error={commentsQ.error} onRetry={commentsQ.refetch} />}
            {commentsQ.isSuccess && tree.length === 0 && <EmptyState label={t.compose.noComments} />}

            <div className="comment-list">
              {tree.map((node) => (
                <CommentNode key={node.id} comment={node} postId={id} />
              ))}
            </div>
          </section>
        </div>

        {/* ---- PRAWY PANEL: meta wątku + podobne ---- */}
        <aside className="post-side right">
          <ThreadMetaPanel post={post} t={t} lang={lang} />
          <SuggestedThreads post={post} t={t} />
        </aside>
        <button
          type="button"
          className="panel-collapse right"
          title={t.common.close}
          onClick={() => setRightOpen(false)}
        >
          <Icon name="chevRight" size={14} />
        </button>
        <button
          type="button"
          className="panel-reveal right"
          title={t.post.about}
          onClick={() => setRightOpen(true)}
        >
          <Icon name="chevLeft" size={16} />
        </button>
      </div>

      {editing && <NewPostModal post={post} onClose={() => setEditing(false)} />}
    </div>
  );
}

/* ----- autor (link do publicznego profilu) ------------------------------- */

function AuthorLink({ author, href, className = '' }) {
  const inner = (
    <>
      <Avatar userId={author?.public_id} username={author?.username} size="sm" />
      <span className="author">@{author?.username ?? '???'}</span>
    </>
  );
  if (href) {
    return <Link to={href} className={className + ' author-link'}>{inner}</Link>;
  }
  return <div className={className}>{inner}</div>;
}

/* ----- lewy panel: karta autora + jego wątki ----------------------------- */

function AuthorPanel({ author, href, t, lang }) {
  const navigate = useNavigate();
  const statsQ = useUserStats(author?.public_id);
  const postsQ = usePosts(author?.public_id ? { author_id: author.public_id, limit: 5 } : {});
  const s = statsQ.data;
  const labels = t.profile.stats;
  const myPosts = (postsQ.data?.items ?? []).slice(0, 5);

  const go = () => href && navigate(href);

  return (
    <div className="author-card">
      <button type="button" className="author-card-head" onClick={go} disabled={!href}>
        <Avatar userId={author?.public_id} username={author?.username} size="xl" />
        <div className="author-name">@{author?.username ?? '???'}</div>
      </button>
      {s?.joined_at && (
        <div className="author-joined mono mute">
          {labels.joined}: {new Date(s.joined_at).toISOString().slice(0, 10)}
        </div>
      )}
      <div className="author-stats">
        <div className="author-stat">
          <div className="v">{s?.posts_count ?? '—'}</div>
          <div className="k">{labels.posts}</div>
        </div>
        <div className="author-stat">
          <div className="v">{s?.comments_count ?? '—'}</div>
          <div className="k">{labels.comments}</div>
        </div>
        <div className="author-stat">
          <div className="v">{s?.likes_received ?? '—'}</div>
          <div className="k">{labels.likes}</div>
        </div>
        <div className="author-stat">
          <div className="v">{s?.joined_at ? timeAgo(s.joined_at, lang) : '—'}</div>
          <div className="k">{labels.joined}</div>
        </div>
      </div>

      {myPosts.length > 0 && (
        <div className="author-threads">
          <div className="author-threads-head mono up">{t.profile.tabsAct}</div>
          {myPosts.map((p) => (
            <Link key={p.id} to={`/posts/${p.id}`} className="author-thread">
              <span className="suggested-glyph">
                <ThreadGlyph postId={p.id} category={p.category} name={p.title} />
              </span>
              <span className="suggested-title">{p.title}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/* ----- prawy panel: metadane wątku --------------------------------------- */

function ThreadMetaPanel({ post, t, lang }) {
  const likesQ = useLikeState('posts', post.id);

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t.post.about}</h3>
      </div>
      <div className="meta-list">
        <div className="meta-row">
          <span className="k">{t.post.created}</span>
          <span className="v">{timeAgo(post.created_at, lang)}</span>
        </div>
        {post.category && (
          <div className="meta-row">
            <span className="k">{t.post.category}</span>
            <span className="v">{post.category.name}</span>
          </div>
        )}
        <div className="meta-row">
          <span className="k">{t.post.comments}</span>
          <span className="v">{post.comment_count ?? 0}</span>
        </div>
        <div className="meta-row">
          <span className="k">{t.post.likes}</span>
          <span className="v">{likesQ.data?.count ?? 0}</span>
        </div>
      </div>
      {post.tags?.length > 0 && (
        <div className="tagline">
          {post.tags.map((tag) => (
            <span className="taglet" key={tag.public_id ?? tag.slug}>#{tag.name}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ----- prawy panel: podobne wątki ---------------------------------------- */

function SuggestedThreads({ post, t }) {
  const categoryId = post.category?.public_id ?? null;
  const q = usePosts(categoryId ? { category_id: categoryId, limit: 6 } : {});
  const items = (q.data?.items ?? [])
    .filter((p) => p.id !== post.id)
    .slice(0, 5);

  if (!categoryId) return null;

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t.post.suggested}</h3>
      </div>
      {q.isLoading && <div className="panel-body"><LoadingState /></div>}
      {q.isSuccess && items.length === 0 && (
        <div className="panel-body">
          <span className="mono mute" style={{ padding: '0 16px', fontSize: 12 }}>
            {t.post.noSuggested}
          </span>
        </div>
      )}
      <div className="suggested-list">
        {items.map((p) => (
          <Link key={p.id} to={`/posts/${p.id}`} className="suggested-item">
            <span className="suggested-glyph">
              <ThreadGlyph postId={p.id} category={p.category} name={p.title} />
            </span>
            <span className="suggested-title">{p.title}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
