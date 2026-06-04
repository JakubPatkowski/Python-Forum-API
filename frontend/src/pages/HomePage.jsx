import { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CategoryGlyph } from '../components/CategoryGlyph';
import { ThreadGlyph } from '../components/ThreadGlyph';
import { useLang } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';
import { Icon } from '../components/Icon';
import { SectionHead } from '../components/SectionHead';
import { TagsPanel, TopUsersPanel } from '../components/Panels';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import { NewPostModal } from '../components/compose/NewPostModal';
import { NewCategoryModal } from '../components/compose/NewCategoryModal';
import { useCategories, useDeleteCategory, usePost, usePosts } from '../hooks/useContentQueries';
import { useSetCategoryImage } from '../hooks/useFiles';
import { useFeaturedPost, useLikeState } from '../hooks/useEngagement';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { timeAgo, excerptOf } from '../utils/format';

export function HomePage() {
  const { t, lang } = useLang();
  const { isAuthenticated, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [selectedCategory, setSelectedCategory] = useState(null);
  const [composing, setComposing] = useState(null); // 'post' | 'category' | null
  // Stan paneli bocznych (tylko szerokie ekrany) — zapamiętany w localStorage.
  const [leftOpen, setLeftOpen] = useLocalStorage('home.leftPanel', true);
  const [rightOpen, setRightOpen] = useLocalStorage('home.rightPanel', true);

  const categoriesQ = useCategories();
  const postsQ = usePosts(
    selectedCategory ? { category_id: selectedCategory } : {},
  );
  const posts = postsQ.data?.items ?? [];
  // „Wątek tygodnia" = najczęściej polubiony (a nie najnowszy). Gdy brak
  // polubień / danych — fallback na najnowszy z listy.
  const featuredQ = useFeaturedPost(selectedCategory);
  const featuredPostQ = usePost(featuredQ.data?.post_id);
  const featured = featuredPostQ.data ?? posts[0] ?? null;

  const openCompose = (kind) => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setComposing(kind);
  };

  const categories = categoriesQ.data ?? [];
  const selectedName =
    categories.find((c) => c.id === selectedCategory)?.name ?? null;

  // Kategoria do nagłówka: wybrana, a przy „Wszystko" — najaktywniejsza
  // (najczęściej występująca wśród załadowanych wątków).
  const { bannerCategory, bannerIsMostActive } = useMemo(() => {
    if (selectedCategory) {
      return {
        bannerCategory: categories.find((c) => c.id === selectedCategory) ?? null,
        bannerIsMostActive: false,
      };
    }
    const counts = {};
    for (const p of posts) {
      const id = p.category?.public_id;
      if (id) counts[id] = (counts[id] ?? 0) + 1;
    }
    let bestId = null;
    let best = 0;
    for (const [id, n] of Object.entries(counts)) {
      if (n > best) {
        best = n;
        bestId = id;
      }
    }
    return {
      bannerCategory: bestId ? categories.find((c) => c.id === bestId) ?? null : null,
      bannerIsMostActive: Boolean(bestId),
    };
  }, [categories, selectedCategory, posts]);

  const layoutClass =
    'home-layout' +
    (leftOpen ? '' : ' left-collapsed') +
    (rightOpen ? '' : ' right-collapsed');

  return (
    <div className="home-wrap">
      <div className={layoutClass}>
        {/* ---- LEWY PANEL: kategorie ---- */}
        <aside className="home-left">
          <CategoryPanel
            query={categoriesQ}
            selected={selectedCategory}
            onSelect={(id) => setSelectedCategory((cur) => (cur === id ? null : id))}
            canCreate={isAuthenticated && hasPermission('category.create')}
            onNewCategory={() => openCompose('category')}
          />
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
          title={t.sections.categories}
          onClick={() => setLeftOpen(true)}
        >
          <Icon name="chevRight" size={16} />
        </button>

        {/* ---- ŚRODEK: nagłówek kategorii + wątek tygodnia + lista ---- */}
        <div className="home-center">
          <CategoryBanner
            category={bannerCategory}
            isMostActive={bannerIsMostActive}
            t={t}
          />

          <Hero
            t={t}
            lang={lang}
            featured={featured}
            onRead={(id) => navigate(`/posts/${id}`)}
          />

          <SectionHead
            title={selectedName ?? t.sections.latest}
            meta={t.sections.latestMeta}
            right={
              <button type="button" className="btn" onClick={() => openCompose('post')}>
                <Icon name="plus" size={12} /> {t.compose.newPost}
              </button>
            }
          />
          <ThreadList query={postsQ} lang={lang} t={t} />
        </div>

        {/* ---- PRAWY PANEL: top użytkownicy + tagi ---- */}
        <aside className="home-right">
          <TopUsersPanel title={t.sections.trending} meta={t.sections.trendingMeta} />
          <TagsPanel title={t.sections.tags} meta={t.sections.tagsMeta} />
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
          title={t.sections.trending}
          onClick={() => setRightOpen(true)}
        >
          <Icon name="chevLeft" size={16} />
        </button>
      </div>

      {composing === 'post' && (
        <NewPostModal
          onClose={() => setComposing(null)}
          defaultCategoryId={selectedCategory ?? ''}
        />
      )}
      {composing === 'category' && (
        <NewCategoryModal onClose={() => setComposing(null)} />
      )}
    </div>
  );
}

