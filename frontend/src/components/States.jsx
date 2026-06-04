import { useTranslation } from '../i18n/LangContext';

/** Spójne stany pomocnicze dla widoków opartych o React Query. */

export function LoadingState({ label }) {
  const t = useTranslation();
  return (
    <div className="state-box mono dim" role="status">
      {label ?? t.common.loading}
    </div>
  );
}

export function EmptyState({ label }) {
  const t = useTranslation();
  return <div className="state-box mono mute">{label ?? t.common.empty}</div>;
}

export function ErrorState({ error, onRetry }) {
  const t = useTranslation();
  const message = error?.message ?? t.common.error;
  return (
    <div className="state-box state-error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          {t.common.retry}
        </button>
      )}
    </div>
  );
}

/**
 * Mały „znacznik placeholdera” dla elementów designu, których API jeszcze nie
 * wspiera (np. liczniki online / reputacja). Czytelnie komunikuje, że to nie
 * są realne dane, zamiast pokazywać zmyślone liczby.
 */
export function NotSupportedTag() {
  const t = useTranslation();
  return (
    <span className="ns-tag" title={t.common.notSupported}>
      {t.common.soon}
    </span>
  );
}
