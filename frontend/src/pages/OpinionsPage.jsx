import { useMemo, useState } from 'react';
import { useTranslation } from '../i18n/LangContext';
import { Icon } from '../components/Icon';
import { SectionHead } from '../components/SectionHead';

const ALL_FILTER_INDEX = 0;

export function OpinionsPage() {
  const t = useTranslation();
  const o = t.opinions;
  const [filterIdx, setFilterIdx] = useState(ALL_FILTER_INDEX);

  // Filtracja po nazwie kategorii w aktualnym języku — wystarczająca dla mockowych danych.
  // Gdy dane przyjdą z API, lepiej porównywać po stabilnym `code`/`slug`.
  const visibleItems = useMemo(() => {
    if (filterIdx === ALL_FILTER_INDEX) return o.items;
    const filterLabel = o.filters[filterIdx].toUpperCase();
    return o.items.filter((it) => it.cat.toUpperCase() === filterLabel);
  }, [filterIdx, o.filters, o.items]);

  return (
    <div className="shell">
      <SectionHead title={o.title} meta={o.meta} />

      <div className="opinions-head">
        <div className="pill-row">
          {o.filters.map((f, i) => (
            <button
              key={f}
              type="button"
              className={'pill' + (filterIdx === i ? ' on' : '')}
              onClick={() => setFilterIdx(i)}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="filler" />
        <span className="badge">{o.sort}</span>
        <button type="button" className="btn primary">
          <Icon name="plus" size={12} /> {o.submit}
        </button>
      </div>

      <div className="opinions-grid">
        {visibleItems.map((it) => (
          <ReviewCard key={it.title} item={it} />
        ))}
      </div>
    </div>
  );
}

function ReviewCard({ item }) {
  return (
    <div className="review">
      <div className="review-thumb">{item.placeholder}</div>
      <div className="review-body">
        <div className="review-meta">
          <span className="cat">{item.cat}</span>
          <span>·</span>
          <span>{item.date}</span>
        </div>
        <h3>{item.title}</h3>
        <p className="quote">“{item.quote}”</p>
        <div className="review-foot">
          <div className="score">
            <div className="score-bar">
              <i style={{ width: `${item.score * 10}%` }} />
            </div>
            <span className="score-num">
              {item.score.toFixed(1)}
              <span className="max">/10</span>
            </span>
          </div>
          <div className="review-author">
            <div className="av">{item.author.slice(0, 2).toUpperCase()}</div>
            <span>@{item.author}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