/* ----- lewy panel: pionowa lista kategorii -------------------------------- */

function CategoryPanel({ query, selected, onSelect, canCreate, onNewCategory }) {
  const { t } = useLang();

  return (
    <div className="side-panel">
      <div className="side-panel-head">
        <span className="mono up">{t.sections.categories}</span>
        {canCreate && (
          <button
            type="button"
            className="side-add"
            title={t.compose.newCategory}
            onClick={onNewCategory}
          >
            <Icon name="plus" size={12} />
          </button>
        )}
      </div>

      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState error={query.error} onRetry={query.refetch} />}

      {query.isSuccess && (
        <div className="cat-list">
          <button
            type="button"
            className={'cat-row' + (selected === null ? ' on' : '')}
            onClick={() => onSelect(null)}
          >
            <span className="cat-row-glyph all">★</span>
            <span className="cat-row-name">
              {t.opinions?.filters?.[0] ?? 'Wszystko'}
            </span>
          </button>

          {query.data.length === 0 && <EmptyState />}
          {query.data.map((c) => (
            <CategoryRow
              key={c.id}
              category={c}
              active={selected === c.id}
              onSelect={() => onSelect(c.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CategoryRow({ category: c, active, onSelect }) {
  const { t } = useLang();
  const { user, hasPermission } = useAuth();
  const setImage = useSetCategoryImage();
  const deleteCategory = useDeleteCategory();
  const inputRef = useRef(null);
  const [ver, setVer] = useState(0);

  const isOwner = user && c.owner_id && c.owner_id === user.id;
  const canSetImage = isOwner || hasPermission('category.manage');
  const canDelete = hasPermission('category.manage');

  const onPickImage = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    await setImage.mutateAsync({ categoryId: c.id, file });
    setVer((v) => v + 1); // bust cache ikony
  };

  return (
    <div className={'cat-row' + (active ? ' on' : '')}>
      <button
        type="button"
        className="cat-row-main"
        onClick={onSelect}
        title={c.description || c.name}
      >
        <span className="cat-row-glyph">
          <CategoryGlyph categoryId={c.id} name={c.name} version={ver} />
        </span>
        <span className="cat-row-name">{c.name}</span>
      </button>

      <span className="cat-row-actions">
        {canSetImage && (
          <button
            type="button"
            className="cat-chip-edit"
            title={t.files.image}
            onClick={() => inputRef.current?.click()}
            disabled={setImage.isPending}
          >
            <Icon name="edit" size={11} />
          </button>
        )}
        {canDelete && (
          <button
            type="button"
            className="cat-chip-del"
            title={t.compose.delete}
            onClick={() => {
              if (window.confirm(t.compose.confirmDelete)) deleteCategory.mutate(c.id);
            }}
          >
            ✕
          </button>
        )}
      </span>
      <input ref={inputRef} type="file" accept="image/*" hidden onChange={onPickImage} />
    </div>
  );
}

/* ----- nagłówek kategorii (środek, na górze) ------------------------------ */

function CategoryBanner({ category, isMostActive, t }) {
  if (!category) {
    return (
      <div className="cat-banner bracketed">
        <span className="br-tr" />
        <span className="br-bl" />
        <div className="cat-banner-glyph">
          <div className="cat-glyph">★</div>
        </div>
        <div className="cat-banner-text">
          <span className="cat-banner-label mono up">{t.sections.categories}</span>
          <h1>{t.sections.allThreads}</h1>
          <p>{t.sections.allThreadsDesc}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="cat-banner bracketed fade-key" key={category.id}>
      <span className="br-tr" />
      <span className="br-bl" />
      <div className="cat-banner-glyph">
        <CategoryGlyph categoryId={category.id} name={category.name} />
      </div>
      <div className="cat-banner-text">
        {isMostActive && (
          <span className="cat-banner-label mono up">{t.sections.popularCat}</span>
        )}
        <h1>{category.name}</h1>
        <p>{category.description || '—'}</p>
      </div>
    </div>
  );
}

/* ----- hero (najlepszy wątek) --------------------------------------------- */

function Hero({ t, lang, featured, onRead }) {
  const hero = t.hero;
  const hasPost = Boolean(featured);
  // Liczba polubień pobierana z endpointu engagement (cache współdzielony z LikeButton)
  const { data: likeState } = useLikeState('posts', featured?.id, hasPost);
  const likes = likeState?.count ?? 0;
  const comments = featured?.comment_count ?? 0;

  return (
    <div className="featured-block">
      {hasPost && (
        <div className="featured-head">
          <span className="featured-label mono up">{t.sections.featuredThread}</span>
          <div className="featured-stats">
            <span className="featured-stat">
              <Icon name="heart" size={12} /> {likes} {t.sections.likes}
            </span>
            <span className="featured-stat">
              <Icon name="comment" size={12} /> {comments} {t.sections.comments}
            </span>
          </div>
        </div>
      )}
      <div className="hero bracketed featured">
        <span className="br-tr" />
        <span className="br-bl" />
        <div className="hero-main">
          <div className="hero-lead">
            {hasPost && (
              <div className="hero-icon">
                <ThreadGlyph
                  postId={featured.id}
                  category={featured.category}
                  name={featured.title}
                />
              </div>
            )}
            <div className="hero-text">
              <div className="tag fade-key" key={hasPost ? featured.id : hero.tag}>
                {hasPost && featured.category ? featured.category.name : hero.tag}
              </div>
              <h1>{hasPost ? featured.title : hero.title}</h1>
              <p>{hasPost ? excerptOf(featured.content) : hero.excerpt}</p>
            </div>
          </div>
          <div className="hero-actions">
            <button
              type="button"
              className="btn primary"
              onClick={() => hasPost && onRead(featured.id)}
              disabled={!hasPost}
            >
              {hero.read} <Icon name="arrow" size={12} />
            </button>
            {hasPost && (
              <span className="badge">
                @{featured.author?.username} · {timeAgo(featured.created_at, lang)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ThreadList({ query, lang, t }) {
  const navigate = useNavigate();
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} onRetry={query.refetch} />;
  const posts = query.data?.items ?? [];
  if (posts.length === 0) return <EmptyState />;

  return (
    <div className="threads">
      {posts.map((p) => (
        <article
          className="thread"
          key={p.id}
          onClick={() => navigate(`/posts/${p.id}`)}
          role="link"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && navigate(`/posts/${p.id}`)}
        >
          <div className="thread-icon">
            <ThreadGlyph postId={p.id} category={p.category} name={p.title} />
          </div>
          <div className="thread-body">
            <div className="thread-top">
              {p.category && <span className="thread-cat">{p.category.name}</span>}
              <span className="badge">{timeAgo(p.created_at, lang)}</span>
            </div>
            <h3 className="thread-title">{p.title}</h3>
            <div className="thread-meta">
              <span className="author">@{p.author?.username ?? '???'}</span>
              <span>·</span>
              <span>{p.comment_count} {t.compose.commentsTitle.toLowerCase()}</span>
            </div>
          </div>
          <div className="thread-stats">
            <span className="n">{p.comment_count}</span>
            <span className="l">{t.compose.commentsTitle.toLowerCase()}</span>
          </div>
        </article>
      ))}
    </div>
  );
}
