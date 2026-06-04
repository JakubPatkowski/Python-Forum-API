import { useEffect, useRef, useState } from 'react';
import { Icon } from '../Icon';

/**
 * Wybór ikony (obraz) dla wątku/kategorii. Trzyma plik w stanie rodzica
 * (przekazywany przez onChange) — upload dzieje się dopiero po utworzeniu
 * encji, bo endpointy ikon wymagają istniejącego id.
 *
 * `currentUrl` — opcjonalny podgląd już ustawionej ikony (tryb edycji).
 */
export function IconPicker({ file, onChange, label, hint, currentUrl = null }) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [imgError, setImgError] = useState(false);

  // Podgląd wybranego pliku (zwalniamy obiekt URL przy zmianie/odmontowaniu).
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // currentUrl może zwrócić 404 (brak ikony) — wtedy chowamy obraz.
  const shown = preview || (imgError ? null : currentUrl);

  const onPick = (e) => {
    const f = e.target.files?.[0] ?? null;
    e.target.value = '';
    if (f) onChange(f);
  };

  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <div className="icon-picker">
        <button
          type="button"
          className="icon-picker-preview"
          onClick={() => inputRef.current?.click()}
          title={label}
        >
          {shown ? (
            <img src={shown} alt="" onError={() => setImgError(true)} />
          ) : (
            <Icon name="plus" size={16} />
          )}
        </button>
        <div className="icon-picker-side">
          <div className="icon-picker-actions">
            <button
              type="button"
              className="btn"
              onClick={() => inputRef.current?.click()}
            >
              {shown ? label : <><Icon name="plus" size={12} /> {label}</>}
            </button>
            {file && (
              <button
                type="button"
                className="link-btn danger"
                onClick={() => onChange(null)}
              >
                ✕
              </button>
            )}
          </div>
          {hint && <span className="field-hint">{hint}</span>}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={onPick}
        />
      </div>
    </div>
  );
}
