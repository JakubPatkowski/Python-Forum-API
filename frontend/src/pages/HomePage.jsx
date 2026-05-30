import { useTranslation } from '../i18n/LangContext';
import { Icon } from '../components/Icon';
import { SectionHead } from '../components/SectionHead';

export function HomePage() {
  const t = useTranslation();
  return (
    <div className="shell">
      <Hero hero={t.hero} stats={t.stats} />
      <SectionHead title={t.sections.categories} meta={t.sections.categoriesMeta} />
      <CategoryGrid categories={t.categories} />

      <div className="main-grid">
        <div>
          <SectionHead
            title={t.sections.latest}
            meta={t.sections.latestMeta}
            right={
              <button type="button" className="btn">
                <Icon name="plus" size={12} /> {t.opinions.submit}
              </button>
            }
          />
          <ThreadList threads={t.threads} />
        </div>
        <HomeSidebar t={t} />
      </div>
    </div>
  );
}

/* ----- podsekcje strony głównej ------------------------------------------ */

function Hero({ hero, stats }) {
  return (
    <div className="hero bracketed">
      <span className="br-tr" />
      <span className="br-bl" />
      <div className="hero-main">
        <div className="tag fade-key" key={hero.tag}>{hero.tag}</div>
        <h1>{hero.title}</h1>
        <p>{hero.excerpt}</p>
        <div className="hero-actions">
          <button type="button" className="btn primary">
            {hero.read} <Icon name="arrow" size={12} />
          </button>
          <button type="button" className="btn">
            <Icon name="bm" size={12} /> {hero.bookmark}
          </button>
        </div>
      </div>
      <div className="hero-stats">
        <StatCell k={stats.members} v="14 821"            d={`↑ 2.4% ${stats.vsLast}`} />
        <StatCell k={stats.threads} v="12 024"            d={`↑ 1.1% ${stats.vsLast}`} />
        <StatCell k={stats.online}  v={<>312<span className="unit">/14k</span></>} d="●  live" />
        <StatCell k={stats.today}   v="487"               d={`↑ 8.7% ${stats.vsLast}`} />
      </div>
    </div>
  );
}

function StatCell({ k, v, d }) {
  return (
    <div className="stat-cell">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className="d">{d}</div>
    </div>
  );
}

function CategoryGrid({ categories }) {
  return (
    <div className="cat-grid">
      {categories.map((c) => (
        <div className="cat" key={c.code}>
          <div className="cat-top">
            <div className="cat-glyph">{c.code}</div>
            <div className="cat-arrow">→</div>
          </div>
          <h3>{c.name}</h3>
          <div className="cat-desc">{c.desc}</div>
          <div className="cat-meta">
            <span><b>{c.threads}</b>  thr</span>
            <span><b>{c.posts}</b>  msg</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ThreadList({ threads }) {
  return (
    <div className="threads">
      {threads.map((th) => (
        <article className="thread" key={th.id}>
          <div className="thread-id">{th.id}</div>
          <div className="thread-body">
            <div className="thread-top">
              <span className="thread-cat">{th.cat}</span>
              <span className="badge">{th.when}</span>
            </div>
            <h3 className="thread-title">{th.title}</h3>
            <div className="thread-meta">
              <span className="author">@{th.author}</span>
              <span>·</span>
              <span>{th.replies} replies</span>
              <span>·</span>
              <span>{th.views} views</span>
            </div>
          </div>
          <div className="thread-stats">
            <span className="n">{th.replies}</span>
            <span className="l">replies</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function HomeSidebar({ t }) {
  return (
    <aside className="sidebar">
      <TopUsersPanel
        title={t.sections.trending}
        meta={t.sections.trendingMeta}
        users={t.topUsers}
      />
      <TagsPanel
        title={t.sections.tags}
        meta={t.sections.tagsMeta}
        tags={t.tags}
      />
    </aside>
  );
}

export function TopUsersPanel({ title, meta, users }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <span className="head-id">{meta}</span>
      </div>
      <div className="panel-body">
        {users.map((u) => (
          <div className="userline" key={u.name}>
            <div className={'av ' + (u.av || '')}>
              {u.name.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="name">@{u.name}</div>
              <div className="role">{u.role}</div>
            </div>
            <div className="pts">{u.pts}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TagsPanel({ title, meta, tags }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <span className="head-id">{meta}</span>
      </div>
      <div className="tagline">
        {tags.map((tag) => {
          const [name, n] = tag.split('·');
          return (
            <div className="taglet" key={tag}>
              #{name}
              <span className="n">{n}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
