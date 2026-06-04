import { useEffect } from 'react';
import { useTranslation } from '../i18n/LangContext';
import { Icon } from './Icon';

/** Prosty modal: overlay + zamykanie Esc / kliknięciem w tło. */
export function Modal({ title, onClose, children }) {
  const t = useTranslation();

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        className="modal bracketed"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <span className="br-tr" />
        <span className="br-bl" />
        <div className="modal-head">
          <h2>{title}</h2>
          <button
            type="button"
            className="icon-btn"
            onClick={onClose}
            aria-label={t.common.close}
          >
            <Icon name="chev" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
