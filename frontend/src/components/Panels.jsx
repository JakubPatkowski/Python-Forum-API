import { useTranslation } from '../i18n/LangContext';
import { useTags } from '../hooks/useContentQueries';
import { NotSupportedTag } from './States';

/**
 * Panel popularnych tagów — realne tagi z API (/tags). Liczniki użycia nie są
 * jeszcze wystawiane przez backend, więc oznaczamy je jako „wkrótce”.
 */
export function TagsPanel({ title, meta, limit = 12 }) {
  const t = useTranslation();
  const { data: tags = [], isLoading, isError } = useTags();
  const shown = tags.slice(0, limit);

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <span className="head-id">{meta}</span>
      </div>
      <div className="tagline">
        {isLoading && <span className="mono dim">{t.common.loading}</span>}
        {isError && <span className="mono mute">{t.common.error}</span>}
        {!isLoading && !isError && shown.length === 0 && (
          <span className="mono mute">{t.common.empty}</span>
        )}
        {shown.map((tag) => (
          <div className="taglet" key={tag.id}>
            #{tag.name}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Panel „Top użytkownicy” — ranking reputacji nie istnieje jeszcze w API.
 * Pokazujemy uczciwy placeholder zamiast zmyślonych liczb.
 */
export function TopUsersPanel({ title, meta }) {
  const t = useTranslation();
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        <span className="head-id">{meta}</span>
      </div>
      <div className="panel-body">
        <div className="placeholder-row">
          <span className="mono mute">{t.common.notSupported}</span>
          <NotSupportedTag />
        </div>
      </div>
    </div>
  );
}
